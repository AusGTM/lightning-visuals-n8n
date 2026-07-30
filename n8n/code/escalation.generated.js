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

module.exports = {
  ESCALATION_CONFIDENCE_BAND,
  JUDGE_MIN_CONFIDENCE,
  JUDGE_OUTPUT_REQUIRED,
  KNOWN_VIDEO_HOSTS,
};
