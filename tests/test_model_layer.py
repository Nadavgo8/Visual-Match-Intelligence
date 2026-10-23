"""The provider-neutral model layer: one attempt, labelled fallback, never a paid provider."""

import asyncio

import pytest

from vmi.agents.providers import CostRiskError, ModelRequest, QuotaExhausted, generate


def request(timeout_s=20.0, kind="answer"):
    return ModelRequest(kind=kind, prompt="What's the score?", snapshot={"score": "1-0"}, snapshot_t=1500.0,
                        timeout_s=timeout_s)


def template(_req):
    return "Harbour City lead 1-0.", ["state"]


class Fake:
    name, model, may_charge = "fake", "fake-1", False

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    async def complete(self, req):
        self.calls += 1
        return await self.behaviour(req)


def ticking_clock(step_s):
    t = [0.0]

    def clock():
        t[0] += step_s
        return t[0]
    return clock


def test_live_answer_is_labelled_with_provider_model_and_latency():
    async def ok(_req):
        return "It's 1-0 to Harbour City.", ["state"]
    res = asyncio.run(generate(Fake(ok), request(), template, clock=ticking_clock(0.25)))
    assert (res.status, res.answer_kind, res.provider, res.model, res.error) == ("ok", "live", "fake", "fake-1", None)
    assert res.text == "It's 1-0 to Harbour City." and res.evidence == ["state"]
    assert res.latency_ms == 250


def test_timeout_returns_the_template_labelled_as_template_after_one_attempt():
    async def hang(_req):
        await asyncio.Event().wait()
    fake = Fake(hang)
    res = asyncio.run(generate(fake, request(timeout_s=0.01), template))  # long enough to start the attempt
    assert fake.calls == 1
    assert (res.status, res.answer_kind, res.error) == ("fallback", "template", "timeout")
    assert res.text == "Harbour City lead 1-0." and res.evidence == ["state"]


def test_exhausted_quota_is_not_retried_and_not_rerouted():
    async def quota(_req):
        raise QuotaExhausted()
    fake = Fake(quota)
    res = asyncio.run(generate(fake, request(), template))
    assert fake.calls == 1
    assert (res.answer_kind, res.error, res.provider) == ("template", "quota_exhausted", "fake")


def test_provider_error_falls_back_and_records_the_error_type():
    async def broken(_req):
        raise ValueError("not JSON")
    res = asyncio.run(generate(Fake(broken), request(), template))
    assert (res.status, res.answer_kind, res.error) == ("fallback", "template", "error:ValueError")


@pytest.mark.parametrize("declared", [True, None])
def test_provider_that_may_charge_or_does_not_say_is_never_called(declared):
    async def ok(_req):
        return "x", []
    fake = Fake(ok)
    if declared is None:
        del Fake.may_charge  # attribute missing: treated as a cost risk
        try:
            with pytest.raises(CostRiskError):
                asyncio.run(generate(fake, request(), template))
        finally:
            Fake.may_charge = False
    else:
        fake.may_charge = declared
        with pytest.raises(CostRiskError):
            asyncio.run(generate(fake, request(), template))
    assert fake.calls == 0


def test_no_provider_answers_with_the_template_marked_unavailable():
    res = asyncio.run(generate(None, request(), template))
    assert (res.status, res.answer_kind, res.provider, res.error) == ("fallback", "template", None, "unavailable")


@pytest.mark.parametrize("kwargs", [{"timeout_s": 20.01}, {"timeout_s": -1}, {"kind": "chat"}])
def test_request_rejects_unknown_kinds_and_time_limits_beyond_20s(kwargs):
    with pytest.raises(ValueError):
        request(**kwargs)
