"""Run the D2-00 question set against one model candidate and write a review report.

    python -m vmi.evaluation.model_eval --provider template --runs 2
    python -m vmi.evaluation.model_eval --provider local --model phi4-mini --runs 2

`template` is the deterministic baseline; its answers never count as model answers.
`local` talks to an OpenAI-compatible runtime on this machine (for example Ollama);
remote endpoints are refused until D2-00 has verified a provider's zero-cost terms.

Automated flags (numbers or names missing from the snapshot, future scores or
players, crowd motives) are review aids. Whether an answer is useful and grounded is
decided by both developers in the review sheet; this tool never reports a PASS.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..agents.explainer import CROWD_CAUSAL, _num, _pack_numbers, _pack_strings
from ..agents.providers import TOTAL_TIMEOUT_S, CostRiskError, ModelRequest, generate
from ..agents.qa import Assistant
from ..agents.tools import MatchTools
from ..engine.replay import Replay
from ..generator.match import generate_match
from .question_set import ITEMS, SEED, Item
from .benchmark import benchmark_match

PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "model_eval.md").read_text(encoding="utf-8")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


# ------------------------------------------------------------------ snapshots
def _score(s: dict) -> str:
    return f"{s['home']}-{s['away']}"


def _future(match, t: float, pack_blob: str, roster: dict[str, str]) -> dict:
    """Scores and player names that only become true after t, for leak detection."""
    scores, names, goals = set(), set(), {}
    running = {"home": 0, "away": 0}
    current = _score(running)
    for e in sorted(match.events, key=lambda e: e["t"]):
        changed = False
        if e["type"] == "shot_result" and e.get("outcome") == "goal" and e["id"] not in goals:
            goals[e["id"]] = e["team"]
            running[e["team"]] += 1
            changed = True
        if e["type"] == "goal_cancelled" and e.get("result_id") in goals:
            running[goals.pop(e["result_id"])] -= 1
            changed = True
        if changed and e["t"] > t:
            scores.add(_score(running))
        if e["t"] <= t:
            current = _score(running)
        if e["t"] > t and e["type"] in {"shot_result", "card", "substitution"}:
            ids = [e.get("player_id")]
            if e["type"] == "substitution":
                ids += [e["substitution"].get("on_id"), e["substitution"].get("off_id")]
            for pid in ids:
                name = roster.get(pid)
                if name and name.lower() not in pack_blob:
                    names.add(name)
    return {"scores": sorted(scores - {current}), "names": sorted(names)}


def _pack(model, item: Item) -> dict:
    tools = MatchTools(model)
    events = tools.get_events()
    if item.window_s is not None:
        start = item.snapshot_t - item.window_s
        events = {"events": [e for e in events["events"] if model.by_id[e["id"]]["t"] >= start]}
        events["evidence"] = [e["id"] for e in events["events"]]
        events["window"] = {"from_clock_s": round(max(start, 0)), "to_clock_s": round(item.snapshot_t)}
    pack = {"question_category": item.category, "score_and_clock": tools.get_score_and_clock(),
            "events": events, "team_stats": tools.get_team_stats(), "momentum": tools.get_momentum(),
            "crowd": tools.get_crowd_peaks()}
    if item.rule_topic:
        pack["rule"] = tools.get_rule(item.rule_topic)
    return json.loads(json.dumps(pack))  # frozen copy: later ingestion can't change it


async def build_snapshots(items=ITEMS, seed: int = SEED):
    """Replay once in time order; freeze a pack, future facts and a template answer per item."""
    match = benchmark_match() if seed == SEED else generate_match(seed)
    roster = {p["id"]: p["name"] for side in match.meta["teams"].values() for p in side["players"]}
    replay = Replay(match)
    packs, futures, templates, delivered = {}, {}, {}, {}
    for item in sorted(items, key=lambda i: i.snapshot_t):
        replay.advance(item.snapshot_t)
        model = replay.model
        pack = _pack(model, item)
        blob: list[str] = []
        _pack_strings(pack, blob)
        packs[item.id] = pack
        futures[item.id] = _future(match, item.snapshot_t, " ".join(blob), roster)
        local = await Assistant(model).answer(item.question, item.profile)
        templates[item.id] = (local["text"], list(local.get("evidence") or []))
        delivered[item.id] = {e["id"]: e["delivered_t"] for e in model.events}
    return packs, futures, templates, delivered, set(roster.values())


def build_prompt(item: Item, pack: dict) -> str:
    return json.dumps({"question": item.question, "snapshot": pack}, ensure_ascii=False)


# ------------------------------------------------------------------ scoring
def score_answer(item: Item, pack: dict, text: str, future: dict, roster: set[str]) -> dict:
    flags = []
    allowed: set[str] = set()
    _pack_numbers(pack, allowed)
    _pack_numbers(item.question, allowed)
    for n in NUMBER.findall(text):
        if _num(float(n)) not in allowed:
            flags.append(f"number {n} not in snapshot")
    strings: list[str] = []
    _pack_strings(pack, strings)
    blob = " ".join(strings) + " " + item.question.lower()
    for name in sorted(roster):
        if re.search(rf"\b{re.escape(name)}\b", text) and name.lower() not in blob:
            flags.append(f"name {name} not in snapshot")
    for s in future["scores"]:
        h, a = s.split("-")
        if re.search(rf"\b{h}\s*[-–:]\s*{a}\b", text):
            flags.append(f"future score {s}")
    for name in future["names"]:
        if re.search(rf"\b{re.escape(name)}\b", text):
            flags.append(f"future player {name}")
    if re.search(r"\b(crowd|stadium|fans|supporters)\b", text, re.I) and CROWD_CAUSAL.search(text):
        flags.append("possible crowd motive")
    hits = sum(1 for w in item.expect if w.lower() in text.lower())
    return {"flags": flags, "expect_hits": f"{hits}/{len(item.expect)}" if item.expect else "n/a"}


# ------------------------------------------------------------------ candidates
def parse_answer(content: str) -> tuple[str, list[str]]:
    """Read {"answer", "evidence"} JSON from a model reply; fall back to the raw text."""
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(content[start:end + 1])
            if isinstance(data.get("answer"), str):
                ev = data.get("evidence") or []
                return data["answer"].strip(), [str(x) for x in ev] if isinstance(ev, list) else []
        except json.JSONDecodeError:
            pass
    return content.strip(), []


class LocalOpenAICompatible:
    """A model served on this machine through an OpenAI-compatible API (e.g. Ollama)."""

    name = "local-openai-compatible"
    may_charge = False

    def __init__(self, base_url: str, model: str, transport: httpx.AsyncBaseTransport | None = None):
        if urlparse(base_url).hostname not in LOCAL_HOSTS:
            raise CostRiskError("only a runtime on this machine can be evaluated before D2-00 verifies "
                                "a remote provider's zero-cost terms")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport

    async def complete(self, request: ModelRequest) -> tuple[str, list[str]]:
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": request.prompt}]}
        async with httpx.AsyncClient(timeout=request.timeout_s, transport=self.transport) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=body)
            resp.raise_for_status()
            return parse_answer(resp.json()["choices"][0]["message"]["content"])


# ------------------------------------------------------------------ runner
def _p(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


async def run(provider, runs: int = 2, items=ITEMS, snapshots=None, clock=time.perf_counter) -> dict:
    packs, futures, templates, _, roster = snapshots or await build_snapshots(items)
    rows = []
    for run_no in range(1, runs + 1):
        for item in items:
            req = ModelRequest(kind="summary" if item.category == "summary" else "answer",
                               prompt=build_prompt(item, packs[item.id]), snapshot=packs[item.id],
                               snapshot_t=item.snapshot_t, profile=item.profile)
            res = await generate(provider, req, lambda _r, i=item: templates[i.id], clock=clock)
            scored = score_answer(item, packs[item.id], res.text, futures[item.id], roster)
            rows.append({"id": item.id, "run": run_no, "category": item.category, "question": item.question,
                         "answer": res.text, "evidence": res.evidence, "answer_kind": res.answer_kind,
                         "status": res.status, "error": res.error, "latency_ms": res.latency_ms,
                         "first_request": not rows, "trap": item.trap, **scored})
    return {"provider": getattr(provider, "name", None), "model": getattr(provider, "model", None),
            "runs": runs, "rows": rows, "summary": summarise(rows)}


def summarise(rows: list[dict]) -> dict:
    live = [r for r in rows if r["answer_kind"] == "live"]
    warm = [r for r in rows if not r["first_request"]]
    warm_live_ms = [r["latency_ms"] for r in warm if r["answer_kind"] == "live"]
    limit_ms = TOTAL_TIMEOUT_S * 1000
    errors: dict[str, int] = {}
    for r in rows:
        if r["error"]:
            errors[r["error"]] = errors.get(r["error"], 0) + 1
    flagged = [r for r in live if r["flags"]]
    return {
        "requests": len(rows), "model_answers": len(live), "template_fallbacks": len(rows) - len(live),
        "fallback_reasons": errors,
        "first_request_ms": rows[0]["latency_ms"] if rows else None,
        "warm_p50_ms": _p(warm_live_ms, 0.5), "warm_p95_ms": _p(warm_live_ms, 0.95),
        "warm_within_20s": (f"{sum(1 for r in warm if r['answer_kind'] == 'live' and r['latency_ms'] <= limit_ms)}"
                            f"/{len(warm)}"),
        "model_answers_with_flags": len(flagged),
        "useful_and_grounded": "PENDING_REVIEW_BY_BOTH_DEVELOPERS",
        "verdict": ("BASELINE_ONLY: template answers are not model answers" if not live
                    else "NOT_DECIDED: needs the review sheet from both developers"),
    }


def write_report(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "review.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "run", "category", "question", "answer", "answer_kind", "latency_ms", "flags",
                    "trap_expectation", "useful (Y/N)", "grounded (Y/N)", "reviewer"])
        for r in report["rows"]:
            w.writerow([r["id"], r["run"], r["category"], r["question"], r["answer"], r["answer_kind"],
                        r["latency_ms"], "; ".join(r["flags"]), r["trap"] or "", "", "", ""])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--provider", choices=["template", "local"], default="template")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--model", default=None)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--output", type=Path, default=Path("out/model-eval"))
    args = ap.parse_args(argv)
    provider = None
    if args.provider == "local":
        if not args.model:
            ap.error("--model is required for --provider local")
        provider = LocalOpenAICompatible(args.base_url, args.model)
    report = asyncio.run(run(provider, runs=args.runs))
    out = args.output / (args.model or "template")
    write_report(report, out)
    print(json.dumps(report["summary"], indent=2))
    print(f"review sheet: {out / 'review.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
