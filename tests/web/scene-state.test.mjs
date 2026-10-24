import test from "node:test";
import assert from "node:assert/strict";
import * as T from "../../web/vendor/three/three.module.js";
import { worldPosition, playerPose, cameraView, qualitySettings, SceneMotion } from "../../web/scene-state.mjs";
import { buildFootballer, Footballers } from "../../web/footballers.mjs";
const player = (x = 10, y = 34, id = "h1", team = "home") => ({ id, x, y, n: 7, team, role: "FW" });
const frame = (t, players = [player()], match_id = "m1", extra = {}) => ({ t, players, match_id, ...extra });
const teams = { home: { colour: "#2678b9" }, away: { colour: "#e9e4d6" } };

test("world uses exact metric axes and source ball height", () => {
  assert.deepEqual(worldPosition(52.5, 34), [0, 0, 0]);
  assert.deepEqual(worldPosition(0, 0, 3.2), [-52.5, 3.2, 34]);
  assert.deepEqual(worldPosition(105, 68), [52.5, 0, -34]);
});
test("stride follows source velocity, clamps teleports and never uses wall time", () => {
  const old = { ...player(10), t: 1, heading: 0 };
  const pose = playerPose(old, player(10.5), 1.1);
  assert.ok(Math.abs(pose.speed - 5) < 1e-10); assert.equal(pose.heading, Math.PI / 2);
  assert.deepEqual(playerPose(old, player(10.5), 1.1), pose);
  assert.equal(playerPose(old, player(90), 8).speed, 0);
  assert.equal(playerPose(old, player(90), 0).speed, 0);
  assert.equal(playerPose(old, player(90), 1.1).speed, 9);
});
test("same paused frame freezes limbs, substitutions and run/seek reset history", () => {
  const motion = new SceneMotion(); motion.update(frame(1));
  const moving = motion.update(frame(1.1, [player(10.5)])).get("h1");
  assert.ok(moving.speed > 0); assert.strictEqual(motion.update(frame(1.1, [player(10.5)])).get("h1"), moving);
  assert.equal(motion.update(frame(0.5)).get("h1").speed, 0);
  assert.equal(motion.update(frame(0.6, [player(90)], "m2")).get("h1").speed, 0);
  assert.equal(motion.update(frame(0.7, [player(80)], "m2", { run_id: "r2" })).get("h1").speed, 0);
  motion.update(frame(0.8, [player(40, 34, "sub")])); assert.deepEqual([...motion.players.keys()], ["sub"]);
  motion.reset(); assert.equal(motion.players.size, 0);
});
test("roster/history remain bounded through 1000 changes", () => {
  const motion = new SceneMotion();
  for (let i = 0; i < 1000; i++) motion.update(frame(i / 20, [player(40, 34, `sub-${i}`)]));
  assert.equal(motion.players.size, 1);
});
test("camera keeps all pitch corners visible at desktop and mobile aspect ratios", () => {
  for (const aspect of [16 / 9, 391 / 220, 0.46, 3]) for (const ball of [[0, 0], [105, 68]]) {
    const view = cameraView(aspect, false, ball, "wide"), camera = new T.PerspectiveCamera(view.fov, aspect, 0.1, 500);
    camera.position.set(...view.position); camera.lookAt(...view.target); camera.updateMatrixWorld();
    for (const x of [0, 105]) for (const y of [0, 68]) {
      const projected = new T.Vector3(...worldPosition(x, y)).project(camera);
      assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1 && projected.z < 1, JSON.stringify({ aspect, x, y, projected }));
    }
  }
});
test("broadcast framing keeps the ball clear of the screen edges throughout the pitch", () => {
  for (const x of [0, 26.25, 52.5, 78.75, 105]) for (const y of [0, 34, 68]) {
    const view = cameraView(16 / 9, false, [x, y]), camera = new T.PerspectiveCamera(view.fov, 16 / 9, 0.1, 500);
    camera.position.set(...view.position); camera.lookAt(...view.target); camera.updateMatrixWorld();
    const projected = new T.Vector3(...worldPosition(x, y)).project(camera);
    assert.ok(Math.abs(projected.x) < 0.85 && Math.abs(projected.y) < 0.85, JSON.stringify({ x, y, projected }));
  }
});
test("reduced motion fixes camera; low power reduces GPU cost without changing source", () => {
  assert.deepEqual(cameraView(16 / 9, true, [0, 0]), cameraView(16 / 9, true, [105, 68]));
  assert.deepEqual(qualitySettings("low", 3), { pixelRatio: 1, shadows: false, shadowSize: 0 });
  assert.deepEqual(qualitySettings("high", 3), { pixelRatio: 1.5, shadows: true, shadowSize: 2048 });
});
test("original human geometry has body, head, articulated limbs and keeper kit", () => {
  const p = player(), a = buildFootballer(p, teams), keeper = buildFootballer({ ...p, role: "GK" }, teams);
  assert.equal(a.legs.length, 2); assert.equal(a.arms.length, 2);
  const boot = a.legs[0].knee.children.at(-1), before = new T.Vector3(), after = new T.Vector3();
  a.root.updateMatrixWorld(true); boot.getWorldPosition(before);
  a.legs[0].joint.rotation.x = 0.5; a.root.updateMatrixWorld(true); boot.getWorldPosition(after);
  assert.ok(before.distanceTo(after) > 0.3, "hip articulation must move the boot, not just a detached decoration");
  assert.notEqual(a.parts[0].color, keeper.parts[0].color);
  assert.equal(a.parts[0].color, teams.home.colour);
});
test("22 articulated players batch into 3 draws; substitutions and hiding release actor history", () => {
  const scene = new T.Scene(), footballers = new Footballers(scene), motion = new SceneMotion();
  const players = Array.from({ length: 22 }, (_, i) => player(i * 4, 34, `p${i}`, i < 11 ? "home" : "away"));
  const f = frame(1, players); footballers.update(f, motion.update(f), teams);
  assert.equal(footballers.actors.size, 22); assert.equal(scene.children.length, 3);
  for (const mesh of scene.children) {
    assert.ok(mesh.isInstancedMesh && mesh.count > 0 && mesh.count <= 660);
    assert.ok([...mesh.instanceMatrix.array.slice(0, mesh.count * 16)].every(Number.isFinite));
  }
  const sub = frame(2, [player(30, 30, "new")]); footballers.update(sub, motion.update(sub), teams);
  assert.deepEqual([...footballers.actors.keys()], ["new"]);
  footballers.hide(); assert.equal(footballers.actors.size, 0); assert.ok(scene.children.every(m => m.count === 0));
});
