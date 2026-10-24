"""The v2 JSON Schemas match the generator's output and agree with the runtime validator."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from vmi.contracts import validate_record
from vmi.generator.match import generate_match
from vmi.generator.scenarios import SCENARIOS, generate_scenario
from vmi.generator.tracking import Tracker

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "v2"
SCHEMAS = {name: json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
           for name in ("event", "stream")}
VALIDATORS = {name: Draft202012Validator(s) for name, s in SCHEMAS.items()}
EXAMPLES = json.loads((CONTRACTS / "examples.json").read_text(encoding="utf-8"))


def schema_errors(record):
    kind = "stream" if "stream" in record else "event"
    return [e.message for e in VALIDATORS[kind].iter_errors(record)]


def runtime_rejects(record, match_id):
    try:
        validate_record(record, match_id)
    except ValueError:
        return True
    return False


@pytest.mark.parametrize("name", ["event", "stream"])
def test_schemas_are_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(SCHEMAS[name])


def test_every_record_of_the_demo_match_fits_the_schemas():
    m = generate_match(12)
    tracker = Tracker(m)
    samples = [tracker.observation(t) for t in (0.0, 100.0, 1500.0, 2950.0, 4500.0)]
    bad = [(r.get("id") or r.get("stream"), errs[:2]) for r in [*m.events, *m.crowd, *m.match_state, *samples]
           if (errs := schema_errors(r))]
    assert not bad, bad[:5]


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_record_fits_the_schemas(name):
    m = generate_scenario(name)
    bad = [(r.get("id") or r.get("stream"), errs[:2]) for r in [*m.events, *m.crowd, *m.match_state]
           if (errs := schema_errors(r))]
    assert not bad, bad[:5]


@pytest.mark.parametrize("ex", EXAMPLES["valid"], ids=lambda e: e["name"])
def test_valid_examples_pass_the_schema_and_the_runtime_validator(ex):
    assert schema_errors(ex["record"]) == []
    assert not runtime_rejects(ex["record"], EXAMPLES["match_id"])


@pytest.mark.parametrize("ex", EXAMPLES["invalid"], ids=lambda e: e["name"])
def test_invalid_examples_are_rejected_exactly_where_documented(ex):
    rejected = set()
    if schema_errors(ex["record"]):
        rejected.add("schema")
    if runtime_rejects(ex["record"], EXAMPLES["match_id"]):
        rejected.add("runtime")
    assert rejected == set(ex["rejected_by"])
