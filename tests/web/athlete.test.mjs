import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import * as T from "../../web/vendor/three/three.module.js";
import { validateAthlete, athleteGeometry, createAthlete, DetailedFootballers } from "../../web/athlete.mjs";
import { SceneMotion } from "../../web/scene-state.mjs";
const bytes = await readFile(new URL("../../web/assets/athlete/athlete.json", import.meta.url));
const data = JSON.parse(bytes), teams = { home: { colour: "#2678b9" }, away: { colour: "#e9e4d6" } };
const p = { id: "h1", x: 40, y: 34, n: 7, role: "FW", team: "home" };
test("pinned CC0 athlete has complete anatomy, valid skinning and exact provenance", async () => {
  assert.strictEqual(validateAthlete(data), data);
  const provenance = JSON.parse(await readFile(new URL("../../web/assets/athlete/provenance.json", import.meta.url)));
  assert.equal(provenance.license, "CC0-1.0"); assert.equal(createHash("sha256").update(bytes).digest("hex"), provenance.athleteSHA256);
  const license = await readFile(new URL("../../web/assets/athlete/CC0.txt", import.meta.url));
  assert.equal(createHash("sha256").update(license).digest("hex"), provenance.files["CC0.txt"]);
  assert.equal(data.positions.length / 3, provenance.vertices); assert.ok(provenance.vertices > 13000 && provenance.vertices < 15000); assert.equal(data.bones.length, 22);
  assert.ok(data.regions.includes(0) && data.regions.includes(1) && data.regions.includes(2) && data.regions.includes(3) && data.regions.includes(4));
});
test("corrupt geometry, weights and cyclic skeletons fail closed before GPU allocation", () => {
  for (const mutate of [d => { d.indices[0] = -1; }, d => { d.positions[0] = NaN; },
    d => { d.skinWeights[0] = 2; }, d => { d.skinIndices[0] = 900; },
    d => { d.bones[0].parent = 0; }, d => { d.bones[0].parent = 1; d.bones[1].parent = 0; },
    d => { d.positions[0] = 1e20; }, d => { d.bones.find(b => b.name === "foot.L").name = "missing"; }]) {
    const bad = structuredClone(data); mutate(bad); assert.throws(() => validateAthlete(bad));
  }
});
test("local CC0 grass maps retain the recorded source bytes", async () => {
  const base = new URL("../../web/assets/turf/", import.meta.url);
  const provenance = JSON.parse(await readFile(new URL("provenance.json", base)));
  assert.equal(provenance.license, "CC0-1.0");
  for (const [name, expected] of Object.entries(provenance.files)) assert.equal(createHash("sha256").update(await readFile(new URL(name, base))).digest("hex"), expected);
});
test("real mesh binds an articulated skeleton and deforms attached foot vertices", () => {
  const base = athleteGeometry(data), actor = createAthlete(data, base, p, teams);
  actor.root.updateMatrixWorld(true); actor.skeleton.update();
  const footIndex = data.regions.findIndex((region, i) => region === 4 && data.positions[i * 3] > 0);
  const before = new T.Vector3().fromBufferAttribute(base.getAttribute("position"), footIndex);
  actor.mesh.applyBoneTransform(footIndex, before);
  actor.joints["upperleg01.L"].rotation.x = 0.55; actor.root.updateMatrixWorld(true); actor.skeleton.update();
  const after = new T.Vector3().fromBufferAttribute(base.getAttribute("position"), footIndex);
  actor.mesh.applyBoneTransform(footIndex, after); assert.ok(after.distanceTo(before) > 0.2);
  actor.dispose(); base.dispose();
});
test("hair surface normals face outward rather than disappearing through back-face culling", () => {
  const geometry = athleteGeometry(data), normals = geometry.getAttribute("normal");
  const index = data.regions.findIndex((region, i) => region === 5 && data.positions[i * 3] > 0.05);
  const radial = new T.Vector3(data.positions[index * 3], data.positions[index * 3 + 1] - 1.752, data.positions[index * 3 + 2] - 0.016);
  assert.ok(radial.dot(new T.Vector3().fromBufferAttribute(normals, index)) > 0); geometry.dispose();
});
test("detailed players pause deterministically and dispose substitutions without growth", () => {
  const scene = new T.Scene(), actors = new DetailedFootballers(scene, data), motion = new SceneMotion();
  const f = (t, players) => ({ t, match_id: "m", players });
  const a = f(1, [p]), b = f(1.1, [{ ...p, x: 40.5 }]);
  actors.update(a, motion.update(a), teams); actors.update(b, motion.update(b), teams);
  const root = actors.actors.get("h1").root, pose = root.toJSON();
  actors.update(b, motion.update(b), teams); assert.deepEqual(root.toJSON(), pose);
  for (let i = 0; i < 20; i++) { const next = f(2 + i, [{ ...p, id: `sub-${i}` }]); actors.update(next, motion.update(next), teams); }
  assert.equal(actors.actors.size, 1); assert.equal(scene.children.length, 1);
  actors.dispose(); assert.equal(scene.children.length, 0);
});
test("full 22-player roster shares immutable anatomy buffers and keeps keeper colours distinct", () => {
  const scene = new T.Scene(), actors = new DetailedFootballers(scene, data), motion = new SceneMotion();
  const players = Array.from({ length: 22 }, (_, i) => ({ ...p, id: `p${i}`, n: i + 1, team: i < 11 ? "home" : "away", role: i % 11 === 0 ? "GK" : "FW" }));
  const frame = { t: 1, match_id: "m", players }; actors.update(frame, motion.update(frame), teams);
  assert.equal(actors.actors.size, 22); assert.equal(scene.children.length, 22);
  const field = actors.actors.get("p1"), keeper = actors.actors.get("p0");
  assert.strictEqual(field.mesh.geometry.getAttribute("position"), keeper.mesh.geometry.getAttribute("position"));
  assert.notEqual(field.kitPalette[1].g, keeper.kitPalette[1].g);
  let sharedDisposals = 0; actors.base.addEventListener("dispose", () => sharedDisposals++);
  const changed = { ...frame, t: 2, players: players.slice(1) }; actors.update(changed, motion.update(changed), teams);
  assert.equal(sharedDisposals, 0); assert.equal(actors.actors.size, 21);
  actors.dispose(); assert.equal(scene.children.length, 0); assert.equal(sharedDisposals, 1);
});

test("running rig keeps a support sole near the turf and preserves the delivered player centre", () => {
  const actors = new DetailedFootballers(new T.Scene(),data), motion = new SceneMotion();
  const sole = data.regions.flatMap((region,i) => region===4 && data.positions[i*3+1]<0.055 ? [i] : []);
  assert.ok(sole.length>10);
  const vector = new T.Vector3();
  for (let i=0;i<30;i++) {
    const player={...p,x:40+i*0.3};
    const frame={match_id:"m",t:1+i*0.05,players:[player]};
    actors.update(frame,motion.update(frame),teams);
    const actor=actors.actors.get(p.id); actor.skeleton.update();
    const heights=sole.map(index=>{
      vector.fromBufferAttribute(actors.base.getAttribute("position"),index);
      actor.mesh.applyBoneTransform(index,vector); vector.applyMatrix4(actor.mesh.matrixWorld);
      return vector.y;
    });
    assert.ok(Math.min(...heights)>-0.025,`sole penetrates turf: ${Math.min(...heights)}`);
    assert.ok(Math.min(...heights)<0.12,`both feet float: ${Math.min(...heights)}`);
    assert.equal(actor.root.position.x,player.x-52.5); assert.equal(actor.root.position.z,34-player.y);
  }
  actors.dispose();
});

test("field players lower their arms from the mesh rest pose while keepers keep a wider ready stance", () => {
  const actors=new DetailedFootballers(new T.Scene(),data),motion=new SceneMotion();
  const frame={match_id:"m",t:1,players:[p,{...p,id:"gk",role:"GK",x:20}]};
  actors.update(frame,motion.update(frame),teams);
  const spread=(id,side)=>{
    const actor=actors.actors.get(id),wrist=new T.Vector3();
    actor.joints[`wrist.${side}`].getWorldPosition(wrist);actor.root.worldToLocal(wrist);
    return Math.abs(wrist.x);
  };
  for (const side of ["L","R"]) {
    assert.ok(spread(p.id,side)<0.36,`field-player arms remain in a spread rest pose: ${spread(p.id,side)}`);
    assert.ok(spread("gk",side)>spread(p.id,side)+0.12,"keeper readiness must remain visibly distinct");
  }
  actors.dispose();
});
