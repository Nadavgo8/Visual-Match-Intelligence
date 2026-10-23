from copy import deepcopy

import pytest

from vmi.generator.analytics import chance_quality, delayed_xg
from vmi.generator.export import initial_metadata


def test_penalty_estimate_and_geometry_are_independent_of_result():
    shot = {"id": "s1", "match_id": "m", "t": 10, "period": 1, "clock": "0:10",
            "team": "home", "player_id": "H9", "shot": {"penalty": True}}
    assert chance_quality(94, 34, penalty=True) == 0.77
    a = delayed_xg(12, shot, 94, 34, False, (2, 5))
    shot["shot"]["outcome"] = "off_target"
    b = delayed_xg(12, shot, 94, 34, False, (2, 5))
    assert a == b
    assert a["xg"] == 0.77
    assert 12 <= a["t"] <= 15
    assert a["delivered_t"] >= a["t"]
    assert chance_quality(99, 34) > chance_quality(80, 12)


@pytest.mark.parametrize("delay", [(-1, 5), (5, 2), (0, float("inf")), (float("nan"), 5)])
def test_invalid_analytics_delays_are_rejected(delay):
    with pytest.raises(ValueError):
        delayed_xg(1, {}, 94, 34, False, delay)


def test_public_metadata_excludes_future_and_is_a_snapshot():
    meta = {"teams": {"home": {"name": "A"}}, "final_score": {"home": 4}, "end_t": 6000}
    snapshot = initial_metadata(meta)
    expected = deepcopy(snapshot)
    meta["teams"]["home"]["name"] = "B"
    assert snapshot == expected == {"teams": {"home": {"name": "A"}}}
