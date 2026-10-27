"""Physical requirements independent of the trajectory implementation's formulas."""

import math

import pytest

from vmi.generator.physics import PathNode, sample, through_velocities, travel_time, certified, unit_roots
from vmi.generator.motion import support_position


def test_continuous_run_keeps_nonzero_velocity_at_an_intermediate_knot():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(2, 14, 20, 0), PathNode(4, 18, 20, 0)])
    for t in (1.99999, 2, 2.00001):
        x, y, motion = sample(nodes, t)
        assert motion["speed"] == pytest.approx(2, abs=0.001)
        assert motion["heading"] == pytest.approx(math.pi / 2)
        assert y == 20 and x == pytest.approx(14, abs=0.0001)
    assert sample(nodes, 4)[2]["distance"] == pytest.approx(8, abs=1e-8)


def test_velocity_and_acceleration_are_physical_derivatives_in_both_directions():
    for points in (((10, 20), (16, 23), (22, 20)), ((22, 20), (16, 23), (10, 20))):
        nodes = through_velocities([PathNode(i * 3, *p, 0) for i, p in enumerate(points)])
        previous = None
        for index in range(601):
            t = index / 100
            x, y, motion = sample(nodes, t)
            vx = math.sin(motion["heading"] or 0) * motion["speed"]
            vy = -math.cos(motion["heading"] or 0) * motion["speed"]
            assert motion["speed"] <= 9 + 1e-6
            if previous:
                px, py, pvx, pvy = previous
                assert math.hypot(vx - pvx, vy - pvy) <= 0.08 + 1e-5
                assert math.hypot(x - px, y - py) <= 0.090001
            if 0.001 < t < 5.999:
                a, b = sample(nodes, t - 0.00001), sample(nodes, t + 0.00001)
                assert (b[0] - a[0]) / 0.00002 == pytest.approx(vx, abs=0.0001)
                assert (b[1] - a[1]) / 0.00002 == pytest.approx(vy, abs=0.0001)
            previous = (x, y, vx, vy)


def test_reversal_brakes_to_rest_and_setup_time_includes_acceleration():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(3, 16, 20, 0), PathNode(6, 10, 20, 0)])
    assert sample(nodes, 3)[2]["speed"] == 0
    assert sample(nodes, 2.9)[2]["heading"] == pytest.approx(math.pi / 2)
    assert sample(nodes, 3.1)[2]["heading"] == pytest.approx(-math.pi / 2)
    assert travel_time(1) > 1 / 9
    assert travel_time(0) == 0


def test_stationary_sampling_and_reverse_seek_do_not_integrate_distance_history():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(3, 16, 20, 0), PathNode(6, 16, 20, 0)])
    expected = sample(nodes, 4)
    sample(nodes, 6)
    sample(nodes, 0)
    assert sample(nodes, 4) == expected
    assert expected[2]["speed"] == 0 and expected[2]["distance"] == pytest.approx(6)
    assert expected[2]["heading"] == pytest.approx(math.pi / 2)


def test_explicit_current_body_facing_is_separate_from_travel_and_seek_pure():
    nodes = through_velocities([PathNode(0, 100, 34, 0), PathNode(3, 105, 34, 0), PathNode(6, 105, 34, 0)],
                               facing_targets={3: -math.pi/2, 6: -math.pi/2})
    expected = sample(nodes, 4)
    assert expected[2]["facing"] == pytest.approx(-math.pi/2)
    assert expected[2]["heading"] == pytest.approx(math.pi/2)
    previous = sample(nodes, 0)[2]["facing"]
    for i in range(1, 601):
        facing = sample(nodes, i/100)[2]["facing"]
        turn = abs(math.atan2(math.sin(facing-previous), math.cos(facing-previous)))
        assert turn <= .060001
        previous = facing
    sample(nodes, 0)
    assert sample(nodes, 4) == expected


def test_impossible_explicit_facing_deadline_is_rejected_instead_of_snapping():
    with pytest.raises(ValueError, match="facing"):
        through_velocities([PathNode(0, 100, 34, 0), PathNode(.1, 100, 34, 0)],
                           facing_targets={0: math.pi/2, .1: -math.pi/2})


def test_stationary_body_obeys_an_explicit_facing_even_without_a_travel_heading():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(3, 10, 20, 0)],
                               facing_targets={3: -math.pi/2})
    for t in (0, 1, 3):
        motion = sample(nodes, t)[2]
        assert motion["speed"] == 0 and motion["facing"] == pytest.approx(-math.pi/2)


@pytest.mark.parametrize("right", [True, False])
def test_defending_own_box_has_cover_screen_and_outlets_in_distinct_depth_bands(right):
    roles = (("CB", 22, 26), ("RB", 28, 10), ("DM", 36, 34), ("CM", 42, 22), ("RW", 62, 12), ("ST", 66, 34))
    positions = []
    for role, x, y in roles:
        player = {"id": role, "team": "home", "position": role, "base_x": x, "base_y": y}
        ball = (6, 30) if right else (99, 38)
        point = support_position(player, right, ball, 10, "away")
        positions.append(point[0] if right else 105 - point[0])
    cb, fullback, dm, cm, winger, striker = positions
    assert cb < fullback < dm < cm < winger < striker
    assert striker >= 25 and winger >= 20 and cm >= 15
    assert max(positions) - min(positions) >= 20


def test_a_twenty_metre_four_second_run_is_not_rejected_as_walking_pace():
    a, b = PathNode(0, 10, 20, 0), PathNode(4, 30, 20, 20)
    assert certified(a, b)
    assert sample([a, b], 2)[2]["speed"] == pytest.approx(7.5)
    assert not certified(a, PathNode(3, 30, 20, 20))  # acceleration exceeds 8m/s²
    assert sorted(unit_roots((1, -1.5, 0.66, -0.08))) == pytest.approx([0.2, 0.5, 0.8])
    assert not certified(PathNode(0, 10, 20, 0, 10, 0), PathNode(2, 30, 20, 20, 10, 0)), (
        "constant10m/s cannot bypass speed9 through zero acceleration"
    )


def test_acceleration_limit_is_independent_of_the_speed_limit():
    assert not certified(PathNode(0, 10, 20, 0), PathNode(1, 12, 20, 2))  # peak speed 3, acceleration 12
    assert certified(PathNode(0, 10, 20, 0), PathNode(1.3, 12, 20, 2))  # peak speed 2.31, acceleration 7.10


def test_certificate_includes_endpoint_bounds_and_zero_or_reversed_time():
    assert certified(PathNode(1, 10, 20, 0), PathNode(1, 10, 20, 0))
    assert not certified(PathNode(1, 10, 20, 0), PathNode(1, 10.01, 20, 0))
    assert not certified(PathNode(1, 10, 20, 0), PathNode(0, 10, 20, 0))
    # Both inner Bezier controls are inside; an outside endpoint still fails.
    assert not certified(PathNode(0, 105.2, 34, 0, -0.6, 0), PathNode(1, 104.6, 34, 0, -0.6, 0))
    assert not certified(PathNode(0, 10, 20, 0, 0, -100), PathNode(2, 10, 21, 0))
    assert unit_roots((0, 0, 2, -1)) == pytest.approx([0.5])
    assert unit_roots((0, 1, -1, 0.25)) == pytest.approx([0.5])


def test_short_slow_corner_still_bounds_actual_body_turn_rate():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(0.1, 10.01, 20, 0), PathNode(0.2, 10.01, 20.01, 0)])
    previous = sample(nodes, 0.1)[2]["facing"]
    for i in range(1, 1001):
        current = sample(nodes, 0.1 + i * 0.0001)[2]["facing"]
        delta = math.atan2(math.sin(current - previous), math.cos(current - previous))
        assert abs(delta) / 0.0001 <= 6.000001
        previous = current


def test_gait_cycles_integrate_variable_cadence_and_facing_has_a_separate_turn_bound():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(3, 16, 23, 0), PathNode(6, 16, 30, 0)])
    integrated = 0.0
    previous = sample(nodes, 0)[2]
    last_rate = previous["speed"] / (0.8 + 0.5 * previous["speed"])
    for index in range(1, 6001):
        current = sample(nodes, index / 1000)[2]
        stride = min(4.4, max(0.8, 0.8 + 0.5 * current["speed"]))
        rate = current["speed"] / stride
        integrated += (last_rate + rate) * 0.0005
        assert current["gait_cycles"] >= previous["gait_cycles"] - 1e-6
        turn = math.atan2(
            math.sin(current["facing"] - previous["facing"]), math.cos(current["facing"] - previous["facing"])
        )
        assert abs(turn) <= 0.006001
        previous, last_rate = current, rate
    assert current["gait_cycles"] == pytest.approx(integrated, abs=0.001)
    assert sample(nodes, 3 - 1e-7)[2]["gait_cycles"] == pytest.approx(
        sample(nodes, 3 + 1e-7)[2]["gait_cycles"], abs=0.000001
    )


def test_certified_strong_turn_distance_and_gait_never_run_backward():
    from vmi.generator.physics import arc_metrics, _metric_curve, _metric_key

    a = PathNode(0, 50, 34, 0, -0.5502310440248639, 1.6246998777916524)
    b = PathNode(5.9167718405420375, 48.86507710453219, 36.7320476955137, 0, 2.3911157157975858, -1.395977939455939)
    assert certified(a, b)
    samples = [arc_metrics(a, b, i / 200) for i in range(201)]
    for previous, current in zip(samples, samples[1:]):
        assert current[0] >= previous[0] - 1e-12
        assert current[1] >= previous[1] - 1e-12
    expected = arc_metrics(a, b, 0.69)
    arc_metrics(a, b, 0.9)
    arc_metrics(a, b, 0.1)
    assert arc_metrics(a, b, 0.69) == expected
    for cell in list(_metric_curve(_metric_key(a, b)).nodes.values()):
        boundary = cell[1]
        left = arc_metrics(a, b, max(0, boundary - 1e-10))
        right = arc_metrics(a, b, min(1, boundary + 1e-10))
        for before, after in zip(left, right):
            assert after >= before - 1e-12
            assert after - before < 1e-6


def test_non_dyadic_reversal_keeps_the_independent_integral_accuracy_requirement():
    from vmi.generator.physics import arc_metrics

    a = PathNode(0, 50, 34, 0, -8.01, 0)
    b = PathNode(10, 54.45, 34, 0, 8.9, 0)
    assert certified(a, b)
    previous = sample([a, b], 0, distance=False)[:2]
    distance = cycles = 0.0
    dt = 10 / 40000
    for index in range(1, 19001):
        position = sample([a, b], index * dt, distance=False)[:2]
        step = math.dist(previous, position)
        distance += step
        cycles += step / min(4.4, 0.8 + 0.5 * step / dt)
        previous = position
    actual = arc_metrics(a, b, 0.475)
    assert actual[0] == pytest.approx(distance, abs=3e-5)
    assert actual[1] == pytest.approx(cycles, abs=3e-5)


@pytest.mark.parametrize("end_velocity", [(2.3911157157975858, -1.395977939455939), (-1.5, 2.0), None])
def test_source_integral_matches_dense_independent_position_measurement(end_velocity):
    from vmi.generator.physics import arc_metrics

    if end_velocity is None:
        # Cross the speed-dependent stride cap at 7.2m/s in a real fast run.
        a, b = PathNode(0, 20, 34, 0), PathNode(4, 40, 34, 0)
    else:
        a = PathNode(0, 50, 34, 0, -0.5502310440248639, 1.6246998777916524)
        b = PathNode(5.9167718405420375, 48.86507710453219, 36.7320476955137, 0, *end_velocity)
    assert certified(a, b)
    previous = sample([a, b], 0, distance=False)[:2]
    distance = cycles = 0.0
    dt = b.t / 40000
    for i in range(1, 40001):
        current = sample([a, b], i * dt, distance=False)[:2]
        travelled = math.dist(previous, current)
        speed = travelled / dt
        distance += travelled
        cycles += travelled / min(4.4, max(0.8, 0.8 + 0.5 * speed))
        if i in (10000, 20000, 27600, 30000, 40000):
            actual = arc_metrics(a, b, i / 40000)
            assert actual[0] == pytest.approx(distance, abs=3e-5)
            assert actual[1] == pytest.approx(cycles, abs=3e-5)
        previous = current


def test_metric_cache_is_bounded_and_eviction_cannot_change_seek_phase():
    from vmi.generator.physics import arc_metrics, _metric_curve, _metric_plan

    a = PathNode(0, 10, 20, 0)
    b = PathNode(3, 12, 20, 0)
    expected = arc_metrics(a, b, 0.537)
    for i in range(300):
        end = PathNode(3, 12 + (i + 1) * 0.001, 20, 0)
        arc_metrics(a, end, 0.3)
    assert _metric_curve.cache_info().currsize <= 256
    assert _metric_plan.cache_info().currsize <= 256
    assert all(len(_metric_curve(key)) <= 8 * 511 for key in ((3.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),))
    assert arc_metrics(a, b, 0.537) == expected
    nodes = through_velocities([a, b, PathNode(6, 14, 20, 0)])
    at = sample(nodes, 3)[2]
    for t in (3 - 1e-8, 3 + 1e-8):
        near = sample(nodes, t)[2]
        assert near["distance"] == pytest.approx(at["distance"], abs=1e-6)
        assert near["gait_cycles"] == pytest.approx(at["gait_cycles"], abs=1e-6)


def test_first_partial_query_builds_only_its_branch_and_all_nodes_are_bounded():
    from vmi.generator.physics import arc_metrics, _metric_curve, _metric_key

    a = PathNode(0, 50, 34, 0, -0.5502310440248639, 1.6246998777916524)
    b = PathNode(5.9167718405420375, 48.86507710453219, 36.7320476955137, 0, 2.3911157157975858, -1.395977939455939)
    _metric_curve.cache_clear()
    direct = arc_metrics(a, b, 0.537)
    curve = _metric_curve(_metric_key(a, b))
    assert 1 <= len(curve) <= 9
    for index in range(513):
        arc_metrics(a, b, index / 512)
    assert len(curve) <= 8 * 511
    assert arc_metrics(a, b, 0.537) == direct
    _metric_curve.cache_clear()
    arc_metrics(a, b, 0.9)
    arc_metrics(a, b, 0.1)
    assert arc_metrics(a, b, 0.537) == direct


def test_aggregate_node_budget_evicts_whole_curves_without_changing_seek(monkeypatch):
    from vmi.generator import physics

    cache = physics._CurveCache(max_nodes=16)
    monkeypatch.setattr(physics, "_metric_curve", cache)
    a, b = PathNode(0, 10, 20, 0, 0.2, 0), PathNode(3, 12, 21, 0, 0, 0.3)
    expected = physics.arc_metrics(a, b, 0.537)
    original = cache(physics._metric_key(a, b))
    for index in range(20):
        physics.arc_metrics(a, PathNode(3, 13 + index * 0.1, 21 + index * 0.03, 0, 0, 0.3), 0.537)
        assert cache.retained_nodes <= 16
        assert cache.retained_nodes == sum(len(entry[0]) for entry in cache.entries.values())
    assert all(entry[0] is not original for entry in cache.entries.values())
    misses = cache.cache_info().misses
    assert physics.arc_metrics(a, b, 0.537) == expected
    assert cache.cache_info().misses > misses


def test_finalized_metric_summary_is_immutable_reloadable_and_not_inferred_from_raw_distance(monkeypatch):
    import json
    from dataclasses import asdict, replace
    from vmi.generator import physics

    raw = [PathNode(0, 10, 20, 999), PathNode(3, 12, 21, 777, 0.2, 0)]
    assert sample(raw, 1.1)[2]["distance"] > 999
    assert raw[1].incoming_metrics is None
    nodes = through_velocities(raw)
    expected = sample(nodes, 1.1)[2]
    assert isinstance(nodes[1].incoming_metrics, tuple)
    restored = [PathNode(**json.loads(json.dumps(asdict(node)))) for node in nodes]
    assert isinstance(restored[1].incoming_metrics[2][0], tuple)
    assert sample(restored, 1.1)[2] == expected
    physics._metric_curve.cache_clear()
    monkeypatch.setattr(physics, "_metric_plan", lambda key: pytest.fail("reconstructed finalized source summary"))
    assert sample(restored, 1.1)[2] == expected
    # Geometry changes invalidate an old summary rather than reusing stale truth.
    with pytest.raises(pytest.fail.Exception, match="reconstructed"):
        sample([restored[0], replace(restored[1], x=13)], 1.1)


def test_zero_duration_source_nodes_do_not_construct_a_dividing_metric_summary():
    nodes = through_velocities([PathNode(0, 10, 20, 0), PathNode(0, 10, 20, 0), PathNode(2, 12, 20, 0)])
    assert nodes[1].incoming_metrics is None
    assert nodes[1].distance == nodes[1].gait_cycles == 0
    for t in (0, 0.5, 2):
        x, y, motion = sample(nodes, t)
        assert all(math.isfinite(value) for value in (x, y, motion["distance"], motion["gait_cycles"]))


@pytest.mark.parametrize("travelled", [0.0, 0.0001, 8.0, 19.2, 20.0])
def test_rest_endpoint_matches_independent_distance_and_cadence_across_stride_cap(travelled):
    from vmi.generator.physics import arc_metrics

    a, b = PathNode(0, 20, 34, 0), PathNode(4, 20 + travelled, 34, 0)
    assert certified(a, b)
    previous = sample([a, b], 0, distance=False)[:2]
    distance = cycles = 0.0
    dt = 4 / 10000
    for index in range(1, 10001):
        position = sample([a, b], index * dt, distance=False)[:2]
        step = math.dist(previous, position)
        distance += step
        cycles += step / min(4.4, 0.8 + 0.5 * step / dt)
        previous = position
    actual = arc_metrics(a, b)
    assert actual[0] == pytest.approx(distance, rel=1e-7, abs=1e-12)
    assert actual[1] == pytest.approx(cycles, rel=1e-7, abs=1e-12)


@pytest.mark.parametrize("travelled,start_speed,end_speed", [(8, 3, 3), (15, 3, 3), (0.0001, 0, 0)])
def test_collinear_partial_primitives_match_dense_travel_and_stay_monotone_near_endpoints(
    travelled, start_speed, end_speed
):
    from vmi.generator.physics import arc_metrics

    a = PathNode(0, 20, 34, 0, start_speed, 0)
    b = PathNode(5, 20 + travelled, 34, 0, end_speed, 0)
    assert certified(a, b)
    previous = sample([a, b], 0, distance=False)[:2]
    distance = cycles = 0.0
    dt = 5 / 20000
    for index in range(1, 20001):
        position = sample([a, b], index * dt, distance=False)[:2]
        step = math.dist(previous, position)
        distance += step
        cycles += step / min(4.4, 0.8 + 0.5 * step / dt)
        if index in (1000, 5000, 10000, 15000, 20000):
            actual = arc_metrics(a, b, index / 20000)
            assert actual[0] == pytest.approx(distance, abs=3e-5)
            assert actual[1] == pytest.approx(cycles, abs=3e-5)
        previous = position
    points = sorted({0.0, 1.0, *(10**-i for i in range(1, 13)), *(1 - 10**-i for i in range(1, 13))})
    values = [arc_metrics(a, b, u) for u in points]
    for left, right in zip(values, values[1:]):
        assert right[0] >= left[0] - 1e-12
        assert right[1] >= left[1] - 1e-12


def physical_fixture(ball_x=20, ball_y=30, holder="H9"):
    from vmi.generator.match import Match
    from vmi.generator.motion import Keyframe
    from vmi.generator.physics import stage_physical_players
    from vmi.generator.teams import make_teams

    teams = {
        side: {"players": [vars(p) | {"starter": True} for p in team.players]} for side, team in make_teams().items()
    }
    match = Match(
        {
            "match_id": "physical-test",
            "teams": teams,
            "motion_model": "source-paths-2",
            "seed": 12,
            "schema_version": "2.0",
            "end_t": 6,
            "final_score": {"home": 0, "away": 0},
        },
        events=[
            {
                "id": "p1",
                "type": "pass",
                "t": 4.0,
                "delivered_t": 4.75,
                "period": 1,
                "clock": "0:04",
                "source": "event_feed",
                "schema_version": "2.0",
                "match_id": "physical-test",
                "team": "home" if holder.startswith("H") else "away",
                "player_id": holder,
                "pass": {"outcome": "complete"},
            }
        ],
        keyframes=[
            Keyframe(0, ball_x, ball_y, holder, True),
            Keyframe(2, ball_x + 4, ball_y, holder, True),
            Keyframe(4, ball_x + 8, ball_y, holder, True),
            Keyframe(6, ball_x + 16, ball_y, None, True),
        ],
    )
    stage_physical_players(match)
    return match


def test_observation_frame_contact_and_seek_share_one_physical_source(monkeypatch):
    from vmi.contracts import validate_record
    from vmi.generator.tracking import Tracker

    match = physical_fixture()
    tracker = Tracker(match)
    expected = tracker.frame(1.5)
    from vmi.generator import physics

    def forbidden_integral(*args, **kwargs):
        raise AssertionError("lightweight engine observation must not integrate visual gait")

    with monkeypatch.context() as scoped:
        scoped.setattr(physics, "arc_metrics", forbidden_integral)
        observation = tracker.observation(1.5)
    assert observation["ball"] == expected["ball"]
    holder = next(p for p in expected["players"] if p["id"] == "H9")
    assert observation["players"] == [{k: v for k, v in holder.items() if k not in {"motion", "contact"}}]
    assert observation["ball_height"] == expected["ball_height"]
    assert observation["possession"] == expected["possession"]
    assert observation["ball_in_play"] == expected["ball_in_play"]
    assert math.dist(expected["ball"], (holder["x"], holder["y"])) == pytest.approx(0.55, abs=0.015)
    assert holder["contact"]["target"] == pytest.approx([*expected["ball"], expected["ball_height"]], abs=0.01)
    tracker.frame(6)
    tracker.frame(0)
    assert tracker.frame(1.5) == expected == Tracker(match).frame(1.5)
    assert next(p for p in tracker.frame(3.99)["players"] if p["id"] == "H9")["contact"]["kind"] == "control"
    released = next(p for p in tracker.frame(4.1)["players"] if p["id"] == "H9")["contact"]
    assert released["kind"] == "release" and released["start_t"] == 4
    assert released["phase"] == pytest.approx(0.3125)
    assert "contact" not in next(p for p in tracker.frame(4.32)["players"] if p["id"] == "H9")
    validate_record(expected, "physical-test")


def test_low_defensive_full_tracking_snapshot_keeps_midfield_and_outlets():
    from vmi.generator.tracking import Tracker

    match = physical_fixture(6, 30, "A9")
    # The ball starts near the home goal in the opponent's possession.
    frame = Tracker(match).frame(0)
    home = {p["role"]: p for p in frame["players"] if p["team"] == "home"}
    assert home["ST"]["x"] >= 25 and home["RW"]["x"] >= 20
    assert home["CM"]["x"] >= 15 and home["CB"]["x"] < home["DM"]["x"] < home["ST"]["x"]
    assert len(frame["players"]) == 22


def test_physical_source_rejects_an_unreachable_contact_instead_of_clamping_it():
    from vmi.generator.motion import Keyframe
    from vmi.generator.physics import stage_physical_players

    match = physical_fixture()
    match.player_paths.clear()
    match.keyframes = [Keyframe(0, 20, 30, "H9", True), Keyframe(1, 40, 30, "H9", True)]
    with pytest.raises(ValueError, match="unreachable physical source contact: H9"):
        stage_physical_players(match)


def test_optional_support_knot_cannot_force_an_impossible_intermediate_stop():
    from vmi.generator.motion import Keyframe
    from vmi.generator.physics import stage_physical_players

    match = physical_fixture()
    match.player_paths.clear()
    match.keyframes = [
        Keyframe(0, 20, 30, "H9", True),
        Keyframe(3, 36, 30, None, True),
        Keyframe(7, 56, 30, "H9", True),
    ]
    stage_physical_players(match)
    assert [n.t for n in match.player_paths["H9"]] == [0, 7]
    assert 6 < sample(match.player_paths["H9"], 3)[2]["speed"] <= 9


@pytest.mark.parametrize(
    "change",
    [
        {"start_t": 10},
        {"end_t": -1},
        {"phase": 1.1},
        {"target": [1, 2]},
        {"target": [1, 2, -1]},
        {"target": [1000000, 2, 0]},
        {"target": [1, 1000000, 0]},
        {"target": [1, 2, 31]},
        {"phase": 1},
        {"kind": "control"},
        {"effector": "unknown"},
        {"outcome": "goal"},
    ],
)
def test_invalid_or_future_contact_cannot_cross_the_runtime_contract(change):
    from vmi.contracts import validate_record

    contact = {
        "kind": "release",
        "effector": "foot",
        "start_t": 1.0,
        "end_t": 1.32,
        "phase": 0.3125,
        "target": [20.0, 30.0, 0.0],
        "heading": 0.0,
    }
    contact.update(change)
    frame = {
        "schema_version": "2.0",
        "stream": "tracking",
        "match_id": "m",
        "t": 1.1,
        "players": [{"contact": contact}],
    }
    with pytest.raises(ValueError, match="source player contact"):
        validate_record(frame, "m")


def test_restart_arrival_does_not_restore_the_takers_stale_encounter_position():
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    sim = _Sim(12, "restart-prior-contact")
    taker = sim.nearest("home", 52.5, 34)
    sim.key("home", 20, 34, None, False)
    sim.keyframes[-1].player_positions[taker.id] = (10, 34)
    sim.t = 30
    sim.kick_off("home")
    action = next(e for e in sim.events if e["type"] == "set_piece")
    tracker = Tracker(sim.export_match())
    release = next(p for p in tracker.frame(action["t"])["players"] if p["id"] == taker.id)
    arrival = next(p for p in tracker.frame(sim.t)["players"] if p["id"] == taker.id)
    assert math.dist((release["x"], release["y"]), (arrival["x"], arrival["y"])) < 1.2


@pytest.mark.parametrize("side", ["home", "away"])
def test_throw_is_a_hand_contact_at_height_before_another_players_receipt(side):
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    sim = _Sim(12, "physical-throw")
    sim.t = 10
    sim.key(side, 60, 0, None, False)
    sim.throw_in(side, 60, 0)
    action = next(e for e in sim.events if e["type"] == "set_piece")
    tracker = Tracker(sim.export_match())
    release = tracker.frame(action["t"])
    player = next(p for p in release["players"] if p["id"] == action["player_id"])
    assert release["ball_height"] == pytest.approx(1.7)
    assert player["contact"]["kind"] == "throw" and player["contact"]["effector"] == "hands"
    assert player["contact"]["target"][2] == pytest.approx(1.7)
    assert tracker.frame(sim.t)["possession"]["holder_id"] != action["player_id"]


@pytest.mark.parametrize("draw,expected", [(0.2, "saved"), (0.45, "blocked")])
def test_save_and_block_have_a_real_actor_at_contact_before_rebound(draw, expected):
    import random
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    class Draw(random.Random):
        def random(self):
            return draw

    sim = _Sim(12, "physical-shot-contact")
    shooter = next(p for p in sim.on_pitch["home"] if p.position == "ST")
    sim.t = 10
    sim.ball_in_play = True
    sim.key("home", 94, 34, shooter)
    sim.rng = Draw(1)
    sim.true_chance = lambda *args: 0
    sim.corner = lambda *args: None  # inspect this rebound, not a subsequent attack
    sim.shot("home", shooter, 94, 34, None)
    result = next(e for e in sim.events if e["type"] == "shot_result")
    assert result["outcome"] == expected
    touch = next(e for e in sim.events if e["type"] == ("save" if expected == "saved" else "block"))
    tracker = Tracker(sim.export_match())
    frame = tracker.frame(touch["t"])
    actor = next(p for p in frame["players"] if p["id"] == touch["player_id"])
    assert actor["contact"]["kind"] == ("save" if expected == "saved" else "block")
    assert actor["contact"]["target"][0] == pytest.approx(102 if expected == "saved" else 96)
    assert math.dist(frame["ball"], (actor["x"], actor["y"])) == pytest.approx(0.55, abs=0.015)
    assert tracker.frame(touch["t"] + 0.1)["ball"] != frame["ball"]


def test_developer_fixture_preserves_physical_paths_separately_from_delivered_frames(tmp_path, monkeypatch):
    import json
    from vmi.generator import fixtures
    from vmi.generator.match import Match
    from vmi.generator.motion import Keyframe
    from vmi.generator.tracking import Tracker

    match = physical_fixture()
    match.keyframes[0].player_facings = (("H9", 0.25),)
    monkeypatch.setattr(fixtures, "generate_scenario", lambda *args: match)
    assert fixtures.export_fixture("physical", 12, tmp_path)["status"] == "PASS"
    directory = tmp_path / "physical"
    rows = lambda file: [json.loads(line) for line in (directory / file).read_text().splitlines()]
    paths = {row["player_id"]: [PathNode(**node) for node in row["nodes"]] for row in rows("player-paths.jsonl")}
    restored = Match(
        json.loads((directory / "meta.json").read_text()),
        events=rows("events.jsonl"),
        keyframes=[Keyframe(**row) for row in rows("keyframes.jsonl")],
        player_paths=paths,
    )
    assert restored.keyframes[0].player_facings == (("H9", 0.25),)
    assert isinstance(restored.keyframes[0].player_facings, tuple)
    for t in (0, 1.5, 4.1, 6):
        assert Tracker(restored).frame(t) == Tracker(match).frame(t)
    delivered = rows("tracking-20hz.jsonl")
    assert delivered[30] == Tracker(match).frame(1.5)
    assert "player_paths" not in delivered[30]


def test_receiver_readiness_delays_cross_release_without_stretching_flight():
    import random
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    class Mid(random.Random):
        def random(self):
            return 0.1

        def uniform(self, a, b):
            return (a + b) / 2

    sim = _Sim(12, "reachable-cross")
    holder = next(p for p in sim.on_pitch["home"] if p.id == "H9")
    receiver = next(p for p in sim.on_pitch["home"] if p.id == "H2")
    sim.ball_in_play = True
    sim.key("home", 80, 10, holder)
    sim.keyframes[-1].player_positions[receiver.id] = (10, 34)
    sim.t = 0.1
    sim.key("home", 80, 10, holder)
    sim.nearest = lambda *a, **kw: receiver
    sim.rng = Mid(1)
    sim.pass_("home", holder, 80, 10, 0.5)
    event = next(e for e in sim.events if e["type"] == "pass")
    assert event["t"] > 10
    assert sim.t - event["t"] == pytest.approx(0.5 + math.hypot(16, 24) / 16, abs=0.01)
    assert event["delivered_t"] >= sim.t
    tracker = Tracker(sim.export_match())
    for t in (1, event["t"] - 0.01):
        frame = tracker.frame(t)
        assert frame["ball"] == pytest.approx([80, 10], abs=0.01)
        assert frame["ball_height"] == 0
        assert frame["possession"]["holder_id"] == holder.id


def test_stopped_ball_moves_only_with_a_reachable_active_retriever():
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    sim = _Sim(12, "actual-retrieval")
    sim.key("home", 100, 34, None, False)
    taker = sim.nearest("home", 52.5, 34)
    sim.keyframes[-1].player_positions[taker.id] = (10, 34)
    sim.t = 20
    sim.set_restart_ball("home", 52.5, 34, taker)
    tracker = Tracker(sim.export_match())
    moved = 0
    previous = tracker.frame(20)
    for i in range(1, math.floor((sim.t - 20) * 20) + 1):
        current = tracker.frame(20 + i / 20)
        assert not current["ball_in_play"]
        if math.dist(current["ball"], previous["ball"]) > 0.01:
            moved += 1
            actor = next(p for p in current["players"] if p["id"] == taker.id)
            assert math.dist(current["ball"], (actor["x"], actor["y"])) == pytest.approx(0.55, abs=0.02)
            assert actor["contact"]["effector"] == "hands"
        previous = current
    assert moved > 20
    assert tracker.frame(sim.t - 0.5)["ball"] == tracker.frame(sim.t)["ball"]


def test_ordinary_foul_has_reachable_two_player_encounter_before_whistle():
    import random
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    class Half(random.Random):
        def random(self):
            return 0.5

    sim = _Sim(12, "actual-foul")
    victim = next(p for p in sim.on_pitch["home"] if p.id == "H9")
    fouler = sim.opp_nearest("home", 60, 34)
    sim.ball_in_play = True
    sim.key("home", 60, 34, victim)
    sim.keyframes[-1].player_positions[fouler.id] = (10, 10)
    sim.t = 1
    sim.key("home", 60, 34, victim)
    sim.rng = Half(1)
    sim.stoppage = lambda *a: None
    sim.restart_free_kick = lambda *a: None
    sim.foul("home", victim, 60, 34)
    event = next(e for e in sim.events if e["type"] == "foul")
    assert event["t"] > 9
    tracker = Tracker(sim.export_match())
    frame = tracker.frame(event["t"])
    actors = {p["id"]: p for p in frame["players"]}
    assert (
        0.8
        < math.dist((actors[victim.id]["x"], actors[victim.id]["y"]), (actors[fouler.id]["x"], actors[fouler.id]["y"]))
        < 1.3
    )
    assert actors[fouler.id]["contact"]["kind"] == "challenge"
    assert frame["possession"]["holder_id"] == victim.id
    assert next(e for e in sim.events if e["type"] == "whistle")["t"] > event["t"]


@pytest.mark.parametrize("side", ["home", "away"])
def test_handball_is_an_actual_high_hand_contact_after_a_chip_and_before_stopping(side):
    import random
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    class Half(random.Random):
        def random(self):
            return 0.5

    sim = _Sim(12, "actual-handball")
    victim = next(p for p in sim.on_pitch[side] if p.position == "ST")
    fouler = sim.opp_nearest(side, 60, 34)
    sim.ball_in_play = True
    sim.key(side, 60, 34, victim)
    sim.keyframes[-1].player_positions[fouler.id] = (10, 10)
    sim.t = 1
    sim.key(side, 60, 34, victim)
    sim.rng = Half(1)
    sim.detail_rng.random = lambda: 0
    sim.card_maybe = lambda *a, **kw: None
    sim.stoppage = lambda *a: None
    sim.restart_free_kick = lambda *a: None
    sim.foul(side, victim, 60, 34)
    handball = next(e for e in sim.events if e["type"] == "handball")
    attempted = next(e for e in sim.events if e["type"] == "pass")
    whistle = next(e for e in sim.events if e["type"] == "whistle")
    assert handball["t"] - attempted["t"] == pytest.approx(0.45)
    assert attempted["pass"]["outcome"] == "incomplete"
    assert attempted["delivered_t"] >= handball["t"]
    tracker = Tracker(sim.export_match())
    before = tracker.frame(attempted["t"] - 0.05)
    assert before["ball_height"] == 0 and before["possession"]["holder_id"] == victim.id
    release = tracker.frame(attempted["t"])
    assert next(p for p in release["players"] if p["id"] == victim.id)["contact"]["kind"] == "release"
    mid = tracker.frame(attempted["t"] + 0.225)
    assert 0.5 < mid["ball_height"] < 1.1
    impact = tracker.frame(handball["t"])
    actor = next(p for p in impact["players"] if p["id"] == fouler.id)
    assert impact["ball_height"] == pytest.approx(1.1)
    assert impact["possession"].get("holder_id") is None
    assert actor["contact"]["kind"] == "challenge" and actor["contact"]["effector"] == "hands"
    assert actor["contact"]["target"] == pytest.approx([*impact["ball"], 1.1])
    assert math.dist((actor["x"], actor["y"]), impact["ball"]) == pytest.approx(0.55, abs=0.015)
    after = tracker.frame(handball["t"] + 0.15)
    assert 0 < after["ball_height"] < 1.1 and after["ball"] != impact["ball"]
    assert whistle["t"] > handball["t"] and tracker.frame(whistle["t"])["ball_height"] == 0


@pytest.mark.parametrize("side", ["home", "away"])
def test_handball_award_uses_actual_contact_when_chip_crosses_into_the_box(side):
    import random
    from vmi.generator.match import _Sim, BOX_X

    class Half(random.Random):
        def random(self):
            return 0.5

    sim = _Sim(12, "handball-box-boundary")
    victim = next(p for p in sim.on_pitch[side] if p.position == "ST")
    sim.ball_in_play = True
    sim.key(side, BOX_X - 1, 34, victim)
    sim.rng = Half(1)
    sim.detail_rng.random = lambda: 0
    sim.card_maybe = lambda *a, **kw: None
    sim.stoppage = lambda *a: None
    taken = []
    sim.penalty = lambda side: taken.append(side)
    sim.foul(side, victim, BOX_X - 1, 34)
    event = next(e for e in sim.events if e["type"] == "handball")
    decision = next(e for e in sim.events if e["type"] == "referee_decision")
    from vmi.generator.tracking import Tracker

    impact = Tracker(sim.export_match()).frame(event["t"])
    local = impact["ball"][0] if side == "home" else 105 - impact["ball"][0]
    assert local == pytest.approx(BOX_X + 0.5)
    assert decision["trigger_event_id"] == event["id"] and decision["decision"] == "penalty"
    assert taken == [side]


def test_source_wait_copies_effector_snapshots_before_a_later_release_changes_them():
    from vmi.generator.match import _Sim

    sim = _Sim(12, "snapshot-effectors")
    keeper = sim.keeper("home")
    sim.key("home", 5, 34, keeper, False, effector="hands")
    first = sim.keyframes[-1]
    sim.hold_until(2)
    sim.keyframes[-1].contact_effectors[keeper.id] = "foot"
    assert first.contact_effectors[keeper.id] == "hands"


@pytest.mark.parametrize("action", ["restart", "save"])
def test_distant_encounter_does_not_slow_a_restart_or_shot(action):
    import random
    from vmi.generator.match import _Sim
    from vmi.generator.tracking import Tracker

    class Draw(random.Random):
        def random(self):
            return 0.2

    sim = _Sim(12, "ready-before-release")
    shooter = next(p for p in sim.on_pitch["home"] if p.id == "H9")
    receiver = sim.keeper("away") if action == "save" else next(p for p in sim.on_pitch["home"] if p.id == "H2")
    ax = 94 if action == "save" else 60
    sim.ball_in_play = True
    sim.key("home", ax, 34, shooter)
    sim.keyframes[-1].player_positions[receiver.id] = (10, 34)
    sim.t = 0.1
    sim.key("home", ax, 34, shooter)
    sim.rng = Draw(1)
    if action == "save":
        sim.true_chance = lambda *a: 0
        sim.corner = lambda *a: None
        sim.stoppage = lambda *a: None
        sim.shot("home", shooter, ax, 34, None)
        departure = next(e for e in sim.events if e["type"] == "shot")["t"]
        arrival = next(e for e in sim.events if e["type"] == "save")["t"]
        duration = 0.6
    else:
        sim.nearest = lambda *a, exclude=None, **kw: receiver if exclude else shooter
        sim.restart_pass("home", "free_kick", ax, 34)
        departure = next(e for e in sim.events if e["type"] == "set_piece")["t"]
        arrival = sim.t
        duration = math.hypot(9, 6) / 12
    assert departure > 8
    assert arrival - departure == pytest.approx(duration, abs=0.01)
    tracker = Tracker(sim.export_match())
    assert tracker.frame(departure - 0.05)["ball_height"] == 0


def test_repeated_centimetre_quantized_contact_needs_no_fictitious_approach():
    from vmi.generator.match import _Sim

    sim = _Sim(12, "quantized-repeat")
    holder = sim.on_pitch["home"][0]
    sim.key("home", 25.1234, 30.4567, holder)
    assert sim.contact_ready(holder, (25.1234, 30.4567), sim.t) == sim.t
