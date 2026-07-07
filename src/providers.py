# src/providers.py
#
# Mock provider adapters. Transcribed from CLAUDE.md §12.2.
# Each adapter reads its repo-root-relative fixture and returns a ProviderResult.
import json
from pathlib import Path
from typing import List
from .schemas import HubSpotRecord, ProviderResult

FIXTURE_DIR = Path("tests/fixtures")


class ProviderAdapter:
    name: str

    def enrich(self, record: HubSpotRecord) -> ProviderResult:
        raise NotImplementedError


class MockApolloCompanyAdapter(ProviderAdapter):
    name = "apollo"

    def enrich(self, record: HubSpotRecord) -> ProviderResult:
        return ProviderResult(**json.loads((FIXTURE_DIR / "provider_apollo_company.json").read_text()))


class MockLushaCompanyAdapter(ProviderAdapter):
    name = "lusha"

    def enrich(self, record: HubSpotRecord) -> ProviderResult:
        return ProviderResult(**json.loads((FIXTURE_DIR / "provider_lusha_company.json").read_text()))


class MockZoomInfoCompanyAdapter(ProviderAdapter):
    name = "zoominfo"

    def enrich(self, record: HubSpotRecord) -> ProviderResult:
        return ProviderResult(**json.loads((FIXTURE_DIR / "provider_zoominfo_company.json").read_text()))


def get_mock_provider_waterfall() -> List[ProviderAdapter]:
    return [
        MockZoomInfoCompanyAdapter(),
        MockApolloCompanyAdapter(),
        MockLushaCompanyAdapter()
    ]
