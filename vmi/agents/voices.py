"""The chat's two voices, worded by code: Kai (commentator) and Ada (analyst).

Kai's live lines are written here from the facts the engine attached to each item (`say`),
in a "friend next to you" tone with a burst of excitement only at the peaks. Each item picks
one of several phrasings from a hash of its cue id, so a replay reads the same every time
and two goals don't sound identical. Nothing here adds a fact: every name, number and score
comes from `say`, and no line says why the crowd reacted.

After Ada's analysis, Kai may add one closing line to her, built from the analysis fact pack
(the crowd's measured jump, or the time left). It is the last turn: nothing replies to it.
"""

from __future__ import annotations

import zlib


def _pick(cue_id: str, options: list[str]) -> str:
    return options[zlib.crc32(cue_id.encode()) % len(options)]


SHOT_OUTCOME = {"saved": "saved", "off_target": "just wide", "blocked": "blocked", "post": "off the post"}


def _kai_options(icon: str, s: dict) -> list[str] | None:
    who, team, score = s.get("who") or "a player", s.get("team") or "", s.get("score", "")
    t = s.get("type")
    if icon == "goal":
        if s.get("penalty"):
            return [f"GOAL! {who} sends the keeper the wrong way. {score}!",
                    f"In it goes! {who} scores the penalty for {team}. {score}."]
        return [f"GOAL! {who} scores for {team}! It's {score}.",
                f"It's in! {who} finds the net for {team}. {score}!",
                f"GOAL for {team}! {who} with the finish. {score}."]
    if icon == "chance" and t == "shot":
        outcome = s.get("outcome")
        if not outcome:
            return [f"{who} shoots for {team}…", f"{who} goes for goal for {team}…"]
        result = SHOT_OUTCOME.get(outcome, outcome.replace("_", " "))
        return [f"{who} has a go for {team}… {result}.", f"Chance for {team}! {who}: {result}.",
                f"{who} tries a shot for {team}: {result}."]
    if icon == "penalty":
        return [f"PENALTY to {team}! The referee points to the spot.", f"Penalty! {team} have a big chance here."]
    if icon == "card_yellow":
        return [f"Yellow card: {who} is cautioned ({team}).", f"{who} of {team} gets a yellow.",
                f"The referee shows {who} a yellow card."]
    if icon == "card_red":
        return [f"RED CARD! {who} is off, and {team} are down to {s.get('left')}.",
                f"Sent off! {who} has to go. {team} play on with {s.get('left')}."]
    if icon == "var" and t == "var":
        incident = s.get("incident", "incident")
        if s.get("phase") == "check":
            what = "a possible penalty" if incident == "penalty" else f"the {incident}"
            return [f"Hold on: VAR is checking {what}.", f"VAR is taking a look at {what}. Let's wait."]
        if s.get("phase") == "on_field_review":
            return ["The referee is going over to the monitor…", "Off to the screen goes the referee…"]
        if s.get("outcome") == "overturned" and incident == "penalty":
            return ["VAR says PENALTY! The decision is overturned.", "It's overturned: PENALTY!"]
        what = "the goal stands" if incident == "goal" else "the original call stands"
        return [f"VAR is done: {what}.", f"No change from VAR: {what}."]
    if icon == "sub":
        on, off = s.get("on") or "a sub", s.get("off") or "a player"
        return [f"Change for {team}: {on} comes on for {off}.", f"{off} makes way for {on} ({team}).",
                f"{team} make a change: {on} on, {off} off."]
    if icon == "injury":
        return [f"{who} is down, so play has stopped.", f"Play's stopped: {who} needs treatment."]
    if icon == "clock":
        return [f"The board is up: {s.get('minutes')} minutes added.", f"{s.get('minutes')} more minutes to play."]
    if icon == "whistle" and t == "period_start":
        return (["And we're off!", "Kick-off! Here we go."] if s.get("period") == 1 else
                ["We're back under way for the second half.", "Second half, here we go."])
    if icon == "whistle" and t == "period_end":
        return ([f"That's half-time. {score}.", f"Half-time whistle: {score}."] if s.get("period") == 1 else
                [f"FULL-TIME! {score}.", f"That's it, it's all over: {score}."])
    if icon == "big_chance":
        xg = s.get("xg")
        return [f"That's a big chance gone for {who}: {xg} xG.",
                f"Big chance missed. That one was worth {xg} xG for {who}.",
                f"Big chance for {who}, but it stays out: {xg} xG."]
    if icon == "milestone":
        n = s.get("n")
        if s.get("stat") == "key_passes":
            return [f"{who} has now set up {n} shots for {team}: {n} key passes.",
                    f"{who} set up that shot: {n} key passes so far."]
        return [f"That's {n} shots for {who} now.", f"{who} keeps trying: {n} shots so far.",
                f"{n} attempts now from {who}."]
    if icon == "momentum":
        return [f"{team} are on top right now.", f"This spell belongs to {team}.",
                f"{team} have the upper hand at the moment."]
    return None


def chat_line(item: dict, depth: str) -> str:
    """What the chat shows for an engine feed item. Basic depth gets the human voice; deep keeps
    the engine's precise wording. Anything without a phrasing keeps the engine text."""
    if depth != "basic" or not item.get("say"):
        return item["text"][depth]
    options = _kai_options(item["icon"], item["say"])
    return _pick(item["cue_id"], options) if options else item["text"][depth]


def kai_followup(cue_id: str, factpack: dict) -> dict | None:
    """Kai's closing turn after Ada's analysis, from facts in the same pack, or None."""
    moment = factpack.get("moment")
    crowd = next((f for f in factpack.get("facts", []) if f.get("type") == "crowd_reaction"), None)
    left = factpack.get("minutes_left")
    if crowd and moment in ("goal", "var_decision"):
        text = _pick(cue_id, ["And the noise level jumped the second it happened.",
                              "You could see it on the crowd meter: right up, straight away.",
                              "The crowd got a lot louder the moment it happened."])
        return {"text": text, "evidence": [crowd["id"]]}
    if crowd and moment == "var_check":
        return {"text": "The crowd got noticeably louder straight after that challenge.", "evidence": [crowd["id"]]}
    if moment == "goal" and left:
        return {"text": _pick(cue_id, [f"{left} minutes still to play.", f"Still {left} minutes left in this one."]),
                "evidence": ["state"]}
    if moment == "half_time":
        return {"text": "Back with you for the second half.", "evidence": ["state"]}
    if moment == "full_time":
        return {"text": "That's full-time from us. Thanks for watching with Kai and Ada.", "evidence": ["state"]}
    return None
