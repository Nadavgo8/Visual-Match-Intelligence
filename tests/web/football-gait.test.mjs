import test from "node:test";
import assert from "node:assert/strict";
import { legAngles, footballGait } from "../../web/football-gait.mjs";

test("two-bone legs reach an independently calculated ankle without reversing the knee", () => {
  const upper = [0, -0.46, 0], lower = [0, -0.42, 0];
  for (const [y, z] of [[-0.82, 0], [-0.74, 0.25], [-0.74, -0.25], [-0.56, 0.2]]) {
    const { hip, knee, ankle } = legAngles(upper, lower, y, z);
    // Forward kinematics is independent of the inverse solver.
    const actualY = -0.46 * Math.cos(hip) - 0.42 * Math.cos(hip + knee);
    const actualZ = -0.46 * Math.sin(hip) - 0.42 * Math.sin(hip + knee);
    assert.ok(Math.abs(actualY - y) < 1e-8);
    assert.ok(Math.abs(actualZ - z) < 1e-8);
    assert.ok(knee > 0 && knee < Math.PI);
    assert.ok(Math.abs(hip + knee + ankle) < 1e-8, "support foot stays level");
  }
});

test("unreachable foot targets stay finite and within leg length", () => {
  for (const [y, z] of [[0, 0], [-10, 10], [-0.01, 0]]) {
    const pose = legAngles([0, -0.46, 0], [0, -0.42, 0], y, z);
    assert.ok(Object.values(pose).every(Number.isFinite));
    assert.ok(pose.knee >= 0 && pose.knee <= Math.PI);
  }
});

test("invalid or zero-length legs fail before producing non-finite GPU transforms", () => {
  for (const [upper,lower,y,z] of [[null,[0,-.4,0],-.7,0],[[0,-.4],[0,-.4,0],-.7,0],
    [[0,-.4,0],[0,-.4,0],NaN,0],[[0,0,0],[0,-.4,0],-.7,0],[[0,-.4,0],[0,0,0],-.7,0],
    [[0,-1e308,0],[0,-.4,0],-.7,0],[[0,-.4,0],[0,-1e308,0],-.7,0]]) {
    assert.throws(()=>legAngles(upper,lower,y,z),RangeError);
  }
  for (const speed of [NaN,Infinity,-1]) {
    const gait=footballGait(speed,NaN,false); assert.equal(gait.left.z,0); assert.equal(gait.left.lift,0);
  }
});

test("gait is a pure function of delivered displacement, with a planted half and a lifted return", () => {
  const stance = footballGait(5, 0.25, false), swing = footballGait(5, 0.75, false);
  assert.equal(stance.left.lift, 0);
  assert.ok(swing.left.lift > 0.1);
  assert.equal(swing.right.lift, 0);
  assert.deepEqual(footballGait(5, 0.75, false), swing, "pause cannot advance a pose");
  const stopped = footballGait(0, 0.75, false);
  assert.equal(stopped.left.lift, 0); assert.equal(stopped.right.lift, 0);
  assert.equal(stopped.left.z, 0); assert.equal(stopped.right.z, 0);
});

test("goalkeepers have a balanced ready stance without inventing a dive or a save", () => {
  const field = footballGait(0, 0, false), keeper = footballGait(0, 0, true);
  assert.ok(keeper.pelvis < field.pelvis);
  assert.ok(keeper.armSpread > field.armSpread);
  assert.equal(keeper.left.lift, 0); assert.equal(keeper.right.lift, 0);
  assert.deepEqual(footballGait(100, -2, false), footballGait(9, 0, false));
});
