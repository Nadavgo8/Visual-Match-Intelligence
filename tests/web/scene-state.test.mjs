import test from "node:test";
import assert from "node:assert/strict";
import * as T from "../../web/vendor/three/three.module.js";
import { worldPosition, playerPose, cameraView, qualitySettings, SceneMotion } from "../../web/scene-state.mjs";
const player = (x = 10, y = 34, id = "h1", team = "home") => ({ id, x, y, n: 7, team, role: "FW" });
const frame = (t, players = [player()], match_id = "m1", extra = {}) => ({ t, players, match_id, ...extra });

test("world uses exact metric axes and source ball height", () => {
  assert.deepEqual(worldPosition(52.5, 34), [0, 0, 0]);
  assert.deepEqual(worldPosition(0, 0, 3.2), [-52.5, 3.2, 34]);
  assert.deepEqual(worldPosition(105, 68), [52.5, 0, -34]);
});
test("stride follows source velocity, clamps teleports and never uses wall time", () => {
  const old = { ...player(10), t: 1, heading: Math.PI / 2 };
  const pose = playerPose(old, player(10.5), 1.1);
  assert.ok(Math.abs(pose.speed - 5) < 1e-10); assert.equal(pose.heading, Math.PI / 2);
  assert.deepEqual(playerPose(old, player(10.5), 1.1), pose);
  assert.equal(playerPose(old, player(90), 8).speed, 0);
  assert.equal(playerPose(old, player(90), 0).speed, 0);
  assert.equal(playerPose(old, player(90), 1.1).speed, 9);
  assert.equal(playerPose({ ...player(10), t: 1 }, player(10.5), 1.1).heading, Math.PI / 2);
});
test("a player turns through source time instead of snapping 180 degrees in one frame", () => {
  let pose = { ...player(10), t: 1, heading: Math.PI / 2 };
  const first = playerPose(pose, player(9.75), 1.05);
  const turn = Math.abs(Math.atan2(Math.sin(first.heading-pose.heading),Math.cos(first.heading-pose.heading)));
  assert.ok(turn > 0 && turn <= .46, "turn speed stays below nine radians per source second");
  assert.ok(Math.abs(first.speed-5)<1e-8);
  pose = first;
  for(let step=2;step<=10;step++) pose=playerPose(pose,player(10-step*.25),1+step*.05);
  assert.ok(Math.abs(Math.atan2(Math.sin(pose.heading+Math.PI/2),Math.cos(pose.heading+Math.PI/2)))<1e-8);
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
test("travel distance drives gait independently of display refresh rate and resets on seek", () => {
  const sample = steps => {
    const motion = new SceneMotion();
    for (let i = 0; i <= steps; i++) motion.update(frame(1 + i / steps, [player(10 + i * 5 / steps)]));
    assert.ok(Math.abs(motion.players.get("h1").distance - 5) < 1e-8);
    motion.update(frame(0.5, [player(50)])); assert.equal(motion.players.get("h1").distance, 0);
  };
  sample(20); sample(60);
});
test("32x playback animates a valid 1.6-second source interval without treating it as seek", () => {
  const motion = new SceneMotion(); motion.update(frame(1, [player(10)]));
  const pose = motion.update(frame(2.6, [player(18)])).get("h1");
  assert.equal(pose.speed, 5); assert.notEqual(pose.stride, 0);
  for (const [t, expected] of [[3, 5], [3.001, 0]]) {
    const boundary = new SceneMotion(); boundary.update(frame(1, [player(10)]));
    assert.equal(boundary.update(frame(t, [player(20)])).get("h1").speed, expected);
  }
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
    for (const height of [0, 3]) {
      const projected = new T.Vector3(...worldPosition(x, y, height)).project(camera);
      assert.ok(Math.abs(projected.x) < 0.85 && Math.abs(projected.y) < 0.85, JSON.stringify({ x, y, height, projected }));
    }
  }
});

test("broadcast camera stays at the central gantry while panning towards either goal", () => {
  for (const x of [0, 10, 52.5, 95, 105]) for (const y of [0, 34, 68]) {
    const view = cameraView(16 / 9, false, [x, y]);
    assert.ok(Math.abs(view.position[0]) <= 22, "the camera must not travel behind an end-stand canopy");
    assert.ok(view.position[2] >= 60, "the camera stays outside the near touchline");
  }
});

test("broadcast composition keeps delivered crowd context visible across both halves", () => {
  for (const [ball, standX] of [[[10,34],-40], [[52.5,34],0], [[95,34],40]]) {
    const view=cameraView(16/9,false,ball), camera=new T.PerspectiveCamera(view.fov,16/9,.1,500);
    camera.position.set(...view.position);camera.lookAt(...view.target);camera.updateMatrixWorld();
    const audience=new T.Vector3(standX,6,-43).project(camera);
    assert.ok(Math.abs(audience.x)<.9 && audience.y>0 && audience.y<.95 && audience.z<1,
      `crowd context is cropped for ball ${ball}: ${audience.toArray()}`);
  }
});
test("reduced motion fixes camera; low power reduces GPU cost without changing source", () => {
  assert.deepEqual(cameraView(16 / 9, true, [0, 0]), cameraView(16 / 9, true, [105, 68]));
  assert.deepEqual(qualitySettings("low", 3), { pixelRatio: 1, shadows: false, shadowSize: 0 });
  assert.deepEqual(qualitySettings("high", 3), { pixelRatio: 1.5, shadows: true, shadowSize: 2048 });
});

test("broadcast retains a forty-metre action span with crowd context behind the play", () => {
  for (const y of [0, 34, 68]) {
    const view = cameraView(16 / 9, false, [52.5, y]);
    const camera = new T.PerspectiveCamera(view.fov, 16 / 9, .1, 500);
    camera.position.set(...view.position); camera.lookAt(...view.target); camera.updateMatrixWorld();
    // Two receivers twenty metres either side of the ball must fit in the
    // active view. The far-side case previously showed mostly spectators.
    for (const x of [32.5, 72.5]) {
      const point = new T.Vector3(...worldPosition(x, y)).project(camera);
      assert.ok(Math.abs(point.x) < .85 && Math.abs(point.y) < .85, `action cropped at ${x},${y}: ${point.toArray()}`);
    }
    // A spectator-height landmark at the front of the far stand stays in the
    // background band. This does not measure the bounding box of every seat.
    const crowdFront = new T.Vector3(0, 1.8, -43).project(camera);
    assert.ok(crowdFront.y > .3, `crowd front drops into the action at ball y=${y}: ${crowdFront.y}`);
  }
});

test("ball rolls only with delivered displacement, and resets on seek or run replacement", () => {
  const motion=new SceneMotion(), frame=(t,ball,run_id="a")=>({match_id:"m",run_id,t,ball,players:[]});
  motion.update(frame(1,[10,34]));
  const still={...motion.ballRoll}; motion.update(frame(1.1,[10,34]));
  assert.deepEqual(motion.ballRoll,still,"a stationary ball cannot rotate with the clock");
  motion.update(frame(1.2,[10.16,34]));
  assert.ok(Math.abs(motion.ballRoll.z+1)<1e-10);
  const paused={...motion.ballRoll}; motion.update(frame(1.2,[10.16,34])); assert.deepEqual(motion.ballRoll,paused);
  motion.update(frame(0,[10,34])); assert.deepEqual(motion.ballRoll,{x:0,z:0});
  motion.update(frame(0.1,[10,34.16])); assert.ok(Math.abs(motion.ballRoll.x+1)<1e-10);
  motion.update(frame(0.1,[10,34.16],"b")); assert.deepEqual(motion.ballRoll,{x:0,z:0});
});
