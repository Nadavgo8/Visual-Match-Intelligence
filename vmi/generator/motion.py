"""Private truth keyframes; consumers of the event feed cannot read future motion."""

from dataclasses import dataclass, field
import math


def formation_position(base_x, base_y, role, player_id, right, ball_x, ball_y, t):
    """Shared optical baseline; explicit encounter positions take precedence."""
    bax, bay = (ball_x, ball_y) if right else (105 - ball_x, 68 - ball_y)
    if role == "GK":
        ax, ay = base_x + max(0, (bax - 30) * 0.05), base_y + (bay - 34) * 0.12
    else:
        seed = sum(map(ord, player_id))
        ax = base_x + (bax - 52.5) * 0.45 + 1.2 * math.sin(t / 3.1 + seed)
        ay = base_y + (bay - base_y) * 0.25 + 1.2 * math.cos(t / 2.7 + seed * 0.7)
    x, y = (ax, ay) if right else (105 - ax, 68 - ay)
    return min(max(x, 0), 105), min(max(y, 0), 68)


@dataclass
class Keyframe:
    t: float
    x: float
    y: float
    holder: str | None
    in_play: bool
    z: float = 0.0
    flight_height: float = 0.0  # arc from this keyframe to the next one
    possession_id: str | None = None
    player_positions: dict[str, tuple[float, float]] = field(default_factory=dict)
