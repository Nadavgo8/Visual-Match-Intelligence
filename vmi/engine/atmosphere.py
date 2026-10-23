"""Conservative 80/20 crowd/controlled-attack meter; no emotion or xG inference."""

from dataclasses import dataclass
import math

FRESH_S = 0.5  # inclusive, in simulation time
STABLE_S = 0.3
CROWD_FRESH_S = 3.0
EPS = 1e-9


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def controlled_owner(frame: dict | None, now: float):
    if not frame or not frame.get("ball_in_play"):
        return None
    q, p = frame.get("quality", {}), frame.get("possession", {})
    if q.get("status") != "measured" or not _finite(q.get("confidence")) or q["confidence"] < 0.8:
        return None
    for stamp in (frame.get("t"), q.get("sample_t"), p.get("sample_t")):
        if not _finite(stamp) or not -EPS <= now - stamp <= FRESH_S + EPS:
            return None
    if p.get("status") != "controlled" or not isinstance(p.get("id"), str) or not p["id"] or p.get("team") not in {"home", "away"}:
        return None
    player = next((x for x in frame.get("players", []) if x.get("id") == p.get("holder_id")), None)
    if not player or player.get("team") != p["team"]:
        return None
    return p, player


def crowd_component(samples, now: float) -> float | None:
    if not samples or not -EPS <= now - samples[-1][0] <= CROWD_FRESH_S + EPS or samples[-1][1] is None:
        return None
    levels = []
    for t, level in reversed(samples):
        if level is None or now - t > CROWD_FRESH_S + EPS:
            break
        levels.append(level)
        if len(levels) == 3:
            break
    return sum(levels) / len(levels) if levels else None


@dataclass
class Atmosphere:
    mode: str = "combined"
    attack: float = 0
    owner_key: tuple | None = None
    candidate: float = 0
    candidate_since: float = 0
    last_sample: float = -1
    reason: str = "No reliable controlled attack"

    def __post_init__(self):
        if self.mode not in {"combined", "crowd_only"}:
            raise ValueError("atmosphere mode must be combined or crowd_only")

    def reset(self, reason="No reliable controlled attack"):
        self.attack = self.candidate = 0
        self.owner_key = None
        self.reason = reason

    def evaluate(self, now: float, frame: dict | None, ball_in_play: bool, crowd) -> dict:
        if self.mode not in {"combined", "crowd_only"}:
            raise ValueError("unknown atmosphere mode")
        if frame and frame["t"] - self.last_sample > FRESH_S + EPS:
            self.reset("Tracking gap interrupted stable possession")
        owner = controlled_owner(frame, now) if ball_in_play else None
        desired = 0
        key = None
        reason = "No reliable controlled attack"
        if owner:
            p, player = owner
            key = (p["team"], p["holder_id"], p["id"])
            role, period = player.get("role"), frame.get("period")
            ball = frame.get("ball")
            if role == "GK":
                reason = "Goalkeeper possession adds no attack component"
            elif role in {"RB", "CB", "LB", "CM", "DM", "RW", "ST", "LW"} and period in {1, 2} and isinstance(ball, list) and len(ball) == 2 and all(_finite(v) for v in ball):
                right = (p["team"] == "home") == (period == 1)
                ax, ay = ball if right else (105 - ball[0], 68 - ball[1])
                if 99.5 <= ax <= 105 and 24.84 <= ay <= 43.16:
                    desired = 1
                elif 88.5 <= ax <= 105 and 13.84 <= ay <= 54.16:
                    desired = 0.65
                elif 82.5 <= ax < 88.5 and 13.84 <= ay <= 54.16:
                    desired = 0.3
                reason = "Controlled possession near the opponent's goal" if desired else "No controlled attack near the opponent's box"
        if not desired:
            self.reset(reason)
        elif frame["t"] > self.last_sample:
            if key != self.owner_key:
                self.attack = 0
                self.candidate = desired
                self.candidate_since = frame["t"]
            elif desired != self.candidate:
                self.candidate = desired
                self.candidate_since = frame["t"]
            self.owner_key = key
            if desired < self.attack:
                self.attack = desired
            elif frame["t"] - self.candidate_since + EPS >= STABLE_S:
                self.attack = desired
            self.reason = reason
        if frame:
            self.last_sample = max(self.last_sample, frame["t"])
        c = crowd_component(crowd, now)
        attack = self.attack if self.mode == "combined" else 0
        value = (0.8 * c + 0.2 * attack if self.mode == "combined" else c) if c is not None else None
        return {"level": round(value, 3) if value is not None else None,
                "value_pct": round(value * 100, 1) if value is not None else None,
                "level5": min(5, 1 + int(value * 5)) if value is not None else None,
                "crowd": round(c, 3) if c is not None else None, "attack": attack,
                "available": value is not None, "crowd_available": c is not None, "mode": self.mode,
                "attack_team": self.owner_key[0] if attack and self.owner_key else None,
                "why": "Crowd data unavailable; use neutral display" if c is None else
                       "Explicit crowd-only mode" if self.mode == "crowd_only" else self.reason}
