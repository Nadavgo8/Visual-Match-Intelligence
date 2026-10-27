"""Deterministic metric trajectories, planned before delivered tracking is sampled."""

from bisect import bisect_right
from dataclasses import dataclass, replace
from functools import lru_cache
import math

from .motion import PLAYER_SPEED, _in_disk, _reachable_target, support_position

PLAYER_ACCELERATION = 8.0  # engineering bound, not a calibrated athlete model
BODY_TURN_SPEED = 6.0  # radians/source second; separate from velocity direction
CONTACT_REACH = 0.55  # horizontal root-to-contact separation, metres
PEAK_RATE = 1.5  # exact peak rate of a cubic rest-to-rest trajectory
PEAK_ACCELERATION = 6.0


def travel_time(distance):
    """Conservative setup time; through-velocity is preserved by the path planner."""
    return max(PEAK_RATE * distance / PLAYER_SPEED, math.sqrt(PEAK_ACCELERATION * distance / PLAYER_ACCELERATION))


def reach(duration):
    duration = max(0, duration)
    return min(PLAYER_SPEED * duration / PEAK_RATE, PLAYER_ACCELERATION * duration * duration / PEAK_ACCELERATION)


@dataclass(frozen=True)
class PathNode:
    t: float
    x: float
    y: float
    distance: float
    vx: float = 0
    vy: float = 0
    heading: float | None = None
    facing: float | None = None
    gait_cycles: float = 0


def progress(u):
    return u * u * (3 - 2 * u)


def velocity(a, b, u):
    dt = b.t - a.t
    if dt <= 0:
        return 0.0, 0.0
    chord = 6 * u * (1 - u) / dt
    left, right = 3 * u * u - 4 * u + 1, 3 * u * u - 2 * u
    return (chord * (b.x - a.x) + left * a.vx + right * b.vx, chord * (b.y - a.y) + left * a.vy + right * b.vy)


def certified(a, b):
    dt = b.t - a.t
    if dt < 0 or any(not 0 <= p.x <= 105 or not 0 <= p.y <= 68 for p in (a, b)):
        return False
    if dt <= 0:
        return math.dist((a.x, a.y), (b.x, b.y)) < 1e-7
    delta = ((b.x - a.x) / dt, (b.y - a.y) / dt)
    if any(
        not 0 <= x <= 105 or not 0 <= y <= 68
        for x, y in ((a.x + a.vx * dt / 3, a.y + a.vy * dt / 3), (b.x - b.vx * dt / 3, b.y - b.vy * dt / 3))
    ):
        return False
    controls = [(a.vx, a.vy), (3 * delta[0] - a.vx - b.vx, 3 * delta[1] - a.vy - b.vy), (b.vx, b.vy)]
    if max(math.dist(controls[i + 1], controls[i]) * 2 / dt for i in (0, 1)) > PLAYER_ACCELERATION + 1e-7:
        return False
    if max(math.hypot(*v) for v in controls) <= PLAYER_SPEED + 1e-7:
        return True
    # v(u)=Au²+Bu+C. Extrema of |v|² are the real roots of v·dv/du.
    aa = tuple(controls[0][i] - 2 * controls[1][i] + controls[2][i] for i in (0, 1))
    bb = tuple(2 * (controls[1][i] - controls[0][i]) for i in (0, 1))
    cc = controls[0]
    dot = lambda x, y: sum(p * q for p, q in zip(x, y))
    roots = unit_roots((2 * dot(aa, aa), 3 * dot(aa, bb), dot(bb, bb) + 2 * dot(aa, cc), dot(bb, cc)))
    return max(math.hypot(*velocity(a, b, u)) for u in [0, 1, *roots]) <= PLAYER_SPEED + 1e-7


def unit_roots(coefficients):
    """All cubic roots in [0,1], isolated on monotone derivative intervals."""
    a, b, c, d = coefficients
    cuts = [0.0, 1.0]
    if abs(a) > 1e-12:
        discriminant = 4 * b * b - 12 * a * c
        if discriminant >= 0:
            root = math.sqrt(discriminant)
            cuts.extend(x for x in ((-2 * b - root) / (6 * a), (-2 * b + root) / (6 * a)) if 0 < x < 1)
    elif abs(b) > 1e-12:
        x = -c / (2 * b)
        if 0 < x < 1:
            cuts.append(x)
    cuts = sorted(set(cuts))
    evaluate = lambda x: ((a * x + b) * x + c) * x + d
    roots = [x for x in cuts if abs(evaluate(x)) < 1e-10]
    for lo, hi in zip(cuts, cuts[1:]):
        left = evaluate(lo)
        if left * evaluate(hi) >= 0:
            continue
        for _ in range(36):
            mid = (lo + hi) / 2
            if left * evaluate(mid) <= 0:
                hi = mid
            else:
                lo = mid
        roots.append((lo + hi) / 2)
    return roots


# Eight-point Gaussian quadrature of metric speed, deterministic and bounded.
_GAUSS = (
    (-0.9602898564975363, 0.1012285362903763),
    (-0.7966664774136267, 0.2223810344533745),
    (-0.5255324099163290, 0.3137066458778873),
    (-0.1834346424956498, 0.3626837833783620),
    (0.1834346424956498, 0.3626837833783620),
    (0.5255324099163290, 0.3137066458778873),
    (0.7966664774136267, 0.2223810344533745),
    (0.9602898564975363, 0.1012285362903763),
)


def _quadrature(coefficients, lo, hi):
    aa, bb, cc, dd, ee, ff, inverse_dt, rest = coefficients
    distance, cycles = 0.0, 0.0
    for x, weight in _GAUSS:
        u = lo + (hi - lo) * (x + 1) / 2
        rate = (
            6 * u * (1 - u) * rest if rest is not None else math.hypot((aa * u + bb) * u + cc, (dd * u + ee) * u + ff)
        )
        distance += weight * rate
        cycles += weight * rate / min(4.4, 0.8 + 0.5 * rate * inverse_dt)
    scale = (hi - lo) / 2
    return scale * distance, scale * cycles


def _metric_key(a, b):
    # Translation cannot change distance/cadence; identical local curves share
    # a cache entry even when they belong to different actors or pitch areas.
    return b.t - a.t, b.x - a.x, b.y - a.y, a.vx, a.vy, b.vx, b.vy


def _metric_coefficients(key):
    dt, dx, dy, avx, avy, bvx, bvy = key
    return (
        -6 * dx + 3 * dt * (avx + bvx),
        6 * dx - dt * (4 * avx + 2 * bvx),
        dt * avx,
        -6 * dy + 3 * dt * (avy + bvy),
        6 * dy - dt * (4 * avy + 2 * bvy),
        dt * avy,
        1 / dt,
        math.hypot(dx, dy) if avx == avy == bvx == bvy == 0 else None,
    )


@lru_cache(maxsize=256)
def _metric_total(key):
    """Accurate canonical endpoint; source planning need not build partial tables."""
    coefficients = _metric_coefficients(key)
    rest = coefficients[-1]
    if rest == 0:
        return 0.0, 0.0

    def integrate(lo, hi, whole, depth):
        mid = (lo + hi) / 2
        left, right = _quadrature(coefficients, lo, mid), _quadrature(coefficients, mid, hi)
        fine = tuple(x + y for x, y in zip(left, right))
        if depth == 8 or all(
            abs(fine[i] - whole[i]) <= tolerance * (hi - lo) for i, tolerance in enumerate((1e-6, 1e-7))
        ):
            return fine
        first, last = integrate(lo, mid, left, depth + 1), integrate(mid, hi, right, depth + 1)
        return tuple(x + y for x, y in zip(first, last))

    cuts = [0.0, 1.0]
    if rest is not None and 1.5 * rest / key[0] > 7.2:
        root = math.sqrt(1 - 4 * 7.2 * key[0] / (6 * rest))
        cuts = [0.0, (1 - root) / 2, (1 + root) / 2, 1.0]
    parts = [integrate(lo, hi, _quadrature(coefficients, lo, hi), 0) for lo, hi in zip(cuts, cuts[1:])]
    return (rest if rest is not None else sum(p[0] for p in parts), sum(p[1] for p in parts))


def _positive_integral(fraction, width, total, left, right):
    # With endpoint slopes in [0,3*mean], every corner of this Hermite
    # derivative's affine slope domain is nonnegative: no backwards phase.
    ceiling = 3 * total / width
    left, right = min(ceiling, max(0, left)), min(ceiling, max(0, right))
    u = fraction
    value = total * progress(u) + width * (left * u * (1 - u) ** 2 - right * u * u * (1 - u))
    return min(total, max(0, value))


@lru_cache(maxsize=256)
def _metric_curve(key):
    """At most 256 positive cells; bounded cache, independent of viewer history."""
    coefficients = _metric_coefficients(key)
    cells = []
    rates = {}

    def rate(u):
        cached = rates.get(u)
        if cached is not None:
            return cached
        aa, bb, cc, dd, ee, ff, inverse_dt, rest = coefficients
        value = (
            6 * u * (1 - u) * rest if rest is not None else math.hypot((aa * u + bb) * u + cc, (dd * u + ee) * u + ff)
        )
        result = value, value / min(4.4, 0.8 + 0.5 * value * inverse_dt)
        rates[u] = result
        return result

    def divide(lo, hi, whole, depth):
        width = hi - lo
        # Positive Simpson cells reuse dyadic samples across subdivision. This
        # avoids dozens of fresh Gauss evaluations on every cold render segment.
        values = [rate(lo + width * j / 8) for j in range(9)]
        quarters = [
            tuple(width / 24 * (values[2 * j][i] + 4 * values[2 * j + 1][i] + values[2 * j + 2][i]) for i in (0, 1))
            for j in range(4)
        ]
        total = tuple(sum(q[i] for q in quarters) for i in (0, 1))
        left, right = rate(lo), rate(hi)
        accurate = all(abs(total[i] - whole[i]) <= tol * width for i, tol in enumerate((1e-6, 1e-7)))
        for j in (1, 2, 3):
            for i, tol in enumerate((1e-5, 1e-5)):
                expected = sum(q[i] for q in quarters[:j])
                if abs(_positive_integral(j / 4, width, total[i], left[i], right[i]) - expected) > tol:
                    accurate = False
        if accurate or depth == 8:
            cells.append((lo, hi, total, left, right))
        else:
            mid = (lo + hi) / 2
            divide(lo, mid, tuple(quarters[0][i] + quarters[1][i] for i in (0, 1)), depth + 1)
            divide(mid, hi, tuple(quarters[2][i] + quarters[3][i] for i in (0, 1)), depth + 1)

    divide(0.0, 1.0, _metric_total(key), 0)
    # Partial and full requests use exactly the same cached canonical endpoint.
    approximate = tuple(sum(cell[2][i] for cell in cells) for i in (0, 1))
    canonical = _metric_total(key)
    factors = tuple(canonical[i] / approximate[i] if approximate[i] else 0 for i in (0, 1))
    cumulative = [0.0, 0.0]
    table = []
    for lo, hi, total, left, right in cells:
        total = tuple(total[i] * factors[i] for i in (0, 1))
        left, right = (tuple(value[i] * factors[i] for i in (0, 1)) for value in (left, right))
        table.append((hi, lo, tuple(cumulative), total, left, right))
        cumulative = [cumulative[i] + total[i] for i in (0, 1)]
    return tuple(table)


def arc_metrics(a, b, u=1):
    if b.t <= a.t or u <= 0:
        return 0.0, 0.0
    key = _metric_key(a, b)
    if u >= 1:
        return _metric_total(key)
    table = _metric_curve(key)
    cell = table[min(bisect_right(table, u, key=lambda cell: cell[0]), len(table) - 1)]
    hi, lo, prefix, total, left, right = cell
    return tuple(
        prefix[i] + _positive_integral((u - lo) / (hi - lo), hi - lo, total[i], left[i], right[i]) for i in (0, 1)
    )


def arc_length(a, b, u=1):
    return arc_metrics(a, b, u)[0]


def through_velocities(nodes):
    """Keep shared nonzero tangents through runs, with certified braking at turns."""
    for i in range(1, len(nodes) - 1):
        a, b, c = nodes[i - 1 : i + 2]
        dt, future = b.t - a.t, c.t - b.t
        if dt <= 0 or future <= 0:
            continue
        incoming = ((b.x - a.x) / dt, (b.y - a.y) / dt)
        outgoing = ((c.x - b.x) / future, (c.y - b.y) / future)
        if sum(x * y for x, y in zip(incoming, outgoing)) <= 0:
            continue
        wanted = tuple((x * future + y * dt) / (dt + future) for x, y in zip(incoming, outgoing))
        candidate = PathNode(b.t, b.x, b.y, 0, *wanted)
        if certified(a, candidate) and certified(candidate, c):
            nodes[i] = candidate
            continue
        lo, hi = 0.0, 1.0
        for _ in range(10):
            scale = (lo + hi) / 2
            candidate = PathNode(b.t, b.x, b.y, 0, wanted[0] * scale, wanted[1] * scale)
            if certified(a, candidate) and certified(candidate, c):
                lo = scale
            else:
                hi = scale
        nodes[i] = PathNode(b.t, b.x, b.y, 0, wanted[0] * lo, wanted[1] * lo)
    total, cycles = 0.0, 0.0
    heading = None
    facing = next(
        (
            math.atan2(b.x - a.x, a.y - b.y)
            for a, b in zip(nodes, nodes[1:])
            if math.dist((a.x, a.y), (b.x, b.y)) > 1e-8
        ),
        None,
    )
    for i, node in enumerate(nodes):
        if i:
            previous = nodes[i - 1]
            length, turns = arc_metrics(previous, node)
            total += length
            cycles += turns
            if math.dist((previous.x, previous.y), (node.x, node.y)) > 1e-8:
                heading = math.atan2(node.x - previous.x, previous.y - node.y)
            if facing is not None and heading is not None:
                delta = math.atan2(math.sin(heading - facing), math.cos(heading - facing))
                allowed = BODY_TURN_SPEED * (node.t - previous.t) / 1.5
                facing += min(allowed, max(-allowed, delta))
                facing = math.atan2(math.sin(facing), math.cos(facing))
        elif len(nodes) > 1:
            dx, dy = nodes[1].x - node.x, nodes[1].y - node.y
            if math.hypot(dx, dy) > 1e-8:
                facing = math.atan2(dx, -dy)
        if facing is None:
            facing = heading
        nodes[i] = replace(node, distance=total, heading=heading, facing=facing, gait_cycles=cycles)
    return nodes


def sample(nodes, t, *, distance=True):
    index = max(0, bisect_right(nodes, t, key=lambda node: node.t) - 1)
    a = nodes[index]
    b = nodes[min(index + 1, len(nodes) - 1)]
    dt = b.t - a.t
    u = min(1, max(0, (t - a.t) / dt)) if dt > 0 else 0
    fraction = progress(u)
    vx, vy = velocity(a, b, u)
    x = a.x + (b.x - a.x) * fraction + dt * (a.vx * u * (1 - u) ** 2 - b.vx * u * u * (1 - u))
    y = a.y + (b.y - a.y) * fraction + dt * (a.vy * u * (1 - u) ** 2 - b.vy * u * u * (1 - u))
    facing = a.facing
    if facing is not None and b.facing is not None:
        delta = math.atan2(math.sin(b.facing - facing), math.cos(b.facing - facing))
        facing += delta * fraction
        facing = math.atan2(math.sin(facing), math.cos(facing))
    length, cycles = arc_metrics(a, b, u) if distance else (0, 0)
    return (
        x,
        y,
        {
            "heading": math.atan2(vx, -vy) if math.hypot(vx, vy) > 1e-8 else a.heading,
            "speed": math.hypot(vx, vy),
            "distance": a.distance + length,
            "gait_cycles": a.gait_cycles + cycles,
            "facing": facing,
        },
    )


def stage_physical_players(match):
    """Plan body roots and C1 paths; ball/contact coordinates remain separate.

    Explicit touches constrain paths. Intermediate support nodes are optional,
    so incidental ball bookkeeping cannot force a stop or impossible reversal.
    Every stored segment has an analytic speed and acceleration certificate.
    """
    # Ball bookkeeping at one timestamp must not erase an actual touch which
    # preceded the whistle/release state at that same instant.
    by_time = {}
    for key in match.keyframes:
        previous = by_time.get(key.t)
        positions = dict(previous.player_positions) if previous else {}
        effectors = dict(previous.contact_effectors) if previous else {}
        positions.update(key.player_positions)
        effectors.update(key.contact_effectors)
        if key.holder:
            positions[key.holder] = (key.x, key.y)
        by_time[key.t] = replace(key, player_positions=positions, contact_effectors=effectors)
    knots = sorted(by_time.values(), key=lambda k: k.t)
    if not knots:
        return
    players = [dict(p) for team in match.meta["teams"].values() for p in team["players"]]
    by_id = {p["id"]: p for p in players}
    for event in match.events:
        if event["type"] == "substitution":
            change = event["substitution"]
            off, on = by_id[change["off_id"]], by_id[change["on_id"]]
            on["base_x"], on["base_y"] = off["base_x"], off["base_y"]
            if off["position"] == "GK":
                on["position"] = "GK"
    period2 = next(
        (e["t"] for e in match.events if e["type"] == "period_start" and e["period_start"]["period_no"] == 2), math.inf
    )
    owner = None
    owners = []
    for k in knots:
        owner = by_id[k.holder]["team"] if k.holder else owner if k.in_play else None
        owners.append(owner)
    for player in players:
        pid = player["id"]
        anchors = {}
        last_touch, last_offset = None, None
        for i, k in enumerate(knots):
            position = (k.x, k.y) if k.holder == pid else k.player_positions.get(pid)
            if position is None:
                continue
            # Event coordinates retain precision while ball keys are quantized
            # to centimetres. Explicit effectors identify the same actual touch.
            touching = k.holder == pid or (pid in k.contact_effectors and math.dist(position, (k.x, k.y)) < 0.01)
            if touching:
                position = (k.x, k.y)
                ahead = knots[min(i + 1, len(knots) - 1)]
                behind = knots[max(0, i - 1)]
                dx, dy = ahead.x - k.x, ahead.y - k.y
                if math.hypot(dx, dy) < 1e-7:
                    dx, dy = k.x - behind.x, k.y - behind.y
                if (
                    player["position"] == "GK"
                    and k.contact_effectors.get(pid) == "hands"
                    and behind.holder != pid
                    and math.dist((behind.x, behind.y), (k.x, k.y)) > 1e-7
                ):
                    # A save meets the incoming ball facing back toward play,
                    # not toward its later deflection behind the goalkeeper.
                    dx, dy = behind.x - k.x, behind.y - k.y
                if math.hypot(dx, dy) < 1e-7:
                    facing_team = by_id[k.holder]["team"] if k.holder else player["team"]
                    dx = 1 if (facing_team == "home") != (k.t >= period2) else -1
                length = math.hypot(dx, dy)
                if k.holder and k.holder != pid and by_id[k.holder]["team"] != player["team"]:
                    dx, dy = -dx, -dy
                offset = (CONTACT_REACH * dx / length, CONTACT_REACH * dy / length)
                if last_touch is not None and math.dist(position, last_touch) < 1e-7:
                    offset = last_offset
                root = (position[0] - offset[0], position[1] - offset[1])
                if not 0 <= root[0] <= 105 or not 0 <= root[1] <= 68:
                    # An out ball can be collected from inside the boundary.
                    # Choose a real reachable root on the contact circle.
                    candidates = [
                        (
                            position[0] - CONTACT_REACH * math.cos(j * math.pi / 32),
                            position[1] - CONTACT_REACH * math.sin(j * math.pi / 32),
                        )
                        for j in range(64)
                    ]
                    root = min(
                        (p for p in candidates if 0 <= p[0] <= 105 and 0 <= p[1] <= 68),
                        key=lambda p: math.dist(p, root),
                    )
                last_touch, last_offset = position, (position[0] - root[0], position[1] - root[1])
                position = root
            elif last_touch is not None and math.dist(position, last_touch) < 0.01:
                # Persistent explicit release anchors still denote the contact
                # point, not a later request to move the body into the ball.
                position = (last_touch[0] - last_offset[0], last_touch[1] - last_offset[1])
            anchors[i] = position
        first = min(anchors, default=None)
        right = player["team"] == "home"
        initial = support_position(player, right, (knots[0].x, knots[0].y), knots[0].t, owners[0])
        if first is not None:
            initial = _in_disk(initial, anchors[first], reach(knots[first].t - knots[0].t))
        anchors.setdefault(0, initial)
        anchors.setdefault(len(knots) - 1, anchors[max(anchors)])
        nodes = []
        total = 0
        indices = sorted(anchors)
        for start_i, end_i in zip(indices, indices[1:]):
            start, end = anchors[start_i], anchors[end_i]
            span = knots[end_i].t - knots[start_i].t
            if math.dist(start, end) > reach(span) + 1e-5:
                raise ValueError(
                    f"unreachable physical source contact: {pid} at {knots[end_i].t} "
                    f"from {knots[start_i].t}: {start} -> {end}, reach={reach(span)}"
                )
            if not nodes:
                nodes.append(PathNode(knots[start_i].t, *start, total))
            previous = start
            previous_t = knots[start_i].t
            for i in range(start_i + 1, end_i):
                k = knots[i]
                if k.t - previous_t < 3 or knots[end_i].t - k.t < 3:
                    continue
                step, remaining = reach(k.t - previous_t), reach(knots[end_i].t - k.t)
                if math.dist(previous, end) > step + remaining:
                    continue
                right = (player["team"] == "home") != (k.t >= period2)
                wanted = support_position(player, right, (k.x, k.y), k.t, owners[i])
                point = _reachable_target(wanted, previous, step, end, remaining)
                total += math.dist(previous, point)
                nodes.append(PathNode(k.t, *point, total))
                previous, previous_t = point, k.t
            total += math.dist(previous, end)
            nodes.append(PathNode(knots[end_i].t, *end, total))
        if not nodes:
            nodes = [PathNode(knots[0].t, *initial, 0)]
        nodes = through_velocities(nodes)
        match.player_paths[pid] = nodes
        for k in knots:
            x, y, _ = sample(nodes, k.t, distance=False)
            k.player_positions[pid] = (x, y)
    by_t = {k.t: k for k in knots}
    for k in match.keyframes:
        k.player_positions = dict(by_t[k.t].player_positions)
