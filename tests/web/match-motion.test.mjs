import test from "node:test";
import assert from "node:assert/strict";
import { FrameTimeline, interpolate, pitchProjection, validFrame, ballAppearance } from "../../web/match-motion.mjs";
const f = (t, x = 0) => ({ match_id: "m1", t, ball: [x, 34], ball_height: x / 10,
  players: [{ id: "h1", n: 1, team: "home", x, y: 34 }] });
const state = (playing = true, extras = {}) => ({ seed: 12, match_id: "m1", t: 0, playing, speed: 1, ...extras });

test("metric projection keeps centre, axes and metres undistorted", () => {
  const p = pitchProjection(1600, 900), [x, y] = p.point(52.5, 34);
  assert.equal(x, 800); assert.equal(y, 474);
  assert.ok(Math.abs((p.point(1, 0)[0] - p.point(0, 0)[0]) - (p.point(0, 0)[1] - p.point(0, 1)[1])) < 1e-9);
});
test("pass and airborne shot sample source midpoints and clamp endpoints", () => {
  const a = f(10, 20), b = f(12, 60), mid = interpolate(a, b, 11);
  assert.deepEqual(mid.ball, [40, 34]); assert.equal(mid.ball_height, 4);
  assert.equal(mid.players[0].x, 40); assert.equal(a.players[0].x, 20);
  assert.equal(interpolate(a, b, 9), a); assert.equal(interpolate(a, b, 13), b);
});

test('optional source motion interpolates distance and crosses the angle seam by the short arc',()=>{
  const a=f(10,20),b=f(12,26);
  a.players[0].motion={heading:Math.PI-.1,speed:3,distance:120};
  b.players[0].motion={heading:-Math.PI+.1,speed:3,distance:126};
  const p=interpolate(a,b,11).players[0];
  assert.equal(p.x,23);assert.equal(p.motion.distance,123);assert.equal(p.motion.speed,3);
  assert.ok(Math.abs(Math.abs(p.motion.heading)-Math.PI)<1e-10);
  for(const bad of [{heading:NaN,speed:3,distance:0},{heading:0,speed:-1,distance:0},{heading:0,speed:3,distance:-1}]){
    assert.equal(validFrame({...a,players:[{...a.players[0],motion:bad}]}),false);
  }
  delete b.players[0].motion;
  assert.equal(interpolate(a,b,11).players[0].motion,undefined,'mixed legacy metadata cannot freeze an old source gait');
});
test("substitution and discontinuous or foreign frames never blend rosters or games", () => {
  const a = f(1, 10), b = f(2, 20); b.players[0].id = "h2";
  assert.equal(interpolate(a, b, 1.5).players[0].id, "h1");
  assert.equal(interpolate(a, b, 2).players[0].id, "h2");
  assert.equal(interpolate(a, f(5, 70), 3), a);
  assert.equal(interpolate(a, { ...b, match_id: "m2" }, 1.5), a);
});
test("time sampling is refresh-rate independent, bounded and pauses exactly", () => {
  const t = new FrameTimeline(); t.sync(state(), 0); t.push(f(1, 10), 0); t.push(f(1.1, 20), 100);
  assert.ok(Math.abs(t.sample(150).ball[0] - 15) < 1e-8);
  for (let n = 0; n < 10; n++) t.sample(150);
  assert.ok(Math.abs(t.sample(150).ball[0] - 15) < 1e-8);
  assert.equal(t.sample(10000).ball[0], 20);
  t.sync(state(false, { t: 1.1 }), 150);
  assert.deepEqual(t.sample(200), t.sample(20000));
  t.sync(state(true, { t: 1.1, speed: 2 }), 200);
  assert.equal(t.sample(260).ball[0], 20);
  t.freeze(220); assert.deepEqual(t.sample(220), t.sample(900));
});
test("seek/reset clears old positions, waits for state and rejects stale identity", () => {
  const t = new FrameTimeline(); t.sync(state(), 0); t.push(f(50, 90), 0);
  t.beginJump(); assert.equal(t.sample(0), null); assert.equal(t.push(f(51), 0), false);
  t.sync(state(false, { t: 2 }), 1); t.push(f(2, 5), 2); assert.equal(t.sample(2).ball[0], 5);
  t.sync(state(false, { seed: 3, match_id: "m2" }), 3);
  assert.equal(t.sample(3), null); assert.equal(t.push(f(60), 3), false);
  assert.equal(t.push({ ...f(0), match_id: "m2" }, 4), true);
});
test("out-of-order, repeated, malformed and excessive frames cannot poison buffer", () => {
  const t = new FrameTimeline(); t.sync(state(), 0);
  for (let i = 0; i < 20; i++) t.push(f(i), i);
  assert.equal(t.frames.length, 4); assert.equal(t.push(f(18), 21), false);
  assert.equal(t.push(f(19), 21), false);
  for (const bad of [{ ...f(20), t: NaN }, { ...f(20), ball_height: -1 }, { ...f(20), ball: [Infinity, 2] },
    { ...f(20), players: [null] }, { ...f(20), ball: [2, 90] },
    { ...f(20), players: [f(0).players[0], f(0).players[0]] }]) {
    assert.equal(validFrame(bad), false); assert.equal(t.push(bad, 22), false);
  }
  assert.equal(t.frames.at(-1).t, 19);
  assert.equal(t.sample(1000).t, 19);
});
test("optional transport run identity is honoured without creating client run IDs", () => {
  const t = new FrameTimeline(); t.sync(state(true, { run_id: "r2" }), 0);
  assert.equal(t.push({ ...f(0), run_id: "r1" }, 0), false);
  assert.equal(t.push({ ...f(0), run_id: "r2" }, 0), true);
});
test("paused packets use source endpoints without residual interpolation", () => {
  const t = new FrameTimeline(); t.sync(state(false), 0);
  t.push(f(1, 10), 0); t.push(f(1.1, 20), 100);
  assert.equal(t.sample(100).ball[0], 20);
  assert.deepEqual(t.sample(100), t.sample(10000));
});
test("height has gentle bounded size, lift and shadow, with grounded baseline", () => {
  const low = ballAppearance(0, 10), high = ballAppearance(4, 10);
  assert.equal(low.lift, 0); assert.equal(high.lift, 18);
  assert.ok(high.radius > low.radius && high.shadowOpacity < low.shadowOpacity);
  assert.equal(ballAppearance(100, 10).lift, 20);
  assert.deepEqual(ballAppearance(NaN, 10), low);
});
test("resume and speed changes cannot rewind into the interpolation buffer", () => {
  const t = new FrameTimeline(); t.sync(state(), 0); t.push(f(1, 10), 0); t.push(f(1.1, 20), 100);
  t.sync(state(false, { t: 1.1 }), 150); assert.equal(t.sample(150).ball[0], 20);
  t.sync(state(true, { t: 1.1 }), 200); assert.equal(t.sample(200).ball[0], 20);
  t.push(f(1.2, 30), 250); t.sync(state(true, { t: 1.2, speed: 4 }), 260);
  assert.equal(t.sample(260).ball[0], 30);
});
