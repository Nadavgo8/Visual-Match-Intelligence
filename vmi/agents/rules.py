"""A small, plain-language knowledge base of the Laws of the Game and of our own metrics.

Written in our own words (not copied from IFAB). The rules expert agent reads it
through the get_rule tool so its answers stay grounded.
"""

from __future__ import annotations

RULES: dict[str, dict] = {
    "offside": {
        "keywords": ["offside", "flag", "last defender"],
        "text": ("A player is offside if, when a team-mate passes the ball, they are in the opponents' half and "
                 "closer to the goal line than both the ball and the second-last defender (usually the last outfield "
                 "defender, since the goalkeeper is normally the last). Being there is not an offence on its own: it "
                 "only counts if the player then gets involved in play. There is no offside from a throw-in, a goal "
                 "kick or a corner. The punishment is an indirect free kick to the defending team."),
    },
    "penalty": {
        "keywords": ["penalty", "spot kick", "pen ", "in the box", "penalty area"],
        "text": ("A penalty is given when a defending player commits a direct free-kick foul (such as a trip, push, "
                 "kick, holding or a deliberate handball) inside their own penalty area while the ball is in play. "
                 "The kick is taken from the penalty mark, 11 metres out, with only the goalkeeper to beat."),
    },
    "var": {
        "keywords": ["var", "video", "review", "monitor", "overturn"],
        "text": ("VAR (the video assistant referee) checks four kinds of decisions: goals, penalties, direct red "
                 "cards and mistaken identity. It only steps in for a clear and obvious error or a serious missed "
                 "incident. For judgement calls the referee is asked to watch the replay at the pitch-side monitor "
                 "(an on-field review) and makes the final decision. Factual calls like offside positions can be "
                 "changed without the monitor."),
    },
    "yellow_card": {
        "keywords": ["yellow", "booking", "booked", "caution"],
        "text": ("A yellow card is a caution for things like reckless challenges, persistent fouling, dissent, time "
                 "wasting, or stopping a promising attack with a foul. Two yellow cards in one match mean a red card "
                 "and the player must leave the pitch."),
    },
    "red_card": {
        "keywords": ["red card", "sent off", "sending off", "dismiss"],
        "text": ("A red card sends a player off for the rest of the match and the team cannot replace them. It is "
                 "given for serious foul play, violent conduct, denying an obvious goal-scoring opportunity by a "
                 "foul or handball, offensive language, or a second yellow card."),
    },
    "advantage": {
        "keywords": ["advantage", "play on", "didn't blow", "no whistle"],
        "text": ("If a foul happens but stopping play would hurt the team that was fouled, the referee can let play "
                 "continue (play advantage). The foul can still be punished with a card at the next stoppage. If the "
                 "advantage does not come within a few seconds, the referee can go back and give the free kick."),
    },
    "handball": {
        "keywords": ["handball", "hand ball", "arm"],
        "text": ("It is handball if a player deliberately touches the ball with their hand or arm, or makes their "
                 "body unnaturally bigger with their arm and the ball hits it. A goal scored straight off an "
                 "attacker's hand or arm, even by accident, does not count."),
    },
    "foul": {
        "keywords": ["foul", "trip", "push", "tackle", "free kick", "free-kick"],
        "text": ("A foul is careless, reckless or excessive contact such as tripping, pushing, kicking, holding or "
                 "charging an opponent. The other team gets a direct free kick where it happened, or a penalty if it "
                 "happened inside the fouling player's own penalty area."),
    },
    "added_time": {
        "keywords": ["added time", "stoppage time", "extra minutes", "injury time"],
        "text": ("At the end of each half the fourth official shows the minimum time added for time lost to "
                 "substitutions, injuries, VAR checks, goal celebrations and time wasting. The referee can play "
                 "longer than shown, but not less."),
    },
    "substitution": {
        "keywords": ["substitution", "sub ", "subs", "replace", "bench"],
        "text": ("In most top competitions each team can make up to five substitutions, in no more than three "
                 "breaks during play (half-time does not count as one). A player who has been substituted cannot "
                 "come back on."),
    },
    "kick_off": {
        "keywords": ["kick-off", "kick off", "kickoff"],
        "text": ("A kick-off starts each half and restarts play after a goal. The team that conceded the goal kicks "
                 "off from the centre spot."),
    },
    "restarts": {
        "keywords": ["throw-in", "throw in", "corner", "goal kick", "goal-kick"],
        "text": ("When the ball goes over the touchline it is a throw-in to the team that did not touch it last. "
                 "Over the goal line (not a goal): a corner if a defender touched it last, a goal kick if an "
                 "attacker did."),
    },
    "whistle": {
        "keywords": ["whistle", "blew", "blow"],
        "text": ("The referee's whistle stops play (fouls, offside, injuries), starts it (kick-offs, penalties, some "
                 "free kicks) and ends each half. Two blasts usually mean a stop for something unusual like a "
                 "review; long blasts are used for half-time and full-time. In this app each whistle type has its "
                 "own banner in a fixed place on the screen."),
    },
    "xg": {
        "keywords": ["xg", "expected goals", "chance quality", "big chance"],
        "text": ("xG (expected goals) is the probability that a shot from that position becomes a goal, based on "
                 "distance and the angle to the goal. 0.05 is a long-range hopeful shot, 0.3+ is a big chance, and "
                 "a penalty is about 0.77. This demo uses delayed synthetic generator estimates, not a calibrated model."),
    },
    "momentum": {
        "keywords": ["momentum", "on top", "bar under the score", "pressure"],
        "text": ("The momentum bar shows which team has been on top over the last 7 minutes. It weighs possession "
                 "time 40%, key passes (passes straight into a shot) 30% and shots 30%. It is a fan feature that "
                 "summarises the run of play, not an official statistic."),
    },
    "atmosphere": {
        "keywords": ["atmosphere", "crowd", "loud", "noise", "meter", "glow"],
        "text": ("The two identical bars at the screen edges show one atmosphere level for the whole stadium: 80% "
                 "how loud the crowd is and up to 20% for a detected attack near the opponents' goal. Fill height "
                 "and colour (turquoise to amber) change together, so it never relies on colour alone, and missing "
                 "crowd data is shown as unavailable, not as quiet. The sensor measures loudness only. It cannot "
                 "tell boos from cheers, so the app never claims why the crowd reacted, only what happened just before."),
    },
}


def lookup(topic: str) -> dict:
    t = f" {topic.lower()} "
    best, score = None, 0
    for key, r in RULES.items():
        s = sum(len(k) for k in r["keywords"] if k in t) + (5 if key.replace("_", " ") in t else 0)
        if s > score:
            best, score = key, s
    if not best:
        return {"topic": topic, "found": False, "known_topics": sorted(RULES), "evidence": []}
    return {"topic": best, "found": True, "text": RULES[best]["text"], "evidence": [f"rule:{best}"]}
