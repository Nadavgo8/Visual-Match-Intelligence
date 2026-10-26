"""The unified match chat: Kai (commentator) and Ada (analyst) in one conversation.

The engine names the speaker of every item and links replies. Replies come only from fixed
engine rules, so the two voices can never set each other off in a loop.
"""

import asyncio
from types import SimpleNamespace

import pytest

from vmi.agents.qa import speaker_for
from vmi.api.server import Room
from vmi.engine.attention import MOMENTUM_REPLY_S, AttentionEngine
from vmi.engine.replay import run_all
from vmi.generator.match import generate_match

# The commentator item each analysis moment answers.
EXPECTED_TARGET_ICON = {"goal": "goal", "var_check": "var", "var_decision": "var", "substitution": "sub",
                        "injury": "injury", "half_time": "whistle", "full_time": "whistle"}


@pytest.fixture(scope="module", params=[12, 2])
def played(request):
    m = generate_match(request.param)
    outs = [o for o in run_all(m) if o["kind"] in ("feed", "analysis")]
    return m, outs


def test_every_analysis_replies_to_the_commentator_item_for_its_event(played):
    _, outs = played
    feed = {o["cue_id"]: o for o in outs if o["kind"] == "feed"}
    analyses = [o for o in outs if o["kind"] == "analysis"]
    assert analyses
    for a in analyses:
        target = feed.get(a["reply_to"])
        assert target is not None, a["moment"]
        assert target["speaker"] == "commentator"
        assert target["icon"] == EXPECTED_TARGET_ICON[a["moment"]], a["moment"]
        assert target["t"] <= a["t"]
        if a["moment"] in ("half_time", "full_time"):
            assert ("Half-time" if a["moment"] == "half_time" else "Full-time") in target["text"]["basic"]


def test_reply_threads_are_short_point_backwards_and_never_target_an_analysis(played):
    _, outs = played
    seen: dict[str, dict] = {}
    for o in outs:
        r = o.get("reply_to")
        if r is not None:
            assert r in seen, "a reply must point at something already said"
            assert seen[r]["kind"] == "feed", "nothing replies to an analysis, so threads stop there"
            if o["kind"] == "feed":  # only a goal builds on Ada's momentum call
                assert o["icon"] == "goal" and seen[r]["speaker"] == "analyst"
        seen.setdefault(o["cue_id"], o)
    for o in outs:  # depth: follow reply_to links; no chain is longer than two hops
        hops, cur = 0, o
        while cur.get("reply_to"):
            cur, hops = seen[cur["reply_to"]], hops + 1
            assert hops <= 2


def test_only_the_momentum_call_is_ada_everything_else_from_the_feed_is_kai(played):
    _, outs = played
    for o in (o for o in outs if o["kind"] == "feed"):
        assert o["speaker"] == ("analyst" if o["icon"] == "momentum" else "commentator")


def test_a_late_xg_update_keeps_the_reply_link_of_the_original_goal_item(played):
    _, outs = played
    links: dict[str, set] = {}
    for o in (o for o in outs if o["kind"] == "feed"):
        links.setdefault(o["cue_id"], set()).add(o["reply_to"])
    assert all(len(v) == 1 for v in links.values())


@pytest.mark.parametrize("momentum, shot, expected", [
    ({"team": "home", "t": 1000.0, "cue_id": "cue_m"}, {"team": "home", "t": 1000.0 + MOMENTUM_REPLY_S}, "cue_m"),
    ({"team": "home", "t": 1000.0, "cue_id": "cue_m"}, {"team": "home", "t": 1000.0 + MOMENTUM_REPLY_S + 1}, None),
    ({"team": "home", "t": 1000.0, "cue_id": "cue_m"}, {"team": "away", "t": 1100.0}, None),
    ({"team": "home", "t": 1000.0, "cue_id": "cue_m"}, {"team": "home", "t": 999.0}, None),
    (None, {"team": "home", "t": 1100.0}, None),
])
def test_a_goal_builds_on_the_momentum_call_only_for_the_same_team_within_ten_minutes(momentum, shot, expected):
    assert AttentionEngine._momentum_reply(SimpleNamespace(last_momentum=momentum), shot) == expected


@pytest.mark.parametrize("question, agent, speaker", [
    ("Who scored the second goal?", "match_analyst", "commentator"),
    ("What happened in the 65th minute?", "match_analyst", "commentator"),
    ("What's the score?", None, "commentator"),
    ("Why is Harbour City dominating possession?", "match_analyst", "analyst"),
    ("Which team looks more dangerous?", "router", "analyst"),
    ("What changed after the substitution?", "match_analyst", "analyst"),
    ("Who's on top?", "match_analyst", "analyst"),
    ("Was that offside?", "rules_expert", "analyst"),
    ("Tell me about number 9", "meaning_analyst", "analyst"),
])
def test_questions_go_to_kai_for_what_happened_and_ada_for_what_it_means(question, agent, speaker):
    assert speaker_for(question, agent) == speaker


def test_server_messages_carry_the_speaker_and_reply_link():
    room = Room("chat-speaker-test", 12)
    profile = {"depth": "basic", "team": None, "amount": "everything"}
    item = {"cue_id": "cue_9", "clock": "12:00", "t": 720.0, "icon": "goal", "team": "home", "text": {"basic": "GOAL!"},
            "evidence": ["e1"], "tier": 1, "delivered": 720.0, "speaker": "commentator", "reply_to": "cue_3"}
    msg = room.feed_msg(item, profile)
    assert (msg["speaker"], msg["reply_to"]) == ("commentator", "cue_3")
    legacy = {k: v for k, v in item.items() if k not in ("speaker", "reply_to")}
    assert (room.feed_msg(legacy, profile)["speaker"], room.feed_msg(legacy, profile)["reply_to"]) == ("commentator", None)

    sent = []
    client = SimpleNamespace(role="app", profile=profile)
    room.clients = [client]

    async def capture(c, m):
        sent.append(m)
    room.send = capture
    analysis = {"kind": "analysis", "cue_id": "cue_10", "clock": "12:08", "t": 728.0, "moment": "goal", "tier": 1, "reply_to": "cue_9",
                "factpack": {"facts": []}}
    key = ("cue_10", "basic", None)
    room.texts[key] = {"text": "Ada's view.", "sentences": [], "source": "template", "model": None,
                       "latency_ms": 0, "validation": "passed"}
    asyncio.run(room.push_analysis(analysis, key, room.run))
    assert [(m["speaker"], m["reply_to"]) for m in sent] == [("analyst", "cue_9")]
