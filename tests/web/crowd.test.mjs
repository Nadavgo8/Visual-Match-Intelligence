import test from "node:test";
import assert from "node:assert/strict";
import { crowdPresentation, createCrowdUniforms, updateCrowd, createCrowd } from "../../web/crowd.mjs";
test("quiet and loud crowd encode delivered crowd, independent of attack or combined level", () => {
  const quietAttack = crowdPresentation({ crowd: 0, attack: 1, level: 0.2 });
  assert.equal(quietAttack.standing, 0); assert.equal(quietAttack.arms, 0);
  const loudNoAttack = crowdPresentation({ crowd: 1, attack: 0, level: 0.8 });
  assert.equal(loudNoAttack.standing, 0.68); assert.equal(loudNoAttack.arms, 2.35);
  assert.deepEqual(crowdPresentation({ crowd: 0.5, attack: 0 }), crowdPresentation({ crowd: 0.5, attack: 1 }));
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
  assert.equal(mesh.count, Math.floor(78 / 0.56) * 24); assert.ok(mesh.geometry.getAttribute("crowdPart"));
  const shader = { uniforms: {}, vertexShader: "#include <color_vertex>\n#include <begin_vertex>" }; mesh.material.onBeforeCompile(shader);
  assert.strictEqual(shader.uniforms.crowdTime, uniforms.crowdTime); assert.match(shader.vertexShader, /crowdTime/);
  assert.match(shader.vertexShader, /mix\(vec3\(1.0\), instanceColor.rgb, crowdTint\)/, "shirt colours must not tint spectators' skin");
});
