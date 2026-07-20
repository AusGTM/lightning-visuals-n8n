// n8n/code/taxonomy.generated.js
//
// GENERATED FROM config/taxonomy.yaml — DO NOT EDIT.
// taxonomy version: lv-taxonomy-v1
// Regenerate with: .venv/bin/python scripts/gen_taxonomy_js.py
//
// Vocabulary data only (spec D2) — see n8n/code/taxonomy.js for the
// hand-written normalizer logic that consumes this module.

const TAXONOMY_VERSION = "lv-taxonomy-v1";

const ORG_TYPES = [
  "governing_body_league",
  "content_producer",
  "broadcaster",
  "individual_club_team",
  "regulator",
  "gambling_operator",
  "hardware_vendor",
  "other",
  "unknown"
];

const ORG_TYPE_SYNONYMS = {
  "league": "governing_body_league",
  "governing body": "governing_body_league",
  "peak body": "governing_body_league",
  "racing authority": "governing_body_league",
  "sporting authority": "governing_body_league",
  "sports governing body": "governing_body_league",
  "controlling body": "governing_body_league",
  "production company": "content_producer",
  "media producer": "content_producer",
  "content studio": "content_producer",
  "production house": "content_producer",
  "media company": "content_producer",
  "tv network": "broadcaster",
  "television network": "broadcaster",
  "network": "broadcaster",
  "channel": "broadcaster",
  "broadcast network": "broadcaster",
  "free to air": "broadcaster",
  "club": "individual_club_team",
  "team": "individual_club_team",
  "racing club": "individual_club_team",
  "football club": "individual_club_team",
  "sporting club": "individual_club_team",
  "franchise team": "individual_club_team",
  "regulatory body": "regulator",
  "regulator authority": "regulator",
  "commission": "regulator",
  "integrity body": "regulator",
  "bookmaker": "gambling_operator",
  "betting operator": "gambling_operator",
  "wagering operator": "gambling_operator",
  "sportsbook": "gambling_operator",
  "casino": "gambling_operator",
  "online gambling": "gambling_operator",
  "av vendor": "hardware_vendor",
  "led vendor": "hardware_vendor",
  "display vendor": "hardware_vendor",
  "av integrator": "hardware_vendor",
  "systems integrator": "hardware_vendor",
  "equipment supplier": "hardware_vendor",
  "hardware supplier": "hardware_vendor"
};

const EVIDENCE_GATED_ORG_TYPES = [
  "content_producer",
  "gambling_operator",
  "governing_body_league",
  "hardware_vendor"
];

const DEFAULT_ORG_TYPE = "unknown";

const CONTENT_TYPES = [
  "live_broadcast",
  "streaming",
  "near_live",
  "highlights",
  "none",
  "unknown"
];

const CONTENT_TYPE_SYNONYMS = {
  "live tv": "live_broadcast",
  "live coverage": "live_broadcast",
  "live racing": "live_broadcast",
  "broadcast": "live_broadcast",
  "live stream": "streaming",
  "livestream": "streaming",
  "ott": "streaming",
  "watch live": "streaming",
  "streaming platform": "streaming",
  "delayed coverage": "near_live",
  "near live": "near_live",
  "replays": "highlights",
  "clips": "highlights",
  "highlights package": "highlights"
};

const CONTENT_TYPE_IMPLIES = {
  "live_broadcast": true,
  "streaming": true,
  "near_live": true,
  "highlights": true,
  "none": false,
  "unknown": null
};

const DEFAULT_CONTENT_TYPE = "unknown";

module.exports = {
  TAXONOMY_VERSION,
  ORG_TYPES,
  ORG_TYPE_SYNONYMS,
  EVIDENCE_GATED_ORG_TYPES,
  DEFAULT_ORG_TYPE,
  CONTENT_TYPES,
  CONTENT_TYPE_SYNONYMS,
  CONTENT_TYPE_IMPLIES,
  DEFAULT_CONTENT_TYPE,
};
