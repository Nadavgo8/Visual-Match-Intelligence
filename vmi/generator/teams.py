"""Synthetic squads. Names and clubs are invented; no real teams or players."""

from __future__ import annotations

from dataclasses import dataclass

# 4-3-3 base shape in attack coordinates: x = 0 own goal line, 105 opponent goal line.
FORMATION_433 = [
    ("GK", 5, 34),
    ("RB", 28, 10), ("CB", 22, 26), ("CB", 22, 42), ("LB", 28, 58),
    ("CM", 42, 22), ("DM", 36, 34), ("CM", 42, 46),
    ("RW", 62, 12), ("ST", 66, 34), ("LW", 62, 56),
]


@dataclass
class Player:
    id: str
    team: str
    number: int
    name: str
    position: str
    base_x: float
    base_y: float


@dataclass
class Team:
    side: str  # "home" | "away"
    name: str
    short: str
    colour: str
    strength: float  # 0..1, nudges pass success and chance creation
    players: list[Player]
    bench: list[Player]


_HOME_NAMES = ["Okafor", "Lindqvist", "Brennan", "Haddad", "Moreau", "Sato",
               "Adeyemi", "Kovac", "Ferreira", "Dumont", "Reyes",
               "Novak", "Ibsen", "Calloway", "Mensah", "Torvik"]
_AWAY_NAMES = ["Varga", "Achebe", "Holloway", "Ricci", "Nakamura", "Petrov",
               "Delacroix", "Osei", "Brandt", "Marsh", "Quintero",
               "Ahlberg", "Silva", "Kerr", "Diallo", "Yilmaz"]
_NUMBERS = [1, 2, 4, 5, 3, 8, 6, 10, 7, 9, 11]
_BENCH = [("CM", 14), ("ST", 19), ("RW", 17), ("CB", 15), ("LB", 23)]


def _squad(side: str, names: list[str]) -> tuple[list[Player], list[Player]]:
    prefix = "H" if side == "home" else "A"
    starters = []
    for (pos, x, y), num, name in zip(FORMATION_433, _NUMBERS, names):
        starters.append(Player(f"{prefix}{num}", side, num, name, pos, x, y))
    bench = []
    for (pos, num), name in zip(_BENCH, names[11:]):
        bench.append(Player(f"{prefix}{num}", side, num, name, pos, 0, 0))
    return starters, bench


def make_teams() -> dict[str, Team]:
    hp, hb = _squad("home", _HOME_NAMES)
    ap, ab = _squad("away", _AWAY_NAMES)
    return {
        "home": Team("home", "Harbour City", "HAR", "#2E6FD8", 0.55, hp, hb),
        "away": Team("away", "Northvale Rovers", "NOR", "#E8E3D3", 0.5, ap, ab),
    }
