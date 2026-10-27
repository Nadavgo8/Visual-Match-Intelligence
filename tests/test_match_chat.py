"""The unified match chat: Kai (commentator) and Ada (analyst) in one conversation.

The engine names the speaker of every item and links replies. Replies come only from fixed
engine rules, so the two voices can never set each other off in a loop.
"""

import asyncio
from types import SimpleNamespace

import pytest

from vmi.agents.qa import speaker_for
from vmi.api.server import Room
from vmi.engine.attention import BIG_CHANCE_XG, MILESTONES, MOMENTUM_REPLY_S, AttentionEngine
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
            if o["kind"] == "feed":  # the only feed replies: a goal to Ada's momentum call, or a shot follow-up
                target = seen[r]
                assert (o["icon"], target["speaker"]) == ("goal", "analyst") or (
                    o["icon"] in ("big_chance", "milestone") and target.get("shot_id")), (o["icon"], target["icon"])
        seen.setdefault(o["cue_id"], o)
    for o in outs:  # depth: follow reply_to links; no chain is longer than two hops
        hops, cur = 0, o
        while cur.get("reply_to"):
            cur, hops = seen[cur["reply_to"]], hops + 1
            assert hops <= 2


def test_ada_speaks_for_interpretation_and_kai_for_everything_else_from_the_feed(played):
    _, outs = played
    for o in (o for o in outs if o["kind"] == "feed"):
        assert o["speaker"] == ("analyst" if o["icon"] in ("momentum", "big_chance") else "commentator")


def test_every_missed_big_chance_is_called_once_and_nothing_below_the_threshold(played):
    _, outs = played
    final = {}
    for o in (o for o in outs if o["kind"] == "feed" and o.get("shot_id")):
        final[o["shot_id"]] = o
    expected = {sid for sid, o in final.items() if o.get("xg") is not None and o["xg"] >= BIG_CHANCE_XG
                and not o["text"]["basic"].startswith("GOAL") and "result pending" not in o["text"]["basic"]}
    called = [o["evidence"][0] for o in outs if o["kind"] == "feed" and o["icon"] == "big_chance"]
    assert sorted(called) == sorted(expected)
    assert expected, "the fixture match should contain at least one missed big chance"


def test_player_milestones_are_said_once_at_three_and_five_only(played):
    _, outs = played
    marks = [(o["say"]["who"], o["say"]["stat"], o["say"]["n"]) for o in outs
             if o["kind"] == "feed" and o["icon"] == "milestone"]
    assert marks and len(marks) == len(set(marks))
    assert {n for _, _, n in marks} <= set(MILESTONES)
    for o in (o for o in outs if o["kind"] == "feed" and o["icon"] == "milestone"):
        assert o["reply_to"] and str(o["say"]["n"]) in o["text"]["basic"]


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


def test_a_new_room_plays_a_random_match_unless_a_seed_or_demo_mode_is_set(monkeypatch):
    from vmi.api import server

    monkeypatch.delenv("VMI_DEMO", raising=False)
    monkeypatch.setattr(server.random, "randint", lambda lo, hi: (lo, hi))
    assert server.new_room_seed(None) == (1, server.MAX_SEED)
    assert server.new_room_seed(7) == 7
    monkeypatch.setenv("VMI_DEMO", "1")
    assert server.new_room_seed(None) == server.DEMO_SEED
    assert server.new_room_seed(7) == 7


def test_the_tv_learns_which_seed_is_the_demo_match():
    from vmi.api import server

    assert Room("demo-seed-state", 12).state("tv")["demo_seed"] == server.DEMO_SEED
