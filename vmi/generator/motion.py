"""Private truth keyframes; consumers of the event feed cannot read future motion."""

from dataclasses import dataclass


@dataclass
class Keyframe:
    t: float
    x: float
    y: float
    holder: str | None
    in_play: bool
    z: float = 0.0
    flight_height: float = 0.0  # arc from this keyframe to the next one
    possession_id: str | None = None
