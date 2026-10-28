import test from "node:test";
import assert from "node:assert/strict";
import { buildCrowd, CrowdReactions, CELEBRATE_S, drawCrowd, goalX, pose } from "../../web/crowd.mjs";

// The TV canvas: 1600x900 with a 60 px margin around the pitch.
const GEOM = { W: 1600, H: 900, left: 60, right: 1540, top: 60, bottom: 840 };
const meters = (level, extra = {}, score = { home: 0, away: 0 }, period = 1) =>
  ({ period, score, atmosphere: { available: true, level, attack: 0, attack_team: null, ...extra } });
function run(r, from, to, dt = 1 / 60) { for (let t = from; t <= to; t += dt) r.step(t, dt); }
const mean = (gs) => gs.reduce((s, g) => s + g.excitement, 0) / gs.length;

test("seats stay in the margin: never on the pitch, always on the canvas", () => {
  const c = buildCrowd(GEOM);
  assert.ok(c.fans.length > 550 && c.fans.length < 1200, `fans=${c.fans.length}`);
  for (const f of c.fans) {
    const onPitch = f.x > GEOM.left - 9 && f.x < GEOM.right + 9 && f.y > GEOM.top - 9 && f.y < GEOM.bottom + 9;
    assert.ok(!onPitch, `fan at ${f.x},${f.y} too close to the pitch`);
    assert.ok(f.x > 8 && f.x < GEOM.W - 8 && f.y > 8 && f.y < GEOM.H - 8, `fan at ${f.x},${f.y} off canvas`);
  }
  const sides = new Set(c.groups.map((g) => g.side));
  assert.deepEqual([...sides].sort(), ["bottom", "left", "right", "top"]);
  assert.ok(c.groups.some((g) => g.team === "away") && c.groups.some((g) => g.team === null));
});

test("layout is deterministic for a reliable demo", () => {
  assert.deepEqual(JSON.stringify(buildCrowd(GEOM)), JSON.stringify(buildCrowd(GEOM)));
});

test("goal ends follow the period: home attacks right in the first half", () => {
  const c = buildCrowd(GEOM);
  assert.equal(goalX(c, "home", 1), GEOM.right);
  assert.equal(goalX(c, "home", 2), GEOM.left);
  assert.equal(goalX(c, "away", 1), GEOM.left);
  assert.equal(goalX(c, null, 1), null);
  assert.equal(goalX(c, "home", undefined), null);
});

test("a quiet or unavailable atmosphere keeps the crowd seated", () => {
  for (const m of [meters(0.15), { period: 1, score: { home: 0, away: 0 }, atmosphere: { available: false, level: null } }]) {
    const r = new CrowdReactions(buildCrowd(GEOM));
    r.meters(m, 0); run(r, 0, 5);
    const standing = r.crowd.fans.filter((f) => pose(f, r.crowd.groups[f.g].excitement).stand > 0.5).length;
    assert.ok(standing < r.crowd.fans.length * 0.03, `standing=${standing}`);
  }
});

test("louder atmosphere stands more fans, monotonically", () => {
  let last = -1;
  for (const level of [0.2, 0.5, 0.8, 1]) {
    const r = new CrowdReactions(buildCrowd(GEOM));
    r.meters(meters(level), 0); run(r, 0, 6);
    const e = mean(r.crowd.groups);
    assert.ok(e > last, `level ${level}: ${e} <= ${last}`);
    last = e;
  }
});

test("a dangerous attack excites the attacking team's fans near that goal more than far ones", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.meters(meters(0.6, { attack: 1, attack_team: "home" }), 0); run(r, 0, 6);
  const top = r.crowd.groups.filter((g) => g.side === "top" && g.team === "home");
  const near = top.filter((g) => g.cx > 1200), far = top.filter((g) => g.cx < 400);
  assert.ok(mean(near) > mean(far) + 0.2, `near ${mean(near)} far ${mean(far)}`);
  // Opposing fans at the same end react less than home fans there.
  const awayNear = r.crowd.groups.filter((g) => g.team === "away" && g.side === "right");
  const homeNear = r.crowd.groups.filter((g) => g.team === "home" && g.cx > 1300);
  assert.ok(mean(homeNear) > mean(awayNear));
});

test("reactions spread as a wave: nearer groups rise before farther ones", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.meters(meters(0.7, { attack: 1, attack_team: "home" }), 0);
  const top = r.crowd.groups.filter((g) => g.side === "top" && g.team === "home").sort((a, b) => b.cx - a.cx);
  const first = top[0], later = top[5];
  assert.ok(first.armAt < later.armAt, "nearest group starts first");
  run(r, 0, first.armAt + 0.3);
  assert.ok(first.excitement > later.excitement + 0.1);
});

test("a goal makes the scoring team's fans celebrate, not the opponents'", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.meters(meters(0.6), 0); run(r, 0, 2);
  r.meters(meters(0.95, {}, { home: 0, away: 1 }), 2); run(r, 2, 6);
  const away = r.crowd.groups.filter((g) => g.team === "away"), home = r.crowd.groups.filter((g) => g.team === "home");
  assert.ok(mean(away) > 0.85, `away ${mean(away)}`);
  assert.ok(mean(home) < 0.2, `home ${mean(home)}`);
  assert.ok(r.celebrating(away[0]) && !r.celebrating(home[0]));
});

test("after a celebration the crowd settles gradually, not abruptly", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.meters(meters(0.3), 0); run(r, 0, 1);
  r.meters(meters(0.3, {}, { home: 1, away: 0 }), 1); run(r, 1, 1 + CELEBRATE_S);
  const g = r.crowd.groups.find((x) => x.team === "home");
  const peak = g.excitement;
  run(r, 1 + CELEBRATE_S, 1 + CELEBRATE_S + 0.5);
  assert.equal(r.celebration, null);
  assert.ok(g.excitement < peak && g.excitement > peak * 0.7, "half a second later, still mostly up");
  run(r, 1 + CELEBRATE_S + 0.5, 1 + CELEBRATE_S + 12);
  assert.ok(g.excitement < 0.2);
});

test("the first score after a reset or seek is a baseline, never a celebration", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.meters(meters(0.5, {}, { home: 2, away: 1 }), 0);
  assert.equal(r.celebration, null);
  r.meters(meters(0.5, {}, { home: 2, away: 1 }), 1);
  r.reset();
  r.meters(meters(0.5, {}, { home: 3, away: 1 }), 2);
  assert.equal(r.celebration, null);
  assert.ok(r.crowd.groups.every((g) => g.excitement === 0));
});

test("visual signals off keeps the crowd calm", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.enabled = false;
  r.meters(meters(1, { attack: 1, attack_team: "home" }), 0); run(r, 0, 4);
  assert.equal(mean(r.crowd.groups), 0);
});

test("drawing is batched: a fixed handful of fills regardless of crowd size", () => {
  const r = new CrowdReactions(buildCrowd(GEOM));
  r.setTeams("#2e6fd8", "#e8e3d3");
  r.meters(meters(0.9, {}, { home: 0, away: 0 }), 0); r.meters(meters(0.9, {}, { home: 1, away: 0 }), 0.1); run(r, 0.1, 4);
  const calls = { fill: 0, stroke: 0, ellipse: 0 };
  const ctx = new Proxy({}, { get: (_, k) => k in calls ? () => { calls[k]++; } : () => {}, set: () => true });
  drawCrowd(ctx, r, 4);
  assert.ok(calls.fill <= 14, `fills=${calls.fill}`);
  assert.equal(calls.stroke, 1);
  assert.equal(calls.ellipse, r.crowd.fans.length);
});
