"""The v2 delivered-record boundary. Unknown major versions fail explicitly."""

import math

VERSION = "2.0"
LINK_PARENTS = {"shot_result": {"shot_id": "shot"}, "shot_xg": {"shot_id": "shot"},
                "goal_cancelled": {"shot_id": "shot", "result_id": "shot_result", "decision_id": "referee_decision"},
                "referee_decision": {"trigger_event_id": None, "stoppage_id": "play_stopped"},
                "restart_awarded": {"decision_id": "referee_decision", "stoppage_id": "play_stopped"},
                "restart_taken": {"restart_id": "restart_awarded", "stoppage_id": "play_stopped"}}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_record(rec: dict, match_id: str) -> None:
    if rec.get("schema_version") != VERSION:
        raise ValueError("unsupported schema_version; v2 is required")
    if not _number(rec.get("t")) or rec["t"] < 0:
        raise ValueError("invalid event time")
    if rec.get("match_id") != match_id:
        raise ValueError("record belongs to another match")
    stream = rec.get("stream")
    if stream:
        if stream not in {"crowd", "match_state", "tracking"}:
            raise ValueError("unknown stream")
        if stream == "crowd" and (not _number(rec.get("crowd_level")) or not 0 <= rec["crowd_level"] <= 1):
            raise ValueError("invalid crowd level")
        if stream == "match_state" and not isinstance(rec.get("ball_in_play"), bool):
            raise ValueError("invalid play state")
        quality = rec.get("quality", {})
        if not isinstance(quality, dict):
            raise ValueError("invalid measurement quality")
        if "confidence" in quality and (not _number(quality["confidence"]) or not 0 <= quality["confidence"] <= 1):
            raise ValueError("invalid measurement confidence")
        if stream == "tracking":
            for player in rec.get("players", []):
                if "motion" not in player:
                    continue
                motion = player["motion"]
                if (not isinstance(motion, dict) or set(motion) != {"heading", "speed", "distance"}
                        or not all(_number(value) for value in motion.values())
                        or not -math.pi <= motion["heading"] <= math.pi
                        or motion["speed"] < 0 or motion["distance"] < 0):
                    raise ValueError("invalid source player motion")
        return
    if not isinstance(rec.get("id"), str) or not rec["id"]:
        raise ValueError("event id is required")
    if not _number(rec.get("delivered_t")) or rec["delivered_t"] < rec["t"]:
        raise ValueError("invalid delivery time")
    kind = rec.get("type")
    if not isinstance(kind, str) or not kind:
        raise ValueError("event type is required")
    if kind in {"pass", "shot", "foul", "handball", "dribble", "carry", "set_piece", "whistle", "substitution", "card", "var",
                "offside", "injury_stoppage", "period_start", "period_end", "added_time"}:
        # Some qualifier-free events intentionally have no nested payload.
        if kind not in {"offside", "injury_stoppage"} and not isinstance(rec.get(kind), dict):
            raise ValueError(f"{kind} payload is required")
    if kind == "dribble" and rec["dribble"].get("outcome") not in {"complete", "failed", "interrupted", "unresolved"}:
        raise ValueError("unknown dribble outcome")
    if kind == "dribble" and (not isinstance(rec["dribble"].get("defender_id"), str)
                              or not rec["dribble"]["defender_id"]
                              or rec["dribble"]["defender_id"] == rec.get("player_id")):
        raise ValueError("dribble requires a distinct identified defender")
    if kind == "handball" and rec["handball"].get("offence") is not True:
        raise ValueError("handball record requires a reported offence")
    for key in LINK_PARENTS.get(kind, {}):
        if not isinstance(rec.get(key), str) or not rec[key] or rec[key] == rec["id"]:
            raise ValueError(f"invalid {key}")
    if kind == "shot":
        if not isinstance(rec.get("shot"), dict) or "outcome" in rec["shot"] or "xg" in rec["shot"]:
            raise ValueError("shot cannot contain its result or xG")
    if kind == "shot_result" and rec.get("outcome") not in {"goal", "saved", "blocked", "post", "off_target"}:
        raise ValueError("invalid shot result")
    if kind == "shot_xg":
        if rec.get("source") != "synthetic_analytics" or not rec.get("method_version"):
            raise ValueError("xG requires synthetic provenance")
        if not _number(rec.get("xg")) or not 0 <= rec["xg"] <= 1:
            raise ValueError("invalid xG")
    elif "xg" in rec:
        raise ValueError("xG is allowed only in shot_xg")
    if kind == "referee_decision" and rec.get("decision") not in {
            "penalty", "no_penalty", "free_kick", "kick_off", "goal_kick", "corner", "throw_in"}:
        raise ValueError("unknown referee decision")
