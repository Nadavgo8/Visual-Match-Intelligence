"""Football clock from delivered period boundaries and simulation time only."""

from dataclasses import dataclass


@dataclass
class MatchClock:
    reported: str = "0:00"
    reported_period: int = 1
    last_t: float = -1
    period: int = 0
    origin: float | None = None
    end: float | None = None

    def observe(self, rec: dict) -> None:
        if rec.get("type") == "shot_xg":
            return  # Its timestamp describes analytics availability, not the match clock.
        period, at = rec.get("period", self.reported_period), rec["t"]
        kind = rec.get("type")
        # A boundary can arrive after a later ordinary record. Use the delivered
        # boundary without rolling the observed period or latest record backwards.
        if kind == "period_start" and (period > self.period or (period == self.period and self.origin is None)):
            end = self.end if period == self.period else None
            self.period, self.origin, self.end = period, at, end
        if kind == "period_end" and period >= self.period:
            if period > self.period:
                self.period, self.origin, self.end = period, None, None
            self.end = at if self.end is None else min(self.end, at)
        if at >= self.last_t:
            self.reported = rec.get("clock", self.reported)
            self.reported_period, self.last_t = period, at

    def read(self, now: float) -> str:
        # Without a delivered origin do not guess the offset from the minute-only
        # added-time label, or read a future period boundary out of the generator.
        if self.origin is None or self.period != self.reported_period:
            return self.reported
        at = max(now, self.last_t, self.origin)
        if self.end is not None:
            at = min(at, self.end)
        seconds = (self.period - 1) * 2700 + at - self.origin
        regular_end = self.period * 2700
        if seconds > regular_end:
            return f"{regular_end // 60}+{int((seconds - regular_end) // 60) + 1}'"
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
