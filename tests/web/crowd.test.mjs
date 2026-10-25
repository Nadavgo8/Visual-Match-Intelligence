import test from "node:test";
import assert from "node:assert/strict";
import * as T from "../../web/vendor/three/three.module.js";
import { crowdPresentation, createCrowdUniforms, updateCrowd, createCrowd, crowdLayout, standAisles } from "../../web/crowd.mjs";
test("quiet and loud crowd encode delivered crowd, independent of attack or combined level", () => {
  const quietAttack = crowdPresentation({ crowd: 0, attack: 1, level: 0.2 });
  assert.equal(quietAttack.standing, 0); assert.equal(quietAttack.arms, 0);
  const loudNoAttack = crowdPresentation({ crowd: 1, attack: 0, level: 0.8 });
  assert.equal(loudNoAttack.standing, 1); assert.equal(loudNoAttack.arms, 2.35);
  assert.deepEqual(crowdPresentation({ crowd: 0.5, attack: 0 }), crowdPresentation({ crowd: 0.5, attack: 1 }));
});
test("spectators face the pitch-facing edge of their stand rather than its back", () => {
  const mesh = createCrowd(78, 24, createCrowdUniforms()), matrix = new T.Matrix4();
  for (const index of [0, 200, mesh.count - 1]) {
    mesh.getMatrixAt(index, matrix);
    const facing = new T.Vector3(0, 0, 1).transformDirection(matrix);
    assert.ok(facing.z < -0.95, `spectator ${index} faces away from the pitch`);
  }
  mesh.dispose(); mesh.geometry.dispose(); mesh.material.dispose();
});
test("missing crowd stays unavailable instead of becoming silence or synthetic cheering", () => {
  for (const crowd of [undefined, null, NaN, Infinity, -0.1, 1.1, "1"]) {
    const view = crowdPresentation({ crowd }); assert.equal(view.available, false); assert.equal(view.level, null);
    assert.equal(view.arms, 0); assert.equal(view.sway, 0);
  }
  assert.equal(crowdPresentation({ crowd: 0 }).available, true);
});
test("source time freezes crowd; reduced motion suppresses sway and arm animation", () => {
  const uniforms = createCrowdUniforms(); updateCrowd(uniforms, { crowd: 1 }, 10, false);
  const old = structuredClone(uniforms); updateCrowd(uniforms, { crowd: 1 }, 10, false); assert.deepEqual(uniforms, old);
  updateCrowd(uniforms, { crowd: 1 }, 10, true); assert.equal(uniforms.crowdArms.value, 0); assert.equal(uniforms.crowdSway.value, 0);
  updateCrowd(uniforms, null, 0, false); assert.equal(uniforms.crowdStanding.value, 0);
});
test("dense crowd uses one bounded instanced draw and source-driven shader uniforms", () => {
  const uniforms = createCrowdUniforms(), mesh = createCrowd(78, 24, uniforms);
  assert.equal(mesh.count, 2921); assert.ok(mesh.geometry.getAttribute("crowdPart"));
  const shader = { uniforms: {}, vertexShader: "#include <color_vertex>\n#include <begin_vertex>\n#include <beginnormal_vertex>" }; mesh.material.onBeforeCompile(shader);
  assert.strictEqual(shader.uniforms.crowdTime, uniforms.crowdTime); assert.match(shader.vertexShader, /crowdTime/);
  assert.match(shader.vertexShader, /crowdTint < 1.5 \? instanceColor.rgb/, "shirt colours must not tint spectators' skin");
  assert.match(shader.vertexShader, /objectNormal.xy = mat2/, "raised arms must keep lighting consistent with their rotation");
  mesh.dispose(); mesh.geometry.dispose(); mesh.material.dispose();
});
test("stairs/concourse remain clear and stand variety stays deterministic without repeating sides", () => {
  const left = crowdLayout(78,24,2), right = crowdLayout(78,24,3);
  assert.deepEqual(left,crowdLayout(78,24,2)); assert.notDeepEqual(left,right);
  for (const seat of left) {
    assert.ok(standAisles(78).every(aisle=>Math.abs(seat.x-aisle)>=0.7));
    assert.notEqual(seat.z,12*0.76); assert.ok(seat.seed>=0 && seat.seed<1);
  }
  for (const args of [[NaN,24],[500,24],[78,Infinity],[78,1.5],[78,33]]) assert.throws(()=>crowdLayout(...args),RangeError);
});
