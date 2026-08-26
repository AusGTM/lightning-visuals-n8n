// n8n/code/escalation.generated.js
//
// GENERATED FROM config/escalation_policy.yaml — DO NOT EDIT.
// Regenerate with: .venv/bin/python scripts/gen_escalation_js.py
//
// Threshold/vocabulary data only — see n8n/code/judge.js for the hand-written
// trigger logic that consumes this module.

const ESCALATION_CONFIDENCE_BAND = [75, 85];

const JUDGE_MIN_CONFIDENCE = 80;

const JUDGE_OUTPUT_REQUIRED = [
  "decision",
  "chosen_value",
  "confidence",
  "evidence_url",
  "evidence_summary",
  "validation_status",
  "reason"
];

const KNOWN_VIDEO_HOSTS = [
  "twitch.tv",
  "vimeo.com",
  "youtu.be",
  "youtube.com"
];

const MATERIAL_CONFLICT_GROUPS = [
  {
    "name": "country_region",
    "fields": [
      "lv_country_region_normalized",
      "country"
    ]
  },
  {
    "name": "org_type",
    "fields": [
      "lv_org_type"
    ]
  },
  {
    "name": "produces_content",
    "fields": [
      "lv_produces_content"
    ]
  },
  {
    "name": "hardware_vendor",
    "fields": [
      "lv_is_hardware_vendor"
    ]
  },
  {
    "name": "gambling_operator",
    "fields": [
      "lv_is_gambling_operator"
    ]
  }
];

module.exports = {
  ESCALATION_CONFIDENCE_BAND,
  JUDGE_MIN_CONFIDENCE,
  JUDGE_OUTPUT_REQUIRED,
  KNOWN_VIDEO_HOSTS,
  MATERIAL_CONFLICT_GROUPS,
};
