"""Derived facts: everything the raw feed does not say but a model can work out."""

from __future__ import annotations

import math

PITCH_X, PITCH_Y = 105.0, 68.0
BOX_DEPTH, BOX_Y = 16.5, (13.84, 54.16)
PENALTY_XG = 0.76


def attacks_right(team: str, period: int) -> bool:
    return (team == "home") == (period == 1)


def attack_coords(team: str, period: int, loc: list[float]) -> tuple[float, float]:
    """Convert a pitch location into the team's attack frame (x towards the goal it attacks)."""
    x, y = loc
    if attacks_right(team, period):
        return x, y
    return PITCH_X - x, PITCH_Y - y


def in_opponent_box(team: str, period: int, loc: list[float] | None) -> bool | None:
    if not loc:
        return None
    ax, ay = attack_coords(team, period, loc)
    return ax >= PITCH_X - BOX_DEPTH and BOX_Y[0] <= ay <= BOX_Y[1]


def in_own_box(team: str, period: int, loc: list[float] | None) -> bool | None:
    """For a defender's event: is it inside the box they defend?"""
    if not loc:
        return None
    ax, ay = attack_coords(team, period, loc)
    return ax <= BOX_DEPTH and BOX_Y[0] <= ay <= BOX_Y[1]


def zone(team: str, period: int, loc: list[float] | None) -> str | None:
    """Flank of an attacking action, from the attacking team's point of view."""
    if not loc:
        return None
    _, ay = attack_coords(team, period, loc)
    # attacking right, y=0 is the right-hand touchline
    if ay < 22:
        return "right"
    if ay > 46:
        return "left"
    return "centre"


def estimate_xg(team: str, period: int, loc: list[float] | None, body_part: str | None,
                penalty: bool = False) -> float | None:
    """Location-only expected goals model (distance and goal-mouth angle).

    The generator's true chance quality includes hidden factors, so this is an
    estimate, as with any real xG model.
    """
    if penalty:
        return PENALTY_XG
    if not loc:
        return None
    ax, ay = attack_coords(team, period, loc)
    dx = max(PITCH_X - ax, 0.5)
    dy = abs(ay - PITCH_Y / 2)
    dist = math.hypot(dx, dy)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2)
    if angle < 0:
        angle += math.pi
    z = -1.55 - 0.11 * dist + 1.4 * angle - (0.75 if body_part == "head" else 0)
    return round(1 / (1 + math.exp(-z)), 2)


def clock_seconds(clock: str) -> int:
    """'66:08' -> 3968, "45+2'" -> 2760 (start of the added minute)."""
    clock = clock.strip("'")
    if "+" in clock:
        base, extra = clock.split("+")
        return int(base) * 60 + (int(extra) - 1) * 60
    m, s = clock.split(":")
    return int(m) * 60 + int(s)


def minute_of(clock: str) -> int:
    """The minute as the TV clock shows it: '66:08' -> 66, "90+3'" -> 90."""
    clock = clock.strip("'")
    if "+" in clock:
        return int(clock.split("+")[0])
    return int(clock.split(":")[0])
