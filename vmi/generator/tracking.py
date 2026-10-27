"""Optical-tracking style frames (x/y of 22 players and the ball), rendered from the
generator's ball keyframes. Frames are computed on demand instead of stored, since
20 per second for a whole match is ~120k frames.
"""

from __future__ import annotations

import bisect
import math

from .match import PITCH_X, PITCH_Y, Match
from .motion import formation_position
from .physics import sample as sample_path


class Tracker:
    def __init__(self, match: Match):
        self.m = match
        self.kf = sorted(match.keyframes, key=lambda k: k.t)
        self.kt = [k.t for k in self.kf]
        self.source_paths = match.meta.get("motion_model") in {"source-paths-1", "source-paths-2"}
        self.distances = []
        self.headings = []
        totals = {}
        headings = {}
        previous = None
        for k in self.kf:
            for pid, position in k.player_positions.items():
                if previous and pid in previous.player_positions:
                    before = previous.player_positions[pid]
                    distance = math.dist(before, position)
                    totals[pid] = totals.get(pid, 0) + distance
                    if distance > 1e-8:
                        headings[pid] = math.atan2(position[0] - before[0], before[1] - position[1])
                else:
                    totals.setdefault(pid, 0)
            self.distances.append(dict(totals))
            self.headings.append(dict(headings))
            previous = k
        teams = match.meta["teams"]
        self.players = {p["id"]: p for side in teams.values() for p in side["players"]}
        # lineup changes over time: (t, team, off, on)
        self.changes = []
        self.period2_t = None
        for e in match.events:
            if e["type"] == "substitution":
                s = e["substitution"]
                self.changes.append((e["t"], e["team"], s["off_id"], s["on_id"]))
            elif e["type"] == "card" and e["card"]["colour"] != "yellow":
                self.changes.append((e["t"], e["team"], e["player_id"], None))
            elif e["type"] == "period_start" and e["period_start"]["period_no"] == 2:
                self.period2_t = e["t"]
        self.base = {}
        self.keeper_changes = []
        self.entry_times = {pid: 0 for pid, p in self.players.items() if p.get("starter")}
        keepers = {pid for pid, p in self.players.items() if p["position"] == "GK"}
        for side in ("home", "away"):
            for p in teams[side]["players"]:
                self.base[p["id"]] = (p["base_x"], p["base_y"])
        # subs inherit the position of the player they replace
        for ct, side, off, on in self.changes:
            if on:
                self.entry_times[on] = ct
                self.base[on] = self.base[off]
                if off in keepers:
                    keepers.add(on)
                    self.keeper_changes.append((ct, on))
        self.contact_actions = {}
        self.entry_metrics = {}
        if self.m.player_paths:
            for pid, entry in self.entry_times.items():
                if entry:
                    self.entry_metrics[pid] = sample_path(self.m.player_paths[pid], entry)[2]
            self._index_contacts()

    def _physical_record(self, pid, t, record, right, holder, ball):
        x, y, motion = sample_path(self.m.player_paths[pid], t)
        if motion["heading"] is None:
            motion["heading"] = math.pi / 2 if right else -math.pi / 2
        if motion["facing"] is None:
            motion["facing"] = motion["heading"]
        if pid in self.entry_metrics:
            entered = self.entry_metrics[pid]
            motion["distance"] = max(0, motion["distance"] - entered["distance"])
            motion["gait_cycles"] = max(0, motion["gait_cycles"] - entered["gait_cycles"])
        record.update(x=round(x, 2), y=round(y, 2), motion=motion)
        contact = self._contact(pid, t, holder, ball)
        if contact:
            record["contact"] = contact
        return record

    def _index_contacts(self):
        """Private physical action history. Never read outcomes, xG or future feed delivery."""
        events = {}
        for event in self.m.events:
            if event["type"] in {"pass", "shot", "save", "block", "clearance", "set_piece", "foul", "handball"}:
                events.setdefault(event["t"], []).append(event)
        previous = None
        for k in self.kf:
            for event in events.get(k.t, []):
                pid = event.get("player_id")
                if pid not in self.m.player_paths:
                    continue
                kind, effector = "release", k.contact_effectors.get(pid, "foot")
                if event["type"] in {"foul", "handball"}:
                    if "incident_t" in event or pid not in k.contact_effectors:
                        continue
                    kind = "challenge"
                if event["type"] == "set_piece" and event["set_piece"]["kind"] == "throw_in":
                    kind, effector = "throw", "hands"
                elif event["type"] == "save":
                    kind, effector = "save", "hands"
                elif event["type"] == "block":
                    kind = "block"
                self.contact_actions.setdefault(pid, []).append((k.t, kind, effector, (k.x, k.y, k.z)))
            if k.holder and (previous is None or previous.holder != k.holder):
                effector = k.contact_effectors.get(k.holder, "foot")
                kind = (
                    "save"
                    if any(e["type"] == "save" and e.get("player_id") == k.holder for e in events.get(k.t, []))
                    else "receive"
                )
                self.contact_actions.setdefault(k.holder, []).append((k.t, kind, effector, (k.x, k.y, k.z)))
            previous = k
        for pid, actions in self.contact_actions.items():
            self.contact_actions[pid] = sorted(set(actions))

    def _contact(self, pid, t, holder, ball):
        actions = self.contact_actions.get(pid, [])
        index = bisect.bisect_right(actions, t, key=lambda action: action[0]) - 1
        if index >= 0:
            start, kind, effector, target = actions[index]
            end = round(start + 0.32, 2)
            if start <= t < end:
                x, y, _ = sample_path(self.m.player_paths[pid], start, distance=False)
                return {
                    "kind": kind,
                    "effector": effector,
                    "start_t": start,
                    "end_t": end,
                    "target": list(target),
                    "phase": min(1, max(0, (t - start) / 0.32)),
                    "heading": math.atan2(target[0] - x, y - target[1]),
                }
        if holder == pid:
            x, y, _ = sample_path(self.m.player_paths[pid], t, distance=False)
            current = self.kf[max(0, bisect.bisect_right(self.kt, t) - 1)]
            return {
                "kind": "control",
                "effector": current.contact_effectors.get(pid, "foot"),
                "start_t": round(t, 2),
                "end_t": round(t, 2),
                "target": list(ball),
                "phase": 1.0,
                "heading": math.atan2(ball[0] - x, y - ball[1]),
            }
        return None

    def role_at(self, pid: str, t: float) -> str:
        if any(ct <= t and on == pid for ct, on in self.keeper_changes):
            return "GK"
        return self.players[pid]["position"]

    def frames(self, start: float = 0, end: float | None = None, hz: int = 20):
        """Stream a bounded time range by index; never allocate a match of frames."""
        end = self.m.duration if end is None else end
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= self.m.duration):
            raise ValueError("tracking range must be finite and inside the match")
        if not isinstance(hz, int) or isinstance(hz, bool) or not 1 <= hz <= 100:
            raise ValueError("tracking frequency must be an integer from 1 to 100")
        for index in range(math.floor((end - start) * hz + 1e-8) + 1):
            yield self.frame(start + index / hz)

    def lineup(self, side: str, t: float) -> list[str]:
        ids = [p["id"] for p in self.m.meta["teams"][side]["players"] if p["starter"]]
        for ct, s, off, on in self.changes:
            if ct > t or s != side:
                continue
            if off in ids:
                if on:
                    ids[ids.index(off)] = on
                else:
                    ids.remove(off)
        return ids

    def attacks_right(self, side: str, t: float) -> bool:
        p2 = self.period2_t is not None and t >= self.period2_t
        return (side == "home") != p2

    def _ball(self, t: float):
        i = bisect.bisect_right(self.kt, t) - 1
        if i < 0:
            a = b = self.kf[0]
            alpha = 0.0
        elif i >= len(self.kf) - 1:
            a = b = self.kf[-1]
            alpha = 0.0
        else:
            a, b = self.kf[i], self.kf[i + 1]
            span = max(b.t - a.t, 1e-6)
            alpha = min(max((t - a.t) / span, 0.0), 1.0)
        bx = a.x + (b.x - a.x) * alpha
        by = a.y + (b.y - a.y) * alpha
        bz = a.z + (b.z - a.z) * alpha + 4 * a.flight_height * alpha * (1 - alpha)
        holder = a.holder if a.holder == b.holder or alpha == 0 else None
        if holder and holder in self.m.player_paths:
            x, y, _ = sample_path(self.m.player_paths[holder], t, distance=False)
            ax, ay = a.player_positions[holder]
            bx_offset, by_offset = a.x - ax, a.y - ay
            if a.holder == b.holder and b.t > a.t:
                px, py = b.player_positions[holder]
                angle = math.atan2(by_offset, bx_offset)
                end_angle = math.atan2(b.y - py, b.x - px)
                turn = math.atan2(math.sin(end_angle - angle), math.cos(end_angle - angle))
                angle += turn * alpha
                radius = math.hypot(bx_offset, by_offset)
                bx_offset, by_offset = radius * math.cos(angle), radius * math.sin(angle)
            bx, by = x + bx_offset, y + by_offset
        return a, b, alpha, bx, by, bz, holder

    def observation(self, t: float) -> dict:
        """Same delivered ball/holder sample without drawing the other 21 players."""
        a, b, alpha, bx, by, bz, holder = self._ball(t)
        players = []
        if holder:
            p = self.players[holder]
            if holder in self.lineup(p["team"], t):
                players.append(
                    {
                        "id": holder,
                        "team": p["team"],
                        "n": p["number"],
                        "role": self.role_at(holder, t),
                        "x": round(bx, 2),
                        "y": round(by, 2),
                    }
                )
                if holder in self.m.player_paths:
                    # Engine observations need the actual root, not visual
                    # gait/contact metadata. Sample the same source trajectory
                    # without integrating arc length at every 20Hz engine tick.
                    x,y,_=sample_path(self.m.player_paths[holder],t,distance=False)
                    players[-1].update(x=round(x,2),y=round(y,2))
            else:
                holder = None
        return self._record(t, a, bx, by, bz, holder, players)

    def frame(self, t: float) -> dict:
        a, b, alpha, bx, by, bz, holder = self._ball(t)
        in_play = a.in_play
        players = []
        for side in ("home", "away"):
            right = self.attacks_right(side, t)
            for pid in self.lineup(side, t):
                p = self.players[pid]
                if pid in self.m.player_paths:
                    record = {"id": pid, "team": side, "n": p["number"], "role": self.role_at(pid, t)}
                    players.append(self._physical_record(pid, t, record, right, holder, (bx, by, bz)))
                    continue
                ox, oy = self.base[pid]
                x, y = formation_position(ox, oy, self.role_at(pid, t), pid, right, bx, by, t)
                pa = a.player_positions.get(pid, (x, y))
                pb = b.player_positions.get(pid, (x, y))
                x, y = pa[0] + (pb[0] - pa[0]) * alpha, pa[1] + (pb[1] - pa[1]) * alpha
                # the player on the ball moves to it
                if self.source_paths:
                    pass
                elif holder == pid:
                    x, y = bx, by
                elif b.holder == pid:
                    w = alpha
                    x, y = x + (b.x - x) * w, y + (b.y - y) * w
                elif a.holder == pid:
                    w = 1 - alpha
                    x, y = x + (a.x - x) * w, y + (a.y - y) * w
                record = {
                    "id": pid,
                    "team": side,
                    "n": p["number"],
                    "role": self.role_at(pid, t),
                    "x": round(min(max(x, 0), PITCH_X), 2),
                    "y": round(min(max(y, 0), PITCH_Y), 2),
                }
                if self.source_paths:
                    index = max(0, bisect.bisect_right(self.kt, t) - 1)
                    span = b.t - a.t
                    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
                    distance = math.hypot(dx, dy)
                    record["motion"] = {
                        "heading": math.atan2(dx, -dy)
                        if distance > 1e-8
                        else self.headings[index].get(pid, math.pi / 2 if right else -math.pi / 2),
                        "speed": distance / span if span > 0 else 0,
                        "distance": self.distances[index].get(pid, 0) + distance * alpha,
                    }
                players.append(record)
        return self._record(t, a, bx, by, bz, holder, players)

    def _record(self, t, a, bx, by, bz, holder, players):
        in_play = a.in_play
        return {"stream": "tracking", "match_id": self.m.meta["match_id"], "source": "tracking", "t": round(t, 2),
                "period": 2 if self.period2_t is not None and t >= self.period2_t else 1,
                "schema_version": "2.0", "ball": [round(bx, 2), round(by, 2)],
                "ball_height": round(bz, 3), "ball_in_play": in_play,
                "possession": {"id": a.possession_id if holder and in_play else None,
                               "holder_id": holder if in_play else None,
                               "team": self.players[holder]["team"] if holder and in_play else None,
                               "sample_t": round(t, 2),
                               "status": "controlled" if holder and in_play else "loose" if in_play else "stopped"},
                "quality": {"status": "measured", "confidence": 1.0, "sample_t": round(t, 2)},
                "players": players}
