# scripts/provider_registry.py
#
# Phase 16.1 (reviews A3) — the single build-time source of provider adapters, kept
# SIDE-EFFECT-FREE: importing this module writes NO files, unlike build_cloud_workflows.py
# which writes taxonomy.generated.js/escalation.generated.js at import (:32-33). A
# read-only importer (Plan 02's scripts/check_provider_credits.py) can therefore pull
# PROVIDER_REGISTRY/PROVIDER_NAMES without triggering that codegen.
#
# The registry keys MUST equal normalizeProviders.js MAPPERS keys —
# tests/test_provider_registry_parity.py enforces set(PROVIDER_REGISTRY) == set(MAPPERS)
# so a provider can never be half-registered.
#
# ponytail: a dict + a mapper, not a plugin framework — two touch points to add a
# provider (one entry here + one MAPPERS function) is the irreducible minimum for a POC.

PROVIDER_REGISTRY = {
    "lusha": {
        "contact_node": "Lusha Enrich",
        "company_node": "Lusha Company",
        "normalize_key": "lusha",
        "credit": {
            "method": "GET", "url": "https://api.lusha.com/v3/account/usage",
            "auth": "header", "header": "api_key", "path": "credits.remaining",
        },
    },
    "apollo": {
        "contact_node": "Apollo Match",
        "company_node": "Apollo Org",
        "normalize_key": "apollo",
        "credit": {
            "method": "POST", "url": "https://api.apollo.io/api/v1/usage_stats/api_usage_stats",
            "auth": "header", "header": "X-Api-Key", "path": None,  # 403 w/o master key -> null
        },
    },
    "zoominfo": {
        "contact_node": "ZoomInfo Enrich",
        "company_node": "ZoomInfo Company",
        "normalize_key": "zoominfo",
        "credit": {
            "method": "GET", "url": "https://api.zoominfo.com/gtm/data/v1/users/usage",
            "auth": "bearer", "accept": "application/vnd.api+json",
            "path": "data[0].attributes.usage[limitType=uniqueIdLimit].usageRemaining",
        },
    },
}

# Canonical name order — baked into the runtime as `const PROVIDER_NAMES = [...]` the
# WRITE_SAFETY_DEFAULTS way (build_cloud_workflows.py, json.dumps into the generated
# jsCode). "all" resolves to exactly this set — no separate list to keep in sync. dict
# preserves insertion order (Python 3.7+); the order here is the existing waterfall
# priority order used throughout the codebase (Lusha, Apollo, ZoomInfo).
PROVIDER_NAMES = list(PROVIDER_REGISTRY.keys())
