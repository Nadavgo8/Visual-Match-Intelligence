import json

from vmi.generator.fixtures import export_fixture, quality_report
from vmi.generator.scenarios import SCENARIOS, generate_scenario


def test_all_scenario_quality_reports_are_explicit_about_injected_anomalies():
    for name in SCENARIOS:
        report = quality_report(generate_scenario(name))
        assert report["status"] == "PASS", report
        assert report["frames_checked"] > 1 and report["tracking_hz"] == 20
        assert not report["errors"]
        if name == "xg_duplicate": assert report["duplicates"] == 1
        if name == "source_missing": assert len(report["orphan_links"]) == 2
        if name == "xg_missing": assert report["missing_xg"] == 1


def test_fixture_export_is_byte_reproducible_and_streams_20hz(tmp_path):
    first, second = tmp_path/"first", tmp_path/"second"
    export_fixture("assist", 12, first)
    export_fixture("assist", 12, second)
    a, b = first/"assist", second/"assist"
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    with (a/"tracking-20hz.jsonl").open(encoding="utf-8") as handle:
        initial = [json.loads(next(handle)) for _ in range(3)]
    assert [f["t"] for f in initial] == [0, 0.05, 0.1]
    assert json.loads((a/"meta.json").read_text())["generator_version"] == "2.4.0"


def test_quality_report_detects_unexpected_duplicate_or_score_corruption():
    m = generate_scenario("assist")
    m.events.append(dict(m.events[0]))
    m.meta["final_score"]["home"] = 99
    report = quality_report(m)
    assert report["status"] == "FAIL"
    problems = [e["problem"] for e in report["errors"]]
    assert "unexpected duplicate event" in problems
    assert "score disagrees with result/cancellation records" in problems
