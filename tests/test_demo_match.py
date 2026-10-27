"""The demo match is a fixed story for the video, the judges' link and the pitch.

If a generator change alters any of these moments, this test fails before it reaches main.
Changing the demo story on purpose means updating this test and the demo script together.
"""

import os

from vmi.generator.match import generate_match

DEMO_STORY = {
    "generator_version": "2.5.0",
    "final": {"home": 2, "away": 1},
    # Original agreed story: the physical demo scenario must satisfy these times.
    "goals": [("37:58", "home", "Dumont"), ("43:34", "home", "Ferreira"), ("65:08", "away", "Marsh")],
    "var": [("37:16", "penalty", "no_penalty", "overturned"), ("66:38", "goal", "goal", "stands")],
    "cancelled_goals": [],
}


def demo_moments(seed: int) -> dict:
    m = generate_match(seed)
    names = {p["id"]: p["name"] for side in m.meta["teams"].values() for p in side["players"]}
    by_id = {e["id"]: e for e in m.events}
    corrections = [e for e in m.events if e["type"] == "goal_cancelled"]
    cancelled_ids = {e["result_id"] for e in corrections}
    for correction in corrections:
        result = by_id[correction["result_id"]]
        assert result["type"] == "shot_result" and result["outcome"] == "goal"
        assert correction["shot_id"] == result["shot_id"]
        assert by_id[correction["decision_id"]]["type"] == "referee_decision"
    counted = {
        side: sum(
            e["type"] == "shot_result" and e["outcome"] == "goal" and e["id"] not in cancelled_ids and e["team"] == side
            for e in m.events
        )
        for side in ("home", "away")
    }
    assert counted == m.meta["final_score"]
    return {
        "generator_version": m.meta["generator_version"],
        "final": m.meta["final_score"],
        "goals": [
            (e["clock"], e["team"], names[e["player_id"]])
            for e in m.events
            if e["type"] == "shot_result" and e["outcome"] == "goal"
        ],
        "var": [
            (e["clock"], e["var"]["incident"], e["var"]["original_decision"], e["var"]["outcome"])
            for e in m.events
            if e["type"] == "var" and e["var"]["phase"] == "decision"
        ],
        "cancelled_goals": [
            (by_id[e["result_id"]]["clock"], e["team"], names[e["player_id"]], e["clock"]) for e in corrections
        ],
    }


def test_demo_seed_defaults_to_2():
    from vmi.api import server

    assert os.getenv("VMI_DEMO_SEED") is None or server.DEMO_SEED == int(os.environ["VMI_DEMO_SEED"])
    if os.getenv("VMI_DEMO_SEED") is None:
        assert server.DEMO_SEED == 2


def test_demo_match_keeps_its_story():
    assert demo_moments(2) == DEMO_STORY
