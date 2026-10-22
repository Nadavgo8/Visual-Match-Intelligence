"""Optical-tracking style frames (x/y of 22 players and the ball), rendered from the
generator's ball keyframes. Frames are computed on demand instead of stored, since
10 per second for a whole match is ~60k frames.
"""

from __future__ import annotations

import bisect
import math

from .match import PITCH_X, PITCH_Y, Match


class Tracker:
    def __init__(self, match: Match):
        self.m = match
        self.kf = sorted(match.keyframes, key=lambda k: k.t)
        self.kt = [k.t for k in self.kf]
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
        keepers = {pid for pid, p in self.players.items() if p["position"] == "GK"}
        for side in ("home", "away"):
            for p in teams[side]["players"]:
                self.base[p["id"]] = (p["base_x"], p["base_y"])
        # subs inherit the position of the player they replace
        for ct, side, off, on in self.changes:
            if on:
                self.base[on] = self.base[off]
                if off in keepers:
                    keepers.add(on)
                    self.keeper_changes.append((ct, on))

    def role_at(self, pid: str, t: float) -> str:
        if any(ct <= t and on == pid for ct, on in self.keeper_changes):
            return "GK"
        return self.players[pid]["position"]

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

    def frame(self, t: float) -> dict:
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
        players = []
        for side in ("home", "away"):
            right = self.attacks_right(side, t)
            # ball position in this team's attack frame
            bax = bx if right else PITCH_X - bx
            bay = by if right else PITCH_Y - by
            for pid in self.lineup(side, t):
                p = self.players[pid]
                ox, oy = self.base[pid]
                if self.role_at(pid, t) == "GK":
                    ax, ay = ox + max(0, (bax - 30) * 0.05), oy + (bay - 34) * 0.12
                else:
                    ax = ox + (bax - 52.5) * 0.45
                    ay = oy + (bay - oy) * 0.25
                    seed = sum(map(ord, pid))
                    ax += 1.2 * math.sin(t / 3.1 + seed)
                    ay += 1.2 * math.cos(t / 2.7 + seed * 0.7)
                x, y = (ax, ay) if right else (PITCH_X - ax, PITCH_Y - ay)
                # the player on the ball moves to it
                if b.holder == pid:
                    w = alpha
                    x, y = x + (b.x - x) * w, y + (b.y - y) * w
                elif a.holder == pid:
                    w = 1 - alpha
                    x, y = x + (a.x - x) * w, y + (a.y - y) * w
                players.append({"id": pid, "team": side, "n": p["number"],
                                "x": round(min(max(x, 0), PITCH_X), 2), "y": round(min(max(y, 0), PITCH_Y), 2)})
        return {"stream": "tracking", "source": "tracking", "t": round(t, 2),
                "ball": [round(bx, 2), round(by, 2)], "players": players}
