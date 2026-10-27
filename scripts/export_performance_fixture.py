"""Export a small deterministic local replay for drawing/transport isolation."""
import argparse
import json
from pathlib import Path

from vmi.engine.replay import Replay
from vmi.generator.match import generate_match
from vmi.generator.tracking import Tracker


def export(path, seed=12, start=600, duration=30):
    match = generate_match(seed)
    replay, tracker = Replay(match), Tracker(match)
    initial = replay.advance(start)
    meters = [o for o in initial if o["kind"] == "meters"][-1:]
    banners, frames = [], []
    for i in range(duration * 20 + 1):
        t = start + i / 20
        for output in replay.advance(t):
            if output["kind"] == "meters":
                meters.append(output)
            elif output["kind"] == "banner":
                banners.append(output)
        frames.append(tracker.frame(t))
    result = {"purpose": "Developer local-replay rendering isolation; no network throughput claim",
              "seed": seed, "generator_version": match.meta["generator_version"], "start": start,
              "duration": duration, "teams": match.meta["teams"], "frames": frames, "meters": meters, "banners": banners}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"Exported seed {seed}, generator {match.meta['generator_version']}, {len(frames)} frames to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--seed", type=int, default=12)
    parser.add_argument("--start", type=int, default=600)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    export(args.path, args.seed, args.start, args.duration)
