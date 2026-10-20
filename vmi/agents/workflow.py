"""The stoppage-analysis chain as a Microsoft Agent Framework Workflow.

    AnalysisJob -> [writer] -> Draft -> [validator] --passed--> output
                                              \\--rejected--> [fallback] -> output

- writer: the Foundry Explainer agent when configured, else the template.
- validator: deterministic receipts check (evidence IDs, numbers, names, crowd rule).
- fallback: the deterministic template, so a fan always gets a correct card.
Each step is an executor, so the run shows up step by step in the traces.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from . import explainer as ex


@dataclass
class AnalysisJob:
    pack: dict
    depth: str = "basic"
    fav: str | None = None
    t0: float = field(default_factory=time.perf_counter)


@dataclass
class Draft:
    job: AnalysisJob
    sentences: list[dict]
    source: str  # "agent" | "template"
    model: str | None = None
    rejected: list[str] = field(default_factory=list)


@dataclass
class Rejected:
    job: AnalysisJob
    reasons: list[str]


class Writer(Executor):
    def __init__(self, agent=None):
        super().__init__(id="writer")
        self.agent = agent

    @handler(input=AnalysisJob, output=Draft)
    async def write(self, job: AnalysisJob, ctx: WorkflowContext) -> None:
        if self.agent is None:
            await ctx.send_message(Draft(job, ex.template(job.pack, job.depth, job.fav), "template"))
            return
        try:
            sents, model = await ex.agent_draft(self.agent, job.pack, job.depth, job.fav)
            await ctx.send_message(Draft(job, sents, "agent", model))
        except Exception as e:  # network, quota, content filter, bad JSON
            await ctx.send_message(Draft(job, [], "agent", rejected=[f"agent error: {type(e).__name__}"]))


class Validator(Executor):
    def __init__(self, roster: set[str]):
        super().__init__(id="validator")
        self.roster = roster

    @handler(input=Draft, output=Rejected, workflow_output=dict)
    async def check(self, d: Draft, ctx: WorkflowContext) -> None:
        problems = d.rejected or ex.validate(d.sentences, d.job.pack, self.roster)
        if not problems:
            await ctx.yield_output(_result(d.job, d.sentences, d.source, d.model, []))
        elif d.source == "agent":
            await ctx.send_message(Rejected(d.job, problems))
        else:  # the template itself failed: show it, but flag it
            await ctx.yield_output(_result(d.job, d.sentences, d.source, None, problems))


class Fallback(Executor):
    def __init__(self, roster: set[str]):
        super().__init__(id="fallback")
        self.roster = roster

    @handler(input=Rejected, workflow_output=dict)
    async def fallback(self, r: Rejected, ctx: WorkflowContext) -> None:
        sents = ex.template(r.job.pack, r.job.depth, r.job.fav)
        res = _result(r.job, sents, "template", None, ex.validate(sents, r.job.pack, self.roster))
        res["rejected"] = r.reasons
        await ctx.yield_output(res)


def _result(job: AnalysisJob, sents, source, model, problems) -> dict:
    return {"text": " ".join(s["s"] for s in sents), "sentences": sents, "source": source, "model": model,
            "latency_ms": round((time.perf_counter() - job.t0) * 1000), "validation": problems or "passed",
            "moment": job.pack["moment"], "depth": job.depth}


def build_analysis_workflow(agent, roster: set[str]):
    writer, validator, fallback = Writer(agent), Validator(roster), Fallback(roster)
    return (WorkflowBuilder(name="stoppage_analysis", start_executor=writer,
                            output_from=[validator, fallback])
            .add_edge(writer, validator)
            .add_edge(validator, fallback)
            .build())
