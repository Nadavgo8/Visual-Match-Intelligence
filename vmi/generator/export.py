"""Export boundaries: initial public metadata never contains the match's ending."""

from copy import deepcopy


def initial_metadata(meta: dict) -> dict:
    return deepcopy({k: v for k, v in meta.items() if k not in {"end_t", "final_score", "scenario", "expected_anomalies"}})


def finish_export(events: list[dict], states: list[dict], crowd: list[dict]) -> None:
    for rec in [*events, *states, *crowd]:
        rec["schema_version"] = "2.0"
    events.sort(key=lambda e: (e["t"], e["id"]))
