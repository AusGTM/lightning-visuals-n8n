// n8n/code/icpScoring.generated.js
//
// GENERATED FROM config/icp_scoring.yaml — DO NOT EDIT.
// Regenerate with: .venv/bin/python scripts/gen_icp_scoring_js.py
//
// Region whitelist / veto reason / geography point data only — see
// scripts/build_cloud_workflows.py's ENRICH_DECIDE_CO_CLOUD for the
// hand-written logic that consumes this module.

const VERSION = "lv-icp-v0.2";

const REGIONS_HOME = [
  "AU",
  "NZ",
  "ANZ",
  "US",
  "GB",
  "IE",
  "CA",
  "ZA",
  "HK",
  "SG",
  "AE",
  "IN"
];

const REGION_ALIASES = {
  "australia": "AU",
  "au": "AU",
  "aus": "AU",
  "new zealand": "NZ",
  "nz": "NZ",
  "anz": "ANZ",
  "us": "US",
  "united states": "US"
};

const HARD_VETO_REASONS = {
  "outside_home_regions": "Outside target regions",
  "no_content": "No broadcast or streaming content",
  "hardware_vendor": "Hardware/AV/LED vendor, not sports-media buyer"
};

const GEOGRAPHY_POINTS = {
  "home": 10,
  "other": 0,
  "unknown": 0
};

module.exports = {
  VERSION,
  REGIONS_HOME,
  REGION_ALIASES,
  HARD_VETO_REASONS,
  GEOGRAPHY_POINTS,
};
