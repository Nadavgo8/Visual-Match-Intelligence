"""The D2-00 question set and runner: delivered-only snapshots, leak flags, honest summaries."""

import asyncio
import csv
import json
from collections import Counter
from types import SimpleNamespace

import httpx
import pytest

from vmi.agents.providers import CostRiskError, ModelRequest
from vmi.evaluation import model_eval as me
from vmi.evaluation import benchmark
from vmi.evaluation.question_set import CATEGORIES, ITEMS, Item


@pytest.fixture(scope="module")
def snapshots():
    return asyncio.run(me.build_snapshots())


def test_question_set_is_30_unique_english_items_in_the_planned_mix():
    assert len(ITEMS) == 30
    assert len({i.id for i in ITEMS}) == 30
    assert Counter(i.category for i in ITEMS) == CATEGORIES
    assert all(i.question.isascii() and i.question.rstrip().endswith(("?", ".")) for i in ITEMS)
    assert all(i.trap for i in ITEMS if i.category == "trap")


def test_annotated_benchmark_is_pinned_and_each_load_is_independent():
    match = benchmark.benchmark_match()
    assert match.meta["generator_version"] == "2.2.0"
    assert match.meta["final_score"] == {"home": 2, "away": 1}
    assert len(match.events) == 2431 and match.keyframes
    match.events[0]["type"] = "corrupted-by-caller"
    assert benchmark.benchmark_match().events[0]["type"] != "corrupted-by-caller"


def test_corrupt_benchmark_fails_before_replay(monkeypatch, tmp_path):
    damaged = tmp_path / "benchmark.gz"
    damaged.write_bytes(b"not the annotated benchmark")
    monkeypatch.setattr(benchmark, "FIXTURE", damaged)
    with pytest.raises(ValueError, match="checksum"):
        benchmark.benchmark_match()


def test_custom_evaluation_seed_remains_explicit(monkeypatch):
    calls = []
    def custom(seed):
        calls.append(seed)
        return benchmark.benchmark_match()
    monkeypatch.setattr(me, "generate_match", custom)
    packs, futures, templates, delivered, roster = asyncio.run(me.build_snapshots(items=(), seed=99))
    assert calls == [99] and roster
    assert packs == futures == templates == delivered == {}


def test_every_pack_event_was_delivered_by_the_snapshot_time(snapshots):
    packs = snapshots[0]
    truth = {e["id"]: e for e in me.benchmark_match().events}
    for item in ITEMS:
        ids = packs[item.id]["events"]["evidence"]
        assert ids, item.id
        late = [i for i in ids if truth[i]["delivered_t"] > item.snapshot_t]
        assert not late, (item.id, late)


def test_future_scores_and_players_are_known_but_absent_from_the_pack(snapshots):
    packs, futures = snapshots[0], snapshots[1]
    assert futures["T01"]["scores"] == ["1-1", "2-1"]  # asked at 1-0
    assert futures["F09"]["scores"] == []  # asked after the last goal
    for item in ITEMS:
        text = json.dumps(packs[item.id]).lower()
        for name in futures[item.id]["names"]:
            assert name.lower() not in text, (item.id, name)


def test_future_score_truth_accounts_for_a_cancelled_goal_before_the_snapshot():
    events = [
        {"id": "g1", "type": "shot_result", "outcome": "goal", "t": 10, "team": "home"},
        {"id": "c1", "type": "goal_cancelled", "result_id": "g1", "t": 20, "team": "home"},
        {"id": "c2", "type": "goal_cancelled", "result_id": "g1", "t": 21, "team": "home"},
        {"id": "g2", "type": "shot_result", "outcome": "goal", "t": 30, "team": "away"},
    ]
    future = me._future(SimpleNamespace(events=events), 25, "", {})
    assert future["scores"] == ["0-1"]


def test_summary_packs_only_cover_their_window(snapshots):
    packs = snapshots[0]
    truth = {e["id"]: e for e in me.benchmark_match().events}
    y02 = next(i for i in ITEMS if i.id == "Y02")
    assert all(truth[i]["t"] >= y02.snapshot_t - y02.window_s for i in packs["Y02"]["events"]["evidence"])


PACK = {"score_and_clock": {"home": "Harbour City", "away": "Northvale Rovers", "score": {"home": 1, "away": 0},
                            "clock": "24:59"}, "events": {"events": [{"id": "e1", "what": "Reyes goal at 18:22"}]}}
ITEM = Item("X1", "fact", "Who scored in the last 10 minutes?", 1500.0, ("Reyes",))
FUTURE = {"scores": ["1-1", "2-1"], "names": ["Novak"]}
ROSTER = {"Reyes", "Novak", "Marsh"}


def test_scorer_accepts_a_grounded_answer():
    s = me.score_answer(ITEM, PACK, "Reyes scored at 18:22, so it's 1-0.", FUTURE, ROSTER)
    assert s == {"flags": [], "expect_hits": "1/1"}


@pytest.mark.parametrize("text,flag", [
    ("Harbour City have had 9 shots.", "number 9 not in snapshot"),
    ("Marsh will equalise.", "name Marsh not in snapshot"),
    ("It ends 2–1.", "future score 2-1"),
    ("Novak comes on later.", "future player Novak"),
    ("The crowd booed because of the decision.", "possible crowd motive"),
])
def test_scorer_flags_invented_numbers_names_future_facts_and_crowd_motives(text, flag):
    assert flag in me.score_answer(ITEM, PACK, text, FUTURE, ROSTER)["flags"]


class Scripted:
    name, model, may_charge = "scripted", "scripted-1", False

    async def complete(self, req):
        return "Reyes scored, it's 1-0.", ["e1"]


def test_run_counts_model_answers_and_separates_the_first_request(snapshots):
    ticks = iter([0.0, 5.0] + [10.0 + i * 0.5 for i in range(200)])
    report = asyncio.run(me.run(Scripted(), runs=2, snapshots=snapshots, clock=lambda: next(ticks)))
    s = report["summary"]
    assert s["requests"] == 60 and s["model_answers"] == 60 and s["template_fallbacks"] == 0
    assert s["first_request_ms"] == 5000
    assert s["warm_p95_ms"] == 500 and s["warm_within_20s"] == "59/59"
    assert s["useful_and_grounded"] == "PENDING_REVIEW_BY_BOTH_DEVELOPERS"
    assert s["verdict"].startswith("NOT_DECIDED")
    assert [r["first_request"] for r in report["rows"]].count(True) == 1


def test_template_baseline_never_counts_as_model_answers(snapshots, tmp_path):
    report = asyncio.run(me.run(None, runs=1, snapshots=snapshots))
    s = report["summary"]
    assert s["model_answers"] == 0 and s["fallback_reasons"] == {"unavailable": 30}
    assert s["verdict"].startswith("BASELINE_ONLY")
    me.write_report(report, tmp_path)
    with (tmp_path / "review.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 30
    assert all(r["useful (Y/N)"] == r["grounded (Y/N)"] == r["reviewer"] == "" for r in rows)


def test_local_adapter_refuses_remote_hosts():
    with pytest.raises(CostRiskError):
        me.LocalOpenAICompatible("https://api.example.com/v1", "some-model")


def test_local_adapter_sends_the_eval_prompt_and_reads_json_replies():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        content = 'Sure: {"answer": "It is 1-0.", "evidence": ["state"]}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    adapter = me.LocalOpenAICompatible("http://localhost:11434/v1", "phi4-mini", transport=httpx.MockTransport(handler))
    req = ModelRequest(kind="answer", prompt='{"question": "Score?"}', snapshot={}, snapshot_t=1.0)
    assert asyncio.run(adapter.complete(req)) == ("It is 1-0.", ["state"])
    assert seen["model"] == "phi4-mini" and seen["temperature"] == 0
    assert seen["messages"][0]["content"] == me.PROMPT


def test_parse_answer_keeps_raw_text_when_the_reply_is_not_json():
    assert me.parse_answer("  It is 1-0.  ") == ("It is 1-0.", [])
    assert me.parse_answer('{"answer": 3}') == ('{"answer": 3}', [])


SUB_ON = {"subscriptionPolicies": {"spendingLimit": "On"}}


@pytest.mark.parametrize("sub,expected", [
    (SUB_ON, True),
    ({"subscriptionPolicies": {"spendingLimit": "Off"}}, False),
    ({"subscriptionPolicies": {"spendingLimit": "CurrentPeriodOff"}}, False),
    ({}, False),
    (None, False),
])
def test_spending_limit_must_be_reported_on(sub, expected):
    assert me.spending_limit_on(lambda: sub) is expected


def test_spending_limit_lookup_failure_counts_as_a_cost_risk():
    def broken():
        raise RuntimeError("az not logged in")
    assert me.spending_limit_on(broken) is False


def test_foundry_candidate_refuses_a_subscription_that_could_charge():
    made = []
    with pytest.raises(CostRiskError):
        me.FoundryCandidate("https://x.services.ai.azure.com/api/projects/p", "gpt-5-mini",
                            read_subscription=lambda: {"subscriptionPolicies": {"spendingLimit": "Off"}},
                            client_factory=lambda e, m: made.append((e, m)))
    assert made == []  # no client is even created


def test_foundry_candidate_with_the_limit_on_is_a_zero_cost_provider():
    c = me.FoundryCandidate("https://x.services.ai.azure.com/api/projects/p", "gpt-5-mini",
                            read_subscription=lambda: SUB_ON, client_factory=lambda e, m: ("client", e, m))
    assert c.may_charge is False and c.model == "gpt-5-mini" and c.name == "microsoft-foundry"
    assert c._client == ("client", "https://x.services.ai.azure.com/api/projects/p", "gpt-5-mini")

