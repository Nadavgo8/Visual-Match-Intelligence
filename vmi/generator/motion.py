"""Private truth keyframes; consumers of the event feed cannot read future motion."""

from dataclasses import dataclass, field
import math


def formation_position(base_x, base_y, role, player_id, right, ball_x, ball_y, t):
    """Shared optical baseline; explicit encounter positions take precedence."""
    bax, bay = (ball_x, ball_y) if right else (105 - ball_x, 68 - ball_y)
    if role == "GK":
        ax, ay = base_x + max(0, (bax - 30) * 0.05), base_y + (bay - 34) * 0.12
    else:
        seed = sum(map(ord, player_id))
        ax = base_x + (bax - 52.5) * 0.45 + 1.2 * math.sin(t / 3.1 + seed)
        ay = base_y + (bay - base_y) * 0.25 + 1.2 * math.cos(t / 2.7 + seed * 0.7)
    x, y = (ax, ay) if right else (105 - ax, 68 - ay)
    return min(max(x, 0), 105), min(max(y, 0), 68)


PLAYER_SPEED = 9.0  # engineering ceiling in metres/source second, not a calibration claim


def support_position(player, right, ball, t, owner):
    """Role/phase targets; all final movement is staged in private source truth."""
    x, y = formation_position(player["base_x"], player["base_y"], player["position"],
                              player["id"], right, *ball, t)
    ax, ay = (x, y) if right else (105 - x, 68 - y)
    bx, by = ball if right else (105 - ball[0], 68 - ball[1])
    role = player["position"]
    if role != "GK" and owner:
        attacking = player["team"] == owner
        if attacking:
            # Width offers a release; midfielders stay connected underneath the
            # ball rather than placing a fixed number of bodies in the box.
            if role in {"RW", "LW", "RB", "LB"}:
                ay = 34 + (ay - 34) * 1.14
            if role in {"CM", "DM"}:
                ax = min(ax, bx - (9 if bx > 70 else 5))
            if bx < 35 and role in {"CB", "RB", "LB"}:
                ax = min(ax, bx + 10)
        else:
            # The defending block narrows toward the ball-side channel and
            # protects the space between ball and goal.
            ay = ay * .78 + by * .22
            # A low ball does not put the entire side on one six-yard line.
            # Cover, midfield screens and counter outlets retain different
            # depths; the block can still advance as the ball moves upfield.
            depth = {"CB":(4,28,-7),"RB":(7,36,-3),"LB":(7,36,-3),
                     "DM":(12,42,-6),"CM":(17,52,-3),
                     "RW":(24,64,8),"LW":(24,64,8),"ST":(30,74,15)}
            floor,ceiling,offset=depth.get(role,(17,52,-3))
            ax = min(ax,max(floor,min(ceiling,bx+offset)))
    x, y = (ax, ay) if right else (105 - ax, 68 - ay)
    return min(104, max(1, x)), min(67, max(1, y))


def _in_disk(point, centre, radius):
    distance = math.dist(point, centre)
    if distance <= radius or distance < 1e-12:
        return point
    return tuple(c + (p - c) * radius / distance for p, c in zip(point, centre))


def _reachable_target(wanted, previous, step, anchor, remaining):
    """Closest target inside both velocity and next-contact reachability disks."""
    a, b = previous, anchor
    d = math.dist(a, b)
    if d > step + remaining + 1e-6:
        raise ValueError("source contacts require an impossible player movement")
    candidates = [wanted, _in_disk(wanted, a, step), _in_disk(wanted, b, remaining)]
    if d > 1e-10 and abs(step - remaining) <= d <= step + remaining:
        along = (step * step - remaining * remaining + d * d) / (2 * d)
        height = math.sqrt(max(0, step * step - along * along))
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        mid = (a[0] + along * ux, a[1] + along * uy)
        candidates.extend([(mid[0] - height * uy, mid[1] + height * ux),
                           (mid[0] + height * uy, mid[1] - height * ux)])
    feasible = [p for p in candidates if math.dist(p, a) <= step + 1e-6
                and math.dist(p, b) <= remaining + 1e-6]
    if not feasible:
        # Tangency after floating-point cancellation.
        return _in_disk(b, a, step)
    return min(feasible, key=lambda p: math.dist(p, wanted))


def stage_players(match):
    """Freeze complete metric player paths once, never during replay sampling.

    Contact anchors are private simulation positions, never noisy event-feed
    coordinates. Anticipation is generated world motion, not delivered knowledge
    of the future pass/result. Memory is O(players * source keyframes).
    """
    knots = sorted({k.t: k for k in match.keyframes}.values(), key=lambda k: k.t)
    if not knots:
        return
    players = [dict(p) for team in match.meta["teams"].values() for p in team["players"]]
    by_id = {p["id"]: p for p in players}
    # Current occupied slots belong to private motion truth, never to initial
    # public roster metadata (which would reveal future substitution choices).
    for event in match.events:
        if event["type"] == "substitution":
            change = event["substitution"]
            off, on = by_id[change["off_id"]], by_id[change["on_id"]]
            on["base_x"], on["base_y"] = off["base_x"], off["base_y"]
            if off["position"] == "GK":
                on["position"] = "GK"
    period2 = next((e["t"] for e in match.events if e["type"] == "period_start"
                    and e["period_start"]["period_no"] == 2), float("inf"))
    holders = {p["id"]: p["team"] for p in players}
    owners, owner = [], None
    for k in knots:
        owner = holders[k.holder] if k.holder else owner if k.in_play else None
        owners.append(owner)
    for player in players:
        pid = player["id"]
        anchors = {i: k.player_positions[pid] for i, k in enumerate(knots) if pid in k.player_positions}
        anchors.update({i: (k.x, k.y) for i, k in enumerate(knots) if k.holder == pid})
        next_anchor, upcoming = {}, None
        for i in reversed(range(len(knots))):
            if i in anchors:
                upcoming = i
            next_anchor[i] = upcoming
        previous, previous_t = None, knots[0].t
        for i, k in enumerate(knots):
            right = (player["team"] == "home") != (k.t >= period2)
            wanted = support_position(player, right, (k.x, k.y), k.t, owners[i])
            anchor_i = next_anchor[i]
            if previous is None:
                position = wanted if anchor_i is None else _in_disk(
                    wanted, anchors[anchor_i], PLAYER_SPEED * (knots[anchor_i].t - k.t))
            elif anchor_i is None:
                position = _in_disk(wanted, previous, PLAYER_SPEED * (k.t - previous_t))
            else:
                try:
                    position = _reachable_target(wanted, previous, PLAYER_SPEED * (k.t - previous_t),
                                                 anchors[anchor_i], PLAYER_SPEED * (knots[anchor_i].t - k.t))
                except ValueError:
                    raise ValueError(f"unreachable source contact: {pid} at {knots[anchor_i].t}") from None
            k.player_positions[pid] = position
            previous, previous_t = position, k.t
    # Same-time bookkeeping frames share the final physical state of that time.
    by_t = {k.t: k for k in knots}
    for k in match.keyframes:
        k.player_positions = dict(by_t[k.t].player_positions)


@dataclass
class Keyframe:
    t: float
    x: float
    y: float
    holder: str | None
    in_play: bool
    z: float = 0.0
    flight_height: float = 0.0  # arc from this keyframe to the next one
    possession_id: str | None = None
    player_positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    contact_effectors: dict[str, str] = field(default_factory=dict)  # private current physical touches
    player_facings: tuple[tuple[str, float], ...] = ()  # immutable private setup orientation, radians

    def __post_init__(self):
        self.player_facings = tuple(tuple(pair) for pair in self.player_facings)
