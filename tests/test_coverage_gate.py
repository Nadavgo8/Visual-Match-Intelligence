"""The coverage gate measures totals, changed code and critical files separately, and fails on missing data."""

import json

import pytest

from tools import coverage_gate as gate

DIFF = """\
diff --git a/vmi/engine/derive.py b/vmi/engine/derive.py
--- a/vmi/engine/derive.py
+++ b/vmi/engine/derive.py
@@ -10,0 +11,3 @@ def a():
+x
+y
+z
@@ -40 +43 @@ def b():
-old
+new
@@ -60,2 +62,0 @@ def c():
-gone
-gone
diff --git a/vmi/old.py b/vmi/old.py
--- a/vmi/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
"""


def report(files, covered=90, statements=100, cbranches=40, branches=50, branch=True):
    return {"meta": {"branch_coverage": branch},
            "totals": {"covered_lines": covered, "num_statements": statements,
                       "covered_branches": cbranches, "num_branches": branches},
            "files": files}


def file(executed, missing, eb=(), mb=()):
    return {"executed_lines": list(executed), "missing_lines": list(missing),
            "executed_branches": [list(b) for b in eb], "missing_branches": [list(b) for b in mb]}


BASE = {"lines": 90.0, "branches": 80.0}


def test_parse_diff_reads_new_side_lines_and_skips_deletions():
    assert gate.parse_diff(DIFF) == {"vmi/engine/derive.py": {11, 12, 13, 43}}


def test_totals_and_changed_code_pass_at_the_boundaries():
    changed = {"vmi/engine/derive.py": set(range(1, 11))}  # 10 statements, 9 covered = 90%
    files = {"vmi\\engine\\derive.py": file(range(1, 10), [10], eb=[(1, 2)] * 17, mb=[(2, 3)] * 3)}  # 85% branches
    problems, summary = gate.evaluate(report(files), BASE, changed)
    assert problems == []
    assert "changed lines: 90.00% (9/10, minimum 90%)" in summary
    assert "changed branches: 85.00% (17/20, minimum 85%)" in summary
    assert "critical changed lines: none" in summary


def test_total_coverage_below_the_baseline_fails():
    problems, _ = gate.evaluate(report({}, covered=89, cbranches=40), BASE, {})
    assert problems == ["vmi/ lines coverage fell from 90.00% to 89.00%"]


def test_changed_lines_below_90_percent_fail():
    files = {"vmi/engine/derive.py": file(range(1, 9), [9, 10])}
    problems, _ = gate.evaluate(report(files), BASE, {"vmi/engine/derive.py": set(range(1, 11))})
    assert problems == ["changed lines coverage 80.00% is below 90%"]


def test_changed_branches_below_85_percent_fail():
    files = {"vmi/engine/derive.py": file([1], [], eb=[(1, 2)] * 4, mb=[(1, 3)])}
    problems, _ = gate.evaluate(report(files), BASE, {"vmi/engine/derive.py": {1}})
    assert problems == ["changed branches coverage 80.00% is below 85%"]


def test_critical_file_needs_95_percent_of_changed_lines():
    changed = {"vmi/contracts.py": set(range(1, 21))}
    ok = {"vmi/contracts.py": file(range(1, 20), [20])}  # 95%
    low = {"vmi/contracts.py": file(range(1, 19), [19, 20])}  # 90%
    assert gate.evaluate(report(ok), BASE, changed)[0] == []
    assert gate.evaluate(report(low), BASE, changed)[0] == ["critical changed lines coverage 90.00% is below 95%"]


def test_lines_outside_vmi_or_not_statements_are_ignored():
    files = {"vmi/engine/derive.py": file([5], [])}
    changed = {"vmi/engine/derive.py": {1, 2, 5}, "tests/test_x.py": {1}, "web/tv.js": {3}}
    assert gate.changed_coverage(report(files), changed) == {"lines": (1, 1), "branches": (0, 0)}


@pytest.mark.parametrize("bad,message", [
    (report({}, branch=False), "no branch data"),
    ({"meta": {"branch_coverage": True}, "totals": {}, "files": {}}, "no totals"),
])
def test_missing_report_data_fails(bad, message):
    with pytest.raises(gate.GateError, match=message):
        gate.evaluate(bad, BASE, {})


def test_changed_file_without_coverage_data_fails():
    with pytest.raises(gate.GateError, match="no coverage data for changed file vmi/new.py"):
        gate.evaluate(report({}), BASE, {"vmi/new.py": {1}})


def test_update_baseline_only_raises(tmp_path):
    assert gate.raised_baseline(report({}, covered=95, cbranches=30), BASE) == {"lines": 95.0, "branches": 80.0}


def test_cli_exit_codes(tmp_path):
    cov, base, diff = tmp_path / "c.json", tmp_path / "b.json", tmp_path / "d.diff"
    base.write_text(json.dumps(BASE))
    diff.write_text("")
    cov.write_text(json.dumps(report({})))
    assert gate.main(["--coverage", str(cov), "--baseline", str(base), "--diff-file", str(diff)]) == 0
    cov.write_text(json.dumps(report({}, covered=10)))
    assert gate.main(["--coverage", str(cov), "--baseline", str(base), "--diff-file", str(diff)]) == 1
    cov.write_text("{}")
    assert gate.main(["--coverage", str(cov), "--baseline", str(base), "--diff-file", str(diff)]) == 2
    assert gate.main(["--coverage", str(cov), "--baseline", str(base)]) == 2  # no diff source
