"""Kai and Ada sound human but stay grounded: wording is code, facts come from the engine."""

import re

import pytest

from vmi.agents.explainer import CROWD_CAUSAL, template
from vmi.agents.voices import chat_line, kai_followup
from vmi.engine.replay import run_all
from vmi.generator.match import generate_match


@pytest.fixture(scope="module", params=[2, 12])
def outs(request):
    return [o for o in run_all(generate_match(request.param)) if o["kind"] in ("feed", "analysis")]


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def test_kai_lines_only_use_numbers_and_names_the_engine_supplied(outs):
    for o in (o for o in outs if o["kind"] == "feed"):
        line = chat_line(o, "basic")
        allowed = " ".join(str(v) for v in o["say"].values()) + " " + o["text"]["basic"] + " " + o["text"]["deep"]
        assert _numbers(line) <= _numbers(allowed), line
        if o["say"].get("who") and o["icon"] in ("goal", "card_yellow", "card_red", "injury"):
            assert o["say"]["who"] in line, line
        assert not CROWD_CAUSAL.search(line), line


def test_the_same_item_always_reads_the_same_and_phrasing_varies_across_items(outs):
    feed = [o for o in outs if o["kind"] == "feed"]
    assert all(chat_line(o, "basic") == chat_line(o, "basic") for o in feed)
    subs = {chat_line(o, "basic").split(":")[0].split(" ")[0] for o in feed if o["icon"] == "sub"}
    if sum(o["icon"] == "sub" for o in feed) >= 4:
        assert len(subs) >= 2, "four substitutions should not all open the same way"


def test_deep_depth_and_items_without_facts_keep_the_engine_wording():
    item = {"cue_id": "cue_1", "icon": "goal", "text": {"basic": "GOAL! X scores.", "deep": "Goal: X, xG 0.3."},
            "say": {"type": "shot", "who": "X", "team": "Home", "score": "Home 1–0 Away", "outcome": "goal"}}
    assert chat_line(item, "deep") == "Goal: X, xG 0.3."
    assert "X" in chat_line(item, "basic") and "Home 1–0 Away" in chat_line(item, "basic")
    assert chat_line({**item, "say": None}, "basic") == "GOAL! X scores."
    assert chat_line({**item, "icon": "unknown"}, "basic") == "GOAL! X scores."


@pytest.mark.parametrize("pack, expected", [
    ({"moment": "goal", "facts": [{"type": "crowd_reaction", "id": "crowd@9"}], "minutes_left": 30}, ["crowd@9"]),
    ({"moment": "goal", "facts": [], "minutes_left": 30}, ["state"]),
    ({"moment": "goal", "facts": [], "minutes_left": 0}, None),
    ({"moment": "var_check", "facts": [{"type": "crowd_reaction", "id": "crowd@3"}]}, ["crowd@3"]),
    ({"moment": "injury", "facts": [{"type": "crowd_reaction", "id": "crowd@4"}]}, None),
    ({"moment": "substitution", "facts": []}, None),
    ({"moment": "half_time", "facts": []}, ["state"]),
    ({"moment": "full_time", "facts": []}, ["state"]),
])
def test_kai_closes_an_analysis_only_with_a_fact_from_its_pack(pack, expected):
    f = kai_followup("cue_7", pack)
    assert (f["evidence"] if f else None) == expected
    if f and pack.get("minutes_left"):
        assert _numbers(f["text"]) <= {str(pack["minutes_left"])}


def test_ada_reacts_to_the_goal_instead_of_announcing_it_again_and_leaves_the_crowd_to_kai(outs):
    goals = [o for o in outs if o["kind"] == "analysis" and o["moment"] == "goal"]
    assert goals
    for a in goals:
        text = " ".join(s["s"] for s in template(a["factpack"], "basic"))
        assert not text.lower().startswith("goal"), text
        assert "louder" not in text and "crowd" not in text, text


@pytest.fixture(scope="module")
def finished():
    from vmi.engine.replay import Replay

    m = generate_match(2)
    r = Replay(m)
    r.advance(m.duration)
    return r.model


def test_leaders_count_each_players_delivered_shots_and_key_passes(finished):
    from vmi.agents.tools import MatchTools

    shots: dict[str, int] = {}
    kps: dict[str, int] = {}
    for e in finished.events:  # counted independently from the raw delivered events
        if e["type"] == "shot" and e["shot"].get("outcome") != "disallowed":
            name = finished.player_name(e["player_id"])
            shots[name] = shots.get(name, 0) + 1
        if e["type"] == "pass" and e["derived"].get("key_pass"):
            name = finished.player_name(e["player_id"])
            kps[name] = kps.get(name, 0) + 1
    r = MatchTools(finished).get_leaders()
    assert r["leaders"]["shots"][0]["value"] == max(shots.values())
    assert r["leaders"]["key_passes"][0]["value"] == max(kps.values())
    assert all(shots[p["name"]] == p["value"] for p in r["leaders"]["shots"])
    assert all(kps[p["name"]] == p["value"] for p in r["leaders"]["key_passes"])
    assert set(MatchTools(finished).get_leaders("fouls")["leaders"]) == {"fouls"}
    assert r["evidence"]


@pytest.mark.parametrize("question, category", [
    ("who had the most key passes? as in a player", "key passes"),
    ("who has the most shots?", "shots"),
    ("who leads in xG?", "xG"),
    ("top scorer?", "goals"),
])
def test_who_leads_questions_get_a_player_answer_without_the_model(finished, question, category):
    from vmi.agents.qa import Assistant

    res = Assistant(finished)._local(question, {})
    assert res["tool_calls"] == ["get_leaders"] and category in res["text"], res["text"]
    assert "(#" in res["text"] and "can't" not in res["text"]


def test_a_tie_for_the_lead_is_shared_not_given_to_one_player(finished):
    from vmi.agents.qa import Assistant

    text = Assistant(finished)._local("top scorer?", {})["text"]
    assert "share the lead for goals, with 1 each" in text  # three scorers on one goal each in the demo match


def test_half_time_report_names_clear_leaders_and_passes_the_validator():
    from vmi.agents.explainer import validate

    m = generate_match(2)
    roster = {p["name"] for t in m.meta["teams"].values() for p in t["players"]}
    for o in run_all(m):
        if o["kind"] == "analysis" and o["moment"] in ("half_time", "full_time"):
            sents = template(o["factpack"], "basic")
            assert validate(sents, o["factpack"], roster) == []
            assert any(s["s"].startswith("Top players:") for s in sents)
            assert "synthetic" not in " ".join(s["s"] for s in sents).lower()


def test_no_chat_text_or_model_fact_pack_mentions_the_xg_method(outs):
    for o in outs:
        if o["kind"] == "feed":
            for depth in ("basic", "deep"):
                assert "geometry" not in chat_line(o, depth) and "synthetic" not in chat_line(o, depth).lower()
        else:
            assert "method_version" not in str(o["factpack"]) and "geometry" not in str(o["factpack"])


def _period_pack(moment="half_time", home=None, away=None, goals=(), mom=None, leaders=None):
    base = {"shots": 5, "shots_on_target": 2, "xg": 0.8, "possession": 0.5}
    facts = [{"id": "stat:match", "type": "match_stats", "home": {**base, **(home or {})}, "away": {**base, **(away or {})}}]
    facts += list(goals)
    if leaders:
        facts.append({"id": "stat:leaders", "type": "player_leaders", **leaders})
    deep = [{"id": "stat:momentum", "type": "momentum_last_7_min", **mom}] if mom else []
    return {"moment": moment, "teams": {"home": "Home FC", "away": "Away Town"}, "score": {"home": 0, "away": 0},
            "minutes_left": 45, "facts": facts, "deep_context": deep, "context": {}}


def test_a_level_goalless_half_reports_equal_shots_and_who_finished_stronger():
    pack = _period_pack(mom={"home_share_pct": 40, "away_share_pct": 60})
    text = " ".join(s["s"] for s in template(pack, "basic"))
    assert "Half-time: Home FC 0–0 Away Town, no goals yet." in text
    assert "Both sides had 5 shots; Home FC put 2 on target, Away Town 2." in text
    assert "Possession was close: Home FC 50%, Away Town 50%." in text
    assert "Away Town finished the half stronger, with 60% of the momentum" in text
    assert "better chances" not in text  # equal xG names nobody


def test_full_time_report_without_xg_or_momentum_and_a_one_sided_possession():
    pack = _period_pack("full_time", home={"xg": None, "possession": 0.7, "shots": 9},
                        away={"possession": 0.3, "shots": 3, "shots_on_target": 1})
    sents = template(pack, "deep")
    text = " ".join(s["s"] for s in sents)
    assert "Full-time: Home FC 0–0 Away Town, no goals in this one." in text
    assert "Home FC took more shots, 9 to 3, with 2 on target against 1 for Away Town." in text
    assert "Possession: Home FC 70%, Away Town 30%." in text
    assert "xG" not in text and "momentum" not in text
    assert len(sents) <= 6


def test_a_goal_without_an_assist_is_described_by_how_it_went_in_or_left_to_the_score():
    from vmi.agents.explainer import _t_goal

    def pack(**goal):
        g = {"id": "g1", "type": "goal", "team": "Home FC", "scorer": {"name": "Ola", "position": "ST"},
             "penalty": False, **goal}
        return {"moment": "goal", "teams": {"home": "Home FC", "away": "Away Town"}, "score": {"home": 1, "away": 0},
                "minutes_left": 30, "facts": [g], "deep_context": [], "context": {"scoring_team_now": "leading"}}
    assert _t_goal(pack(body_part="head"), "basic", None)[0]["s"] == "Ola did it with a header."
    plain = _t_goal(pack(), "basic", None)
    assert len(plain) == 1 and plain[0]["s"].startswith("That puts Home FC ahead")
