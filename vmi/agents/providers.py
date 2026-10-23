"""Provider-neutral model layer (D2-00 skeleton).

The product reaches a language model only through `generate`: a request with a
frozen snapshot, a profile and a time limit goes in; text, fact references and a
status come out. The model is never chosen here. Until D2-00 is decided, no
provider is wired into the app, and every failure falls back to a labelled
template instead of a retry or another provider.

Answer kinds shown to the viewer:
- "live": written by a model for this request.
- "cached": written by a model earlier and reused (labelled by the cache owner).
- "template": written by deterministic code. Never presented as AI.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

TOTAL_TIMEOUT_S = 20.0
REQUEST_KINDS = {"explain", "answer", "summary"}


class QuotaExhausted(Exception):
    """The provider's free quota is used up. Never retried or rerouted to a paid provider."""


class CostRiskError(ValueError):
    """The provider did not declare that it cannot charge. Zero extra cost is mandatory."""


@dataclass(frozen=True)
class ModelRequest:
    kind: str
    prompt: str
    snapshot: dict
    snapshot_t: float
    run_id: str | None = None
    profile: dict = field(default_factory=dict)
    timeout_s: float = TOTAL_TIMEOUT_S

    def __post_init__(self):
        if self.kind not in REQUEST_KINDS:
            raise ValueError(f"unknown request kind {self.kind!r}")
        if not 0 <= self.timeout_s <= TOTAL_TIMEOUT_S:
            raise ValueError("timeout must be between 0 and the 20 s total limit")


@dataclass
class ModelResult:
    text: str
    evidence: list[str]
    status: str  # "ok" | "fallback"
    answer_kind: str  # "live" | "template"
    provider: str | None
    model: str | None
    latency_ms: int
    error: str | None = None  # "timeout" | "quota_exhausted" | "unavailable" | "error:<Type>"


class Provider(Protocol):
    name: str
    model: str
    may_charge: bool

    async def complete(self, request: ModelRequest) -> tuple[str, list[str]]: ...


Fallback = Callable[[ModelRequest], tuple[str, list[str]]]


def check_zero_cost(provider) -> None:
    """Refuse any provider that hasn't explicitly declared `may_charge = False`."""
    if getattr(provider, "may_charge", True) is not False:
        raise CostRiskError(f"provider {getattr(provider, 'name', provider)!r} may charge; refusing to call it")


async def generate(provider: Provider | None, request: ModelRequest, fallback: Fallback,
                   clock: Callable[[], float] = time.perf_counter) -> ModelResult:
    """One attempt at the provider within the request's time limit, else the template.

    No retries and no second provider: a timeout, an exhausted quota or any error
    returns the fallback text labelled "template", with the reason in `error`.
    """
    t0 = clock()
    if provider is None:
        text, evidence = fallback(request)
        return ModelResult(text, evidence, "fallback", "template", None, None, _ms(clock, t0), "unavailable")
    check_zero_cost(provider)
    try:
        text, evidence = await asyncio.wait_for(provider.complete(request), timeout=request.timeout_s)
        return ModelResult(text, list(evidence), "ok", "live", provider.name, provider.model, _ms(clock, t0))
    except asyncio.TimeoutError:
        error = "timeout"
    except QuotaExhausted:
        error = "quota_exhausted"
    except Exception as e:  # network, bad output, model crash: the viewer still gets a correct text
        error = f"error:{type(e).__name__}"
    text, evidence = fallback(request)
    return ModelResult(text, evidence, "fallback", "template", provider.name, provider.model, _ms(clock, t0), error)


def _ms(clock: Callable[[], float], t0: float) -> int:
    return round((clock() - t0) * 1000)
