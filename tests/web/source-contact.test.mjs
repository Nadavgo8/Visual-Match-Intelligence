import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import * as T from "../../web/vendor/three/three.module.js";
import { DetailedFootballers, sourceTouch, touchTarget, forehead, BALL_RADIUS } from "../../web/athlete.mjs";
import { SceneMotion } from "../../web/scene-state.mjs";
import { interpolate, validFrame, validContact, CONTACT_APPROACH } from "../../web/match-motion.mjs";

const data = JSON.parse(await readFile(new URL("../../web/assets/athlete/athlete.json", import.meta.url)));
const teams = { home: { colour: "#2678b9" }, away: { colour: "#e9e4d6" } };
const motion = { heading: Math.PI / 2, facing: Math.PI / 2, speed: 2, distance: 50, gait_cycles: 12.3 };
const touch = (effector, target, phase = 0, kind = "release") =>
  ({ kind, effector, start_t: 10, end_t: 10.32, phase, target, heading: Math.PI / 2 });
const player = (contact, role = "FW") => ({ id: "h1", x: 40, y: 34, n: 7, role, team: "home", motion, contact });
const frameOf = (p, t = 10) => ({ t, match_id: "m", run_id: 1, players: [p], ball: p.contact?.target.slice(0, 2) ?? [45, 34],
  ball_height: p.contact?.target[2] ?? 0, ball_in_play: true });

function pose(p, t, actors = new DetailedFootballers(new T.Scene(), data), motionState = new SceneMotion()) {
  const frame = frameOf(p, t);
  actors.update(frame, motionState.update(frame), teams);
  return { actors, actor: actors.actors.get(p.id), ball: p.contact && touchTarget(p.contact.target) };
}
const at = (actor, name) => actor.joints[name].getWorldPosition(new T.Vector3());
const bones = actor => actor.skeleton.bones.map(b => [...b.quaternion.toArray(), ...b.position.toArray()]);

test("a source foot strike puts the nearer boot on the drawn ball without moving the tracked root or ball", () => {
  for (const [y, side] of [[33.85, "R"], [34.15, "L"]]) {
    const p = player(touch("foot", [40.55, y, 0]));
    const { actors, actor, ball } = pose(p, 10);
    // The ankle sits behind the ball surface: radius plus the boot's toe.
    assert.ok(at(actor, `foot.${side}`).distanceTo(ball) <= BALL_RADIUS + .08, `${side} boot misses the ball`);
    assert.equal(actor.root.position.x, p.x - 52.5); assert.equal(actor.root.position.z, 34 - p.y);
    actors.dispose();
  }
});

test("keeper hands reach a chest-high ball, and a low ball by crouching with planted feet", () => {
  for (const target of [[40.5, 34, 1.1], [40.6, 34.3, .3]]) {
    const { actors, actor, ball } = pose(player(touch("hands", target, 0, "save"), "GK"), 10);
    const nearest = Math.min(at(actor, "wrist.L").distanceTo(ball), at(actor, "wrist.R").distanceTo(ball));
    assert.ok(nearest <= BALL_RADIUS + .05, `hands miss ball at height ${target[2]}: ${nearest}`);
    for (const side of ["L", "R"]) assert.ok(at(actor, `foot.${side}`).y > -.02, "a crouch pushes a foot below the pitch");
    assert.equal(actor.root.position.x, 40 - 52.5);
    actors.dispose();
  }
});

test("a header brings the forehead to the ball surface, jumping for a high ball", () => {
  for (const height of [1.75, 1.95]) {
    const { actors, actor, ball } = pose(player(touch("head", [40.3, 34, height])), 10);
    assert.ok(Math.abs(forehead(actor).distanceTo(ball) - BALL_RADIUS) <= .05, `forehead misses ball at ${height}`);
    actors.dispose();
  }
});

test("the touch approaches from the buffered frame, peaks at contact and releases after the follow-through", () => {
  const c = touch("foot", [40.55, 33.85, 0]);
  const weight = phase => sourceTouch({ ...c, phase })?.weight ?? 0;
  assert.equal(weight(-(CONTACT_APPROACH + .01) / .32), 0);
  assert.ok(weight(-.5 * CONTACT_APPROACH / .32) > 0 && weight(-.5 * CONTACT_APPROACH / .32) < 1);
  assert.equal(weight(0), 1);
  assert.ok(weight(.5) > 0 && weight(.5) < 1);
  assert.equal(weight(1), 0);
  // Foot control is left to the gait; a ball held in the hands stays held.
  assert.equal(sourceTouch({ ...c, start_t: 10, end_t: 10, phase: 1, kind: "control" }), null);
  assert.equal(sourceTouch({ ...c, effector: "hands", start_t: 10, end_t: 10, phase: 1, kind: "control" }).weight, 1);
  // Mid follow-through the boot is between its gait position and the ball.
  const ball = touchTarget(c.target);
  const strike = pose(player({ ...c, phase: 0 }), 10), follow = pose(player({ ...c, phase: .5 }), 10.16);
  const free = pose(player(undefined), 10);
  const d = r => at(r.actor, "foot.R").distanceTo(ball);
  assert.ok(d(strike) < d(follow) && d(follow) < d(free));
  for (const r of [strike, follow, free]) r.actors.dispose();
});

test("the same source time gives the same body after pause, seek or a fresh connection", () => {
  const c = touch("head", [40.3, 34, 1.9], .25);
  const fresh = pose(player(c), 10.08);
  const seen = new DetailedFootballers(new T.Scene(), data), motionState = new SceneMotion();
  for (const t of [3, 9.5, 9.9, 10.04]) pose({ ...player(touch("foot", [40.55, 33.85, 0], 0)), contact: undefined }, t, seen, motionState);
  pose(player(touch("foot", [40.55, 33.85, 0])), 30, seen, motionState); // seek away
  const back = pose(player(c), 10.08, seen, motionState);
  assert.deepEqual(bones(back.actor), bones(fresh.actor));
  const again = pose(player(c), 10.08, seen, motionState); // paused: same frame twice
  assert.deepEqual(bones(again.actor), bones(fresh.actor));
  fresh.actors.dispose(); seen.dispose();
});

test("source contact is validated and carried through interpolation, with an approach from the next frame", () => {
  const strike = touch("foot", [40.5, 34, 0], 0);
  const a = { ...frameOf(player(undefined), 9.9), players: [{ ...player(undefined), motion: { ...motion, facing: 1, gait_cycles: 12 } }] };
  const b = { ...frameOf(player(strike), 10), players: [{ ...player(strike), motion: { ...motion, facing: 1.2, gait_cycles: 12.2 } }] };
  assert.ok(validFrame(a) && validFrame(b));
  assert.equal(validContact({ ...strike, effector: "knee" }), false);
  assert.equal(validFrame({ ...b, players: [{ ...b.players[0], contact: { ...strike, target: [1, 2] } }] }), false);
  const mid = interpolate(a, b, 9.95).players[0];
  assert.ok(Math.abs(mid.motion.facing - 1.1) < 1e-9 && Math.abs(mid.motion.gait_cycles - 12.1) < 1e-9);
  // 0.05 s before the delivered strike: the approach shows, with a negative phase.
  assert.equal(mid.contact.start_t, 10); assert.ok(mid.contact.phase < 0);
  // Too early for the approach: no contact is invented.
  assert.equal(interpolate({ ...a, t: 9.7 }, b, 9.75).players[0].contact, undefined);
  // An earlier touch in progress keeps running until its end, then is dropped.
  const after = { ...b, t: 10.4, players: [{ ...b.players[0], contact: undefined }] };
  assert.ok(Math.abs(interpolate(b, after, 10.16).players[0].contact.phase - .5) < 1e-9);
  assert.equal(interpolate(b, after, 10.35).players[0].contact, undefined);
});

test("real demo-match contacts: boot, hands and forehead meet the drawn ball, even with the ball behind the body", async () => {
  const { contacts } = JSON.parse(await readFile(new URL("./source-contacts.fixture.json", import.meta.url)));
  const tolerance = { foot: BALL_RADIUS + .08, hands: BALL_RADIUS + .05, head: .05 };
  assert.deepEqual(new Set(contacts.map(c => c.frame.players.find(p => p.id === c.pid).contact.effector)), new Set(["foot", "hands", "head"]));
  for (const { frame, pid } of contacts) {
    assert.ok(validFrame(frame));
    const actors = new DetailedFootballers(new T.Scene(), data), motionState = new SceneMotion();
    actors.update(frame, motionState.update(frame), teams);
    const actor = actors.actors.get(pid), p = frame.players.find(q => q.id === pid), c = p.contact, ball = touchTarget(c.target);
    const d = c.effector === "foot" ? Math.min(at(actor, "foot.L").distanceTo(ball), at(actor, "foot.R").distanceTo(ball))
      : c.effector === "hands" ? Math.min(at(actor, "wrist.L").distanceTo(ball), at(actor, "wrist.R").distanceTo(ball))
      : Math.abs(forehead(actor).distanceTo(ball) - BALL_RADIUS);
    assert.ok(d <= tolerance[c.effector], `${c.kind}/${c.effector} at ${frame.t}: ${d}`);
    assert.equal(actor.root.position.x, p.x - 52.5); assert.equal(actor.root.position.z, 34 - p.y);
    actors.dispose();
  }
});
