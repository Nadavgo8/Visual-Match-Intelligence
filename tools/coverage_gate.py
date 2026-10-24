"""Coverage gate (docs/implementation/12-QUALITY-AND-GIT-GATES.md §3.3).

Reads a coverage.py JSON report with branch data and the diff against a base commit,
and checks each rule separately:

- all of vmi/: line and branch coverage may not fall below the recorded baseline;
- lines and branches changed in vmi/: at least 90% and 85%;
- changed lines and branches in critical files (time, run_id, future filtering,
  event linking, validator, model layer): at least 95% and 90%.

Missing data fails: no totals, no branch data, or a changed file without coverage.
`--update-baseline` may only raise the baseline, never lower it.

    python -m pytest tests -p pytest_cov --cov --cov-branch --cov-report=json:out/coverage.json
    python -m tools.coverage_gate --coverage out/coverage.json --base origin/main
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "coverage-baseline.json"
CRITICAL = {"vmi/contracts.py", "vmi/engine/model.py", "vmi/engine/replay.py", "vmi/agents/explainer.py",
            "vmi/agents/providers.py", "vmi/api/server.py"}
CHANGED_MIN = {"lines": 90.0, "branches": 85.0}
CRITICAL_MIN = {"lines": 95.0, "branches": 90.0}
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class GateError(Exception):
    """Coverage data is missing or unusable; the gate cannot pass."""


def parse_diff(text: str) -> dict[str, set[int]]:
    """Added or changed line numbers (new side) per file from `git diff -U0`."""
    changed: dict[str, set[int]] = {}
    path = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target.removeprefix("b/")
        elif path and (m := HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                changed.setdefault(path, set()).update(range(start, start + count))
    return changed


def _files(report: dict) -> dict[str, dict]:
    return {name.replace("\\", "/"): data for name, data in report.get("files", {}).items()}


def _pct(covered: int, total: int) -> float | None:
    return None if total == 0 else round(100.0 * covered / total, 2)


def totals(report: dict) -> dict[str, float]:
    t = report.get("totals") or {}
    if not report.get("meta", {}).get("branch_coverage"):
        raise GateError("the report has no branch data; run with --cov-branch")
    if not t.get("num_statements") or "num_branches" not in t:
        raise GateError("the report has no totals")
    return {"lines": _pct(t["covered_lines"], t["num_statements"]),
            "branches": _pct(t["covered_branches"], t["num_branches"]) or 0.0}


def changed_coverage(report: dict, changed: dict[str, set[int]], only: set[str] | None = None) -> dict:
    files = _files(report)
    lines = [0, 0]
    branches = [0, 0]
    for path, numbers in changed.items():
        if not (path.startswith("vmi/") and path.endswith(".py")) or (only is not None and path not in only):
            continue
        data = files.get(path)
        if data is None:
            raise GateError(f"no coverage data for changed file {path}")
        executed, missing = set(data.get("executed_lines", [])), set(data.get("missing_lines", []))
        lines[0] += len(numbers & executed)
        lines[1] += len(numbers & (executed | missing))
        hit = [b for b in data.get("executed_branches", []) if b[0] in numbers]
        miss = [b for b in data.get("missing_branches", []) if b[0] in numbers]
        branches[0] += len(hit)
        branches[1] += len(hit) + len(miss)
    return {"lines": tuple(lines), "branches": tuple(branches)}


def evaluate(report: dict, baseline: dict, changed: dict[str, set[int]]) -> tuple[list[str], list[str]]:
    """Return (problems, summary lines). No problems means the gate passes."""
    problems, summary = [], []
    now = totals(report)
    for kind in ("lines", "branches"):
        base = baseline.get(kind)
        if base is None:
            raise GateError(f"baseline has no {kind} value")
        summary.append(f"vmi/ {kind}: {now[kind]:.2f}% (baseline {base:.2f}%)")
        if now[kind] < base:
            problems.append(f"vmi/ {kind} coverage fell from {base:.2f}% to {now[kind]:.2f}%")
    for label, scope, minimum in (("changed", None, CHANGED_MIN), ("critical changed", CRITICAL, CRITICAL_MIN)):
        got = changed_coverage(report, changed, scope)
        for kind in ("lines", "branches"):
            covered, total = got[kind]
            pct = _pct(covered, total)
            if pct is None:
                summary.append(f"{label} {kind}: none")
                continue
            summary.append(f"{label} {kind}: {pct:.2f}% ({covered}/{total}, minimum {minimum[kind]:.0f}%)")
            if pct < minimum[kind]:
                problems.append(f"{label} {kind} coverage {pct:.2f}% is below {minimum[kind]:.0f}%")
    return problems, summary


def raised_baseline(report: dict, baseline: dict) -> dict:
    now = totals(report)
    return {**baseline, **{k: max(baseline.get(k, 0.0), now[k]) for k in ("lines", "branches")}}


def git_diff(base: str) -> str:
    return subprocess.run(["git", "diff", "-U0", "--no-color", "--no-ext-diff", f"{base}...HEAD", "--", "vmi"],
                          cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VMI coverage gate")
    ap.add_argument("--coverage", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--base", help="git ref to diff against, e.g. origin/main")
    ap.add_argument("--diff-file", type=Path, help="a saved `git diff -U0` instead of --base")
    ap.add_argument("--update-baseline", action="store_true", help="raise the baseline to the current totals")
    args = ap.parse_args(argv)
    try:
        report = json.loads(args.coverage.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        if args.update_baseline:
            args.baseline.write_text(json.dumps(raised_baseline(report, baseline), indent=2) + "\n", encoding="utf-8")
            print(f"baseline written to {args.baseline}")
            return 0
        if args.diff_file:
            diff = args.diff_file.read_text(encoding="utf-8")
        elif args.base:
            diff = git_diff(args.base)
        else:
            raise GateError("give --base or --diff-file so changed code can be measured")
        problems, summary = evaluate(report, baseline, parse_diff(diff))
    except (GateError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        print(f"COVERAGE GATE: FAIL (missing data) - {e}", file=sys.stderr)
        return 2
    print("\n".join(summary))
    if problems:
        print("COVERAGE GATE: FAIL\n- " + "\n- ".join(problems), file=sys.stderr)
        return 1
    print("COVERAGE GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
