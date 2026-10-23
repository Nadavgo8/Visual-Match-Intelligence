"""Reproducible small JSONL fixtures and a streaming 20 Hz quality report.

Run: python -m vmi.generator.fixtures --output out/v2-fixtures
"""

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..contracts import LINK_PARENTS, validate_record
from .scenarios import SCENARIOS, generate_scenario
from .tracking import Tracker


def quality_report(match) -> dict:
    errors = []
    unique = {e["id"]: e for e in match.events}
    counts = Counter(e["type"] for e in unique.values())
    duplicates = len(match.events) - len(unique)
    orphans = []
    for e in [*match.events, *match.crowd, *match.match_state]:
        try:
            validate_record(e, match.meta["match_id"])
        except ValueError as exc:
            errors.append({"id": e.get("id"), "problem": str(exc)})
        for link in LINK_PARENTS.get(e.get("type"), {}):
            if e[link] not in unique:
                orphans.append({"id": e["id"], "link": link, "missing": e[link]})
    expected = match.meta.get("expected_anomalies", [])
    if duplicates and "duplicate_event" not in expected:
        errors.append({"problem": "unexpected duplicate event"})
    if orphans and "missing_source" not in expected:
        errors.append({"problem": "unexpected orphan links"})
    xg_shots = {e["shot_id"] for e in unique.values() if e["type"] == "shot_xg"}
    missing_xg = sum(e["type"] == "shot" and e["id"] not in xg_shots for e in unique.values())
    if missing_xg and "missing_xg" not in expected:
        errors.append({"problem": "unexpected missing xG"})
    score = {"home": 0, "away": 0}
    for e in unique.values():
        if e["type"] == "shot_result" and e["outcome"] == "goal":
            score[e["team"]] += 1
        elif e["type"] == "goal_cancelled":
            score[e["team"]] -= 1
    if score != match.meta["final_score"]:
        errors.append({"problem": "score disagrees with result/cancellation records"})
    kfs = sorted(match.keyframes, key=lambda k: k.t)
    jumps = []
    peak_speed = 0.0
    for a, b in zip(kfs, kfs[1:]):
        distance = math.hypot(b.x - a.x, b.y - a.y)
        if b.t == a.t and distance > 0.02:
            jumps.append({"t": a.t, "distance_m": round(distance, 2)})
        elif b.t > a.t:
            peak_speed = max(peak_speed, distance / (b.t - a.t))
    tracker = Tracker(match)
    n_frames = 0
    peak_height = 0.0
    for frame in tracker.frames(hz=20):
        n_frames += 1
        peak_height = max(peak_height, frame["ball_height"])
        bx, by = frame["ball"]
        ids = [p["id"] for p in frame["players"]]
        if not (-1 <= bx <= 106 and -1 <= by <= 69 and 0 <= frame["ball_height"] <= 20):
            errors.append({"t": frame["t"], "problem": "ball outside configured fixture bounds"})
            break
        if len(ids) != len(set(ids)) or any(not (0 <= p["x"] <= 105 and 0 <= p["y"] <= 68) for p in frame["players"]):
            errors.append({"t": frame["t"], "problem": "invalid active player positions"})
            break
    return {"scenario": match.meta.get("scenario"), "seed": match.meta["seed"], "schema_version": "2.0",
            "status": "FAIL" if errors else "PASS", "errors": errors, "counts": dict(counts),
            "score": score, "possessions": len({k.possession_id for k in kfs if k.possession_id}),
            "duplicates": duplicates, "orphan_links": orphans, "missing_xg": missing_xg,
            "expected_anomalies": expected, "tracking_hz": 20, "frames_checked": n_frames,
            "peak_ball_height_m": peak_height, "peak_ball_speed_mps": round(peak_speed, 2),
            "setup_discontinuities": jumps[:10], "setup_discontinuity_count": len(jumps),
            "note": "Scripted segment setup can reposition players/ball; jumps are reported, not hidden. Not a calibrated motion model."}


def _jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def export_fixture(name: str, seed: int, destination: Path) -> dict:
    match = generate_scenario(name, seed)
    folder = destination / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(json.dumps(match.meta, indent=2, sort_keys=True), encoding="utf-8")
    for stream, rows in (("events", match.events), ("crowd", match.crowd), ("match_state", match.match_state)):
        _jsonl(folder / f"{stream}.jsonl", rows)
    _jsonl(folder / "keyframes.jsonl", (asdict(k) for k in match.keyframes))
    _jsonl(folder / "tracking-20hz.jsonl", Tracker(match).frames())
    report = quality_report(match)
    (folder / "quality.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("out/v2-fixtures"))
    parser.add_argument("--scenario", choices=SCENARIOS, action="append")
    parser.add_argument("--seed", type=int, default=12)
    args = parser.parse_args()
    reports = [export_fixture(name, args.seed, args.output) for name in args.scenario or SCENARIOS]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "quality-summary.json").write_text(json.dumps(reports, indent=2, sort_keys=True), encoding="utf-8")
    failures = sum(r["status"] != "PASS" for r in reports)
    print(f"{len(reports)} fixtures exported; {failures} failed quality reports; 20 Hz streamed to {args.output}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
