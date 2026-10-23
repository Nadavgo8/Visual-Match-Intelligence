"""Synthetic, uncalibrated chance estimates, independent of a shot's result."""

import math
import random

METHOD_VERSION = "synthetic-geometry-1"


def chance_quality(ax: float, ay: float, header: bool = False, penalty: bool = False) -> float:
    if penalty:
        return 0.77
    dx, dy = 105.0 - ax, abs(ay - 34.0)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66 ** 2)
    if angle < 0:
        angle += math.pi
    z = -1.6 - 0.115 * math.hypot(dx, dy) + 1.45 * angle - (0.8 if header else 0)
    return 1 / (1 + math.exp(-z))


def delayed_xg(seed: int, shot: dict, ax: float, ay: float, header: bool,
               delay_range: tuple[float, float]) -> dict:
    low, high = delay_range
    if not (math.isfinite(low) and math.isfinite(high) and 0 <= low <= high):
        raise ValueError("xG delays must be finite, nonnegative and ordered")
    rng = random.Random(f"{seed}:{shot['id']}:{METHOD_VERSION}")
    available = round(shot["t"] + rng.uniform(low, high), 2)
    return {
        "schema_version": "2.0", "id": f"xg_{shot['id']}", "match_id": shot["match_id"],
        "source": "synthetic_analytics", "type": "shot_xg", "shot_id": shot["id"],
        "t": available, "delivered_t": round(available + rng.uniform(0.1, 0.3), 2),
        "period": shot["period"], "clock": shot["clock"], "team": shot["team"],
        "player_id": shot["player_id"], "method_version": METHOD_VERSION,
        "xg": round(chance_quality(ax, ay, header, shot["shot"].get("penalty", False)), 3),
    }
