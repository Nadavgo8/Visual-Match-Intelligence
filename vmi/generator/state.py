"""Explicit football state, separate from export latency and rendered motion."""

from dataclasses import dataclass


@dataclass
class PlayState:
    stoppage_id: str | None = None
    trigger_event_id: str | None = None
    decision_id: str | None = None
    restart_id: str | None = None
    possession_id: str | None = None
    possession_team: str | None = None
    possession_no: int = 0
    play_context: str = "open_play"

    def possession(self, side: str, force: bool = False) -> str:
        if force or side != self.possession_team or self.possession_id is None:
            self.possession_no += 1
            self.possession_id = f"pos_{self.possession_no:04d}"
            self.possession_team = side
            self.play_context = "open_play"
        return self.possession_id
