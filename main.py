import json
import os
from pathlib import Path
from dotenv import load_dotenv

from src.schemas import HubSpotRecord
from src.providers import get_mock_provider_waterfall
from src.web_research import claude_web_research
from src.normalizer import provider_to_candidates
from src.merge_policy import build_merge_result
from src.hubspot_client import patch_record

# DEVIATION 1 (vs CLAUDE.md §12.10): load_dotenv() is NOT called at module import.
# A real .env with ANTHROPIC_API_KEY exists; a module-level load would leak the key
# into `import main`, firing live Haiku calls inside the hermetic pytest suite. It is
# loaded only under the __main__ guard below, so `import main` stays side-effect-free.


def load_fixture(path):
    return json.loads(Path(path).read_text())


def run_local_mvp():
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow_canonical = os.getenv("ALLOW_CANONICAL_WRITES", "false").lower() == "true"
    allow_icp_score_writes = os.getenv("ALLOW_ICP_SCORE_WRITES", "true").lower() == "true"
    allow_staging = os.getenv("ALLOW_STAGING_WRITES", "true").lower() == "true"

    record = HubSpotRecord(**load_fixture("tests/fixtures/company_current.json"))

    provider_results = []
    all_candidates = []

    providers = get_mock_provider_waterfall()

    for provider in providers:
        result = provider.enrich(record)
        provider_results.append(result)
        all_candidates.extend(provider_to_candidates(result))

    web_result = claude_web_research(record)
    provider_results.append(web_result)
    all_candidates.extend(provider_to_candidates(web_result))

    merge_result = build_merge_result(record, all_candidates)

    patch = {}

    if allow_staging:
        patch.update(merge_result.staging_patch)
        patch.update(merge_result.metadata_patch)

    patch.update(merge_result.status_patch)

    if allow_canonical:
        patch.update(merge_result.canonical_patch)
    else:
        if allow_icp_score_writes and merge_result.icp_score:
            for key in [
                "lv_icp_fit_score",
                "lv_icp_tier",
                "lv_anti_icp_flag",
                "lv_anti_icp_reason",
                "lv_icp_score_breakdown",
                "lv_icp_scored_at",
                "lv_icp_scoring_version",
                "lv_icp_confidence",
                "lv_icp_needs_review",
                "lv_recommended_motion"
            ]:
                if key in merge_result.canonical_patch:
                    patch[key] = merge_result.canonical_patch[key]

    print("\n=== Provider + Research Results ===")
    print(json.dumps([r.model_dump() for r in provider_results], indent=2, default=str))

    print("\n=== Field Decisions ===")
    print(json.dumps([d.model_dump() for d in merge_result.field_decisions], indent=2, default=str))

    print("\n=== ICP Score ===")
    print(json.dumps(merge_result.icp_score.model_dump() if merge_result.icp_score else None, indent=2, default=str))

    print("\n=== HubSpot Patch Payload ===")
    print(json.dumps(patch, indent=2, default=str))

    patch_record(
        object_type=record.object_type,
        record_id=record.id,
        properties=patch,
        dry_run=dry_run
    )

    # DEVIATION 2 (vs CLAUDE.md §12.10): return the assembled emitted patch dict so the
    # offline gate (tests/test_main.py) asserts on it deterministically instead of stdout.
    return patch


def run_ingest_cli(path):
    # Phase 8: --ingest entrypoint. Reads the same env gates the pipeline honors and
    # prints the per-row report. dry_run defaults True and ALLOW_CONTACT_CREATE off, so
    # a bare run never writes or creates.
    from src.ingest import run_contact_ingest
    from collections import Counter

    allow_create = os.getenv("ALLOW_CONTACT_CREATE", "false").lower() == "true"
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    report = run_contact_ingest(path, allow_create=allow_create, dry_run=dry_run)

    print("\n=== Contact Ingest Report ===")
    print(json.dumps(report, indent=2, default=str))
    counts = Counter(entry["action"] for entry in report)
    print("\n=== Action Summary ===")
    print(", ".join(f"{action}={n}" for action, n in sorted(counts.items())))
    return report


if __name__ == "__main__":
    import sys

    load_dotenv()
    if "--ingest" in sys.argv:
        path = sys.argv[sys.argv.index("--ingest") + 1]
        run_ingest_cli(path)
    else:
        run_local_mvp()
