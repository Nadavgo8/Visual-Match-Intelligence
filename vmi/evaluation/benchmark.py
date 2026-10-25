"""Immutable inputs for the annotated 30-question benchmark, independent of demos."""

import gzip
import hashlib
import json
from pathlib import Path

from ..generator.match import Match
from ..generator.motion import Keyframe

FIXTURE = Path(__file__).with_name("fixtures") / "demo-v2.2.json.gz"
SHA256 = "04d9e2119d9adf5a56ed87cb6cf1d6cd5e960160afea8dc5c7d1368d1e351572"


def benchmark_match() -> Match:
    """Return a fresh copy of the versioned match used to annotate question_set."""
    blob = FIXTURE.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SHA256:
        raise ValueError("evaluation benchmark checksum mismatch")
    data = json.loads(gzip.decompress(blob))
    data["keyframes"] = [Keyframe(**frame) for frame in data["keyframes"]]
    return Match(**data)
