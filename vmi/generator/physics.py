"""Deterministic metric trajectories, planned before delivered tracking is sampled."""

from bisect import bisect_right
from collections import OrderedDict, namedtuple
from threading import RLock
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
    # Canonical developer truth, never public tracking. Only finalized nodes
    # carry (geometry, cuts, masses, total, polynomial); raw nodes have None.
    incoming_metrics: tuple | None = None

    def __post_init__(self):
        if isinstance(self.incoming_metrics, list):

            def freeze(value):
                return tuple(freeze(item) for item in value) if isinstance(value, list) else value

            object.__setattr__(self, "incoming_metrics", freeze(self.incoming_metrics))


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
        stride = 0.8 + 0.5 * rate * inverse_dt
        cycles += weight * rate / (stride if stride < 4.4 else 4.4)
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


def _metric_cuts(coefficients):
    """Fixed domains at speed extrema/zeros and the cadence stride-cap kink."""
    aa, bb, cc, dd, ee, ff, inverse_dt, _ = coefficients
    av, bv, cv = (aa, dd), (bb, ee), (cc, ff)
    dot = lambda x, y: x[0] * y[0] + x[1] * y[1]
    extrema = unit_roots((2 * dot(av, av), 3 * dot(av, bv), dot(bv, bv) + 2 * dot(av, cv), dot(bv, cv)))
    points = sorted({0.0, 1.0, *(u for u in extrema if 0 < u < 1)})
    threshold = (7.2 / inverse_dt) ** 2
    evaluate = lambda u: ((aa * u + bb) * u + cc) ** 2 + ((dd * u + ee) * u + ff) ** 2 - threshold
    crossings = []
    for lo, hi in zip(points, points[1:]):
        left = evaluate(lo)
        if left * evaluate(hi) >= 0:
            continue
        for _ in range(36):
            mid = (lo + hi) / 2
            if left * evaluate(mid) <= 0:
                hi = mid
            else:
                lo = mid
        crossings.append((lo + hi) / 2)
    cuts = []
    for point in sorted([*points, *crossings]):
        if not cuts or point - cuts[-1] > 1e-10:
            cuts.append(point)
    # Cubic extrema plus at most four quartic cap crossings: eight domains.
    return tuple(cuts)


def _interval_metrics(coefficients, lo, hi):
    """Accurate positive mass on a fixed interval, independent of the query."""

    def integrate(left_u, right_u, whole, depth):
        mid = (left_u + right_u) / 2
        left = _quadrature(coefficients, left_u, mid)
        right = _quadrature(coefficients, mid, right_u)
        fine = left[0] + right[0], left[1] + right[1]
        # Budget canonical integration below the independently tested 3e-5
        # per-segment metric requirement, rather than 1e-7 per tiny interval.
        if depth == 8 or (
            abs(fine[0] - whole[0]) <= 5e-6 * (right_u - left_u)
            and abs(fine[1] - whole[1]) <= 5e-6 * (right_u - left_u)
        ):
            return fine
        first = integrate(left_u, mid, left, depth + 1)
        last = integrate(mid, right_u, right, depth + 1)
        return first[0] + last[0], first[1] + last[1]

    return integrate(lo, hi, _quadrature(coefficients, lo, hi), 0)


def _collinear_polynomial(coefficients):
    aa, bb, cc, dd, ee, ff, _, _ = coefficients
    vectors = ((aa, dd), (bb, ee), (cc, ff))
    direction = max(vectors, key=lambda v: math.hypot(*v))
    length = math.hypot(*direction)
    if length == 0:
        return 0.0, 0.0, 0.0
    ux, uy = direction[0] / length, direction[1] / length
    if any(abs(x * uy - y * ux) > 1e-10 * max(1, math.hypot(x, y)) for x, y in vectors):
        return None
    return tuple(x * ux + y * uy for x, y in vectors)


def _quadratic_roots(aa, bb, cc):
    if abs(aa) < 1e-12:
        return [-cc / bb] if abs(bb) > 1e-12 else []
    discriminant = bb * bb - 4 * aa * cc
    if discriminant < 0:
        return []
    value = -0.5 * (bb + math.copysign(math.sqrt(discriminant), bb))
    return [value / aa, cc / value] if value else [-bb / (2 * aa)]


def _collinear_cuts(polynomial, duration):
    aa, bb, cc = polynomial
    points = [0.0, 1.0]
    if abs(aa) > 1e-12:
        points.append(-bb / (2 * aa))
    for level in (0.0, -7.2 * duration, 7.2 * duration):
        points.extend(_quadratic_roots(aa, bb, cc - level))
    cuts = []
    for point in sorted(p for p in points if 0 <= p <= 1):
        if not cuts or point - cuts[-1] > 1e-10:
            cuts.append(point)
    return tuple(cuts)


def _reciprocal_quadratic(aa, bb, cc):
    # Integral on [0,1]. Shift/scale before calling this to avoid subtracting
    # almost equal logarithms or atan primitives on tiny partial intervals.
    discriminant = 4 * aa * cc - bb * bb
    middle = 2 * cc + bb
    if abs(discriminant) <= 1e-12 * max(1, abs(4 * aa * cc), bb * bb):
        return 2 / middle
    if discriminant > 0:
        root = math.sqrt(discriminant)
        return 2 * math.atan2(root, middle) / root
    root = math.sqrt(-discriminant)
    return math.log1p(2 * root / (middle - root)) / root


def _collinear_metrics(coefficients, polynomial, lo, hi):
    width = hi - lo
    if width <= 0:
        return 0.0, 0.0
    aa, bb, cc = polynomial
    duration = 1 / coefficients[6]
    mid = (lo + hi) / 2
    sign = 1 if (aa * mid + bb) * mid + cc >= 0 else -1
    aa, bb, cc = sign * aa, sign * bb, sign * cc
    initial, slope = (aa * lo + bb) * lo + cc, 2 * aa * lo + bb
    distance = max(0.0, width * (initial + slope * width / 2 + aa * width * width / 3))
    speed = ((aa * mid + bb) * mid + cc) / duration
    if speed >= 7.2:
        return distance, distance / 4.4
    maximum = max(abs((aa * u + bb) * u + cc) / duration for u in (lo, hi))
    if maximum < 0.01:
        # Four terms of the positive small-speed polynomial have relative
        # error <=(.00625)^4. Gauss8 integrates its degree-eight polynomial
        # exactly: changing partial nodes cannot create the old norm cusp bug.
        cycles = 0.0
        for x, weight in _GAUSS:
            u = lo + width * (x + 1) / 2
            rate = max(0.0, (aa * u + bb) * u + cc)
            small = 0.625 * rate / duration
            cycles += weight * rate / 0.8 * (1 - small + small * small - small * small * small)
        return distance, cycles * width / 2
    reciprocal = width * _reciprocal_quadratic(
        0.5 * aa * width * width / duration, 0.5 * slope * width / duration, 0.8 + 0.5 * initial / duration
    )
    return distance, max(0.0, 2 * duration * (width - 0.8 * reciprocal))


@lru_cache(maxsize=256)
def _metric_plan(key):
    """Canonical endpoint shared by source planning and every sampled CDF."""
    coefficients = _metric_coefficients(key)
    polynomial = _collinear_polynomial(coefficients)
    cuts = _collinear_cuts(polynomial, key[0]) if polynomial is not None else _metric_cuts(coefficients)
    parts = [
        (
            _collinear_metrics(coefficients, polynomial, lo, hi)
            if polynomial is not None
            else _interval_metrics(coefficients, lo, hi)
        )
        for lo, hi in zip(cuts, cuts[1:])
    ]
    total = tuple(sum(part[i] for part in parts) for i in (0, 1))
    return key, cuts, tuple(parts), total, polynomial


def _metric_total(key):
    return _metric_plan(key)[3]


def _positive_integral(fraction, width, total, left, right):
    # With endpoint slopes in [0,3*mean], every corner of this Hermite
    # derivative's affine slope domain is nonnegative: no backwards phase.
    ceiling = 3 * total / width
    left, right = min(ceiling, max(0, left)), min(ceiling, max(0, right))
    u = fraction
    value = total * progress(u) + width * (left * u * (1 - u) ** 2 - right * u * u * (1 - u))
    return min(total, max(0, value))


class _MetricCurve:
    """Lazy positive CDF: at most eight domains of 511 query-independent nodes.

    Cache history changes only work performed. Node bounds, acceptance, positive
    child masses and interpolation values depend solely on the source geometry.
    """

    def __init__(self, key, cache, plan):
        self.key = key
        self.cache = cache
        self.coefficients = _metric_coefficients(key)
        _, self.cuts, self.masses, self.total, self.polynomial = plan
        masses = self.masses
        sums = tuple(sum(mass[i] for mass in masses) for i in (0, 1))
        prefix = [0.0, 0.0]
        self.domains = []
        for mass in masses:
            normalized = tuple(self.total[i] * mass[i] / sums[i] if sums[i] else 0.0 for i in (0, 1))
            self.domains.append((normalized, tuple(prefix)))
            prefix = [prefix[i] + normalized[i] for i in (0, 1)]
        self.nodes = {}

    def __len__(self):
        return len(self.nodes)

    def rate(self, u):
        aa, bb, cc, dd, ee, ff, inverse_dt, rest = self.coefficients
        value = (
            6 * u * (1 - u) * rest if rest is not None else math.hypot((aa * u + bb) * u + cc, (dd * u + ee) * u + ff)
        )
        return value, value / min(4.4, 0.8 + 0.5 * value * inverse_dt)

    def node(self, domain, depth, index, total):
        identity = domain, depth, index
        if identity in self.nodes:
            return self.nodes[identity]
        start, end = self.cuts[domain : domain + 2]
        width = (end - start) * 2.0**-depth
        lo, hi = start + index * width, start + (index + 1) * width
        values = [self.rate(lo + width * j / 8) for j in range(9)]
        quarters = [
            tuple(width / 24 * (values[2 * j][i] + 4 * values[2 * j + 1][i] + values[2 * j + 2][i]) for i in (0, 1))
            for j in range(4)
        ]
        approximate = tuple(sum(q[i] for q in quarters) for i in (0, 1))
        left, right = values[0], values[-1]
        accurate = all(abs(approximate[i] - total[i]) <= 1e-5 for i in (0, 1))
        for j in (1, 2, 3):
            for i in (0, 1):
                expected = sum(q[i] for q in quarters[:j])
                if abs(_positive_integral(j / 4, width, total[i], left[i], right[i]) - expected) > 1e-5:
                    accurate = False
        children = None
        if not accurate and depth < 8:
            mid = (lo + hi) / 2
            first = _interval_metrics(self.coefficients, lo, mid)
            last = _interval_metrics(self.coefficients, mid, hi)
            # Accurate positive half masses are normalized to their canonical
            # parent. Coarse Simpson values must never become permanent prefixes.
            first = tuple(total[i] * first[i] / (first[i] + last[i]) if first[i] + last[i] else 0.0 for i in (0, 1))
            children = first, tuple(total[i] - first[i] for i in (0, 1))
        result = lo, hi, total, left, right, children
        self.nodes[identity] = result
        self.cache.updated(self)
        return result

    def evaluate(self, u):
        depth = index = 0
        domain = min(bisect_right(self.cuts, u) - 1, len(self.domains) - 1)
        total, prefix = self.domains[domain]
        if self.polynomial is not None:
            partial = _collinear_metrics(self.coefficients, self.polynomial, self.cuts[domain], u)
            return tuple(
                prefix[i] + min(total[i], partial[i] * total[i] / self.masses[domain][i])
                if self.masses[domain][i]
                else prefix[i]
                for i in (0, 1)
            )
        while True:
            lo, hi, total, left, right, children = self.node(domain, depth, index, total)
            if children is None:
                return tuple(
                    prefix[i] + _positive_integral((u - lo) / (hi - lo), hi - lo, total[i], left[i], right[i])
                    for i in (0, 1)
                )
            if u < (lo + hi) / 2:
                total, index = children[0], index * 2
            else:
                prefix = [prefix[i] + children[0][i] for i in (0, 1)]
                total, index = children[1], index * 2 + 1
            depth += 1


_CacheInfo = namedtuple("CacheInfo", "hits misses maxsize currsize")


class _CurveCache:
    """Whole-curve LRU bounded by entry count and aggregate retained nodes."""

    def __init__(self, max_nodes=8192, max_curves=256):
        self.max_nodes, self.max_curves = max_nodes, max_curves
        self.entries = OrderedDict()
        self.retained_nodes = self.hits = self.misses = 0
        self.lock = RLock()

    def __call__(self, key, plan=None):
        with self.lock:
            if key in self.entries:
                self.hits += 1
                self.entries.move_to_end(key)
                return self.entries[key][0]
            self.misses += 1
            curve = _MetricCurve(key, self, plan if plan is not None else _metric_plan(key))
            self.entries[key] = curve, 0
            self.trim()
            return curve

    def trim(self):
        while len(self.entries) > self.max_curves or self.retained_nodes > self.max_nodes:
            _, (_, weight) = self.entries.popitem(last=False)
            self.retained_nodes -= weight

    def updated(self, curve):
        with self.lock:
            entry = self.entries.get(curve.key)
            if entry is not None and entry[0] is curve:
                weight = len(curve)
                self.retained_nodes += weight - entry[1]
                self.entries[curve.key] = curve, weight
                self.entries.move_to_end(curve.key)
                self.trim()

    def cache_info(self):
        with self.lock:
            return _CacheInfo(self.hits, self.misses, self.max_curves, len(self.entries))

    def cache_clear(self):
        with self.lock:
            self.entries.clear()
            self.retained_nodes = self.hits = self.misses = 0


_metric_curve = _CurveCache()


def arc_metrics(a, b, u=1):
    if b.t <= a.t or u <= 0:
        return 0.0, 0.0
    key = _metric_key(a, b)
    plan = b.incoming_metrics
    if plan is None or plan[0] != key:
        plan = _metric_plan(key)
    if u >= 1:
        return plan[3]
    return _metric_curve(key, plan).evaluate(u)


def arc_length(a, b, u=1):
    return arc_metrics(a, b, u)[0]


def through_velocities(nodes, *, facing_targets=None):
    """Keep shared nonzero tangents through runs, with certified braking at turns."""
    facing_targets = facing_targets or {}
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
    if facing is None and facing_targets:
        facing = facing_targets[min(facing_targets)]
    for i, node in enumerate(nodes):
        metrics = None
        if i:
            previous = nodes[i - 1]
            if node.t > previous.t:
                metrics = _metric_plan(_metric_key(previous, node))
                length, turns = metrics[3]
            else:
                length, turns = 0.0, 0.0
            total += length
            cycles += turns
            if math.dist((previous.x, previous.y), (node.x, node.y)) > 1e-8:
                heading = math.atan2(node.x - previous.x, previous.y - node.y)
            desired = facing_targets.get(node.t, heading)
            if facing is not None and desired is not None:
                delta = math.atan2(math.sin(desired - facing), math.cos(desired - facing))
                allowed = BODY_TURN_SPEED * (node.t - previous.t) / 1.5
                if node.t in facing_targets and abs(delta) > allowed + 1e-7:
                    raise ValueError("unreachable source body facing deadline")
                facing += min(allowed, max(-allowed, delta))
                facing = math.atan2(math.sin(facing), math.cos(facing))
        elif len(nodes) > 1:
            dx, dy = nodes[1].x - node.x, nodes[1].y - node.y
            if math.hypot(dx, dy) > 1e-8:
                facing = math.atan2(dx, -dy)
        if facing is None:
            facing = heading
        if i == 0 and node.t in facing_targets:
            facing = facing_targets[node.t]
        nodes[i] = replace(
            node, distance=total, heading=heading, facing=facing, gait_cycles=cycles, incoming_metrics=metrics
        )
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
        facings = dict(previous.player_facings) if previous else {}
        positions.update(key.player_positions)
        effectors.update(key.contact_effectors)
        facings.update(key.player_facings)
        if key.holder:
            positions[key.holder] = (key.x, key.y)
        by_time[key.t] = replace(key, player_positions=positions, contact_effectors=effectors,
                                player_facings=tuple(facings.items()))
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
                explicit_facing = dict(k.player_facings).get(pid)
                if explicit_facing is not None:
                    # A planned stationary kick constrains both orientation and
                    # the physical foot reach, independently of ball bookkeeping.
                    offset = (CONTACT_REACH * math.sin(explicit_facing),
                              -CONTACT_REACH * math.cos(explicit_facing))
                elif last_touch is not None and math.dist(position, last_touch) < 1e-7:
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
        targets = {k.t: dict(k.player_facings)[pid] for k in knots if pid in dict(k.player_facings)}
        if targets.keys() - {node.t for node in nodes}:
            raise ValueError("source body facing requires an explicit position anchor")
        nodes = through_velocities(nodes, facing_targets=targets)
        match.player_paths[pid] = nodes
        for k in knots:
            x, y, _ = sample(nodes, k.t, distance=False)
            k.player_positions[pid] = (x, y)
    by_t = {k.t: k for k in knots}
    for k in match.keyframes:
        k.player_positions = dict(by_t[k.t].player_positions)
