"""The shared D2-00 question set: 30 English questions on frozen v2.2 seed 12.

Each question is asked at a snapshot time. The fact pack a model receives is built
from the engine after replaying only what was delivered by that time, so a correct
answer never needs the future. Future-only facts (later scores, players who only
appear later) are listed per item so the scorer can flag a leak.

The benchmark input is pinned in fixtures/demo-v2.2.json.gz. This timeline is
not a promise about a later generator version's demo. For reading the items:
18:22 home goal (1-0); 38:37 VAR penalty
check, overturned to a penalty for the away team at 39:32; 40:40 away goal (1-1);
VAR goal check stands; half-time; 52:06 home winner (2-1); subs from 56:43.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SEED = 12

# Snapshot times in simulation seconds (see the timeline above).
S_EARLY = 1500.0  # 25:00, home lead 1-0
S_PENALTY = 2400.0  # 40:00, penalty awarded after VAR, not yet taken
S_HALF_TIME = 2980.0  # half-time break, 1-1
S_LATE = 4500.0  # about 75:00, 2-1 after subs

CATEGORIES = {"fact": 10, "interpretation": 5, "rules": 5, "summary": 5, "trap": 5}


@dataclass(frozen=True)
class Item:
    id: str
    category: str
    question: str
    snapshot_t: float
    expect: tuple[str, ...] = ()  # words a good answer is likely to contain (informative only)
    rule_topic: str | None = None
    window_s: float | None = None  # summaries: seconds before the snapshot to cover
    trap: str | None = None  # what a correct answer must do, for human review
    profile: dict = field(default_factory=lambda: {"depth": "basic"})


ITEMS: tuple[Item, ...] = (
    # facts and stats
    Item("F01", "fact", "What's the score right now?", S_EARLY, ("1", "0")),
    Item("F02", "fact", "Who scored for Harbour City?", S_EARLY, ("Reyes",)),
    Item("F03", "fact", "In which minute was the goal scored?", S_EARLY, ("18",)),
    Item("F04", "fact", "How many shots has each team had so far?", S_EARLY),
    Item("F05", "fact", "What did VAR decide about the penalty incident?", S_PENALTY, ("penalty", "overturned")),
    Item("F06", "fact", "Who got the yellow card?", S_PENALTY, ("Brennan",)),
    Item("F07", "fact", "What was the half-time score?", S_HALF_TIME, ("1",)),
    Item("F08", "fact", "Who scored for Northvale Rovers?", S_HALF_TIME, ("Marsh",)),
    Item("F09", "fact", "How many substitutions has each team made?", S_LATE),
    Item("F10", "fact", "Who is on top in the last seven minutes?", S_LATE),
    # interpretation
    Item("I01", "interpretation", "Is Harbour City dominating this game?", S_EARLY),
    Item("I02", "interpretation", "How big a moment is this penalty for Northvale Rovers?", S_PENALTY),
    Item("I03", "interpretation", "Which team looked more dangerous in the first half?", S_HALF_TIME),
    Item("I04", "interpretation", "What changed after Harbour City's second goal?", S_LATE),
    Item("I05", "interpretation", "Are Northvale Rovers pushing for an equaliser?", S_LATE),
    # rules
    Item("R01", "rules", "Why can VAR overturn the referee's decision?", S_PENALTY, rule_topic="var"),
    Item("R02", "rules", "What is offside?", S_EARLY, rule_topic="offside"),
    Item("R03", "rules", "What happens when a penalty is given?", S_PENALTY, rule_topic="penalty"),
    Item("R04", "rules", "Why is there added time at the end of a half?", S_HALF_TIME, rule_topic="added_time"),
    Item("R05", "rules", "When is a handball an offence?", S_EARLY, rule_topic="handball"),
    # summaries ("What did I miss?" style)
    Item("Y01", "summary", "What did I miss in the last 10 minutes?", S_EARLY, window_s=600),
    Item("Y02", "summary", "Catch me up on the last 5 minutes.", S_PENALTY, window_s=300),
    Item("Y03", "summary", "Summarise the first half.", S_HALF_TIME, window_s=S_HALF_TIME),
    Item("Y04", "summary", "What did I miss since the second half started?", S_LATE, window_s=S_LATE - 3011),
    Item("Y05", "summary", "What happened in the last 15 minutes?", S_LATE, window_s=900),
    # traps: future, crowd motive, false premise
    Item("T01", "trap", "Who scores the winning goal?", S_EARLY, trap="refuse to predict; say the match is still 1-0"),
    Item("T02", "trap", "What will the final score be?", S_PENALTY, trap="refuse to predict the result"),
    Item("T03", "trap", "Why did the crowd boo the referee?", S_PENALTY,
         trap="say the sensor measures loudness only and cannot tell why or whether it was booing"),
    Item("T04", "trap", "How did the red card change the game?", S_HALF_TIME,
         trap="correct the premise: there has been no red card"),
    Item("T05", "trap", "Did Northvale Rovers' second goal come from a corner?", S_LATE,
         trap="correct the premise: Northvale Rovers have scored once"),
)
