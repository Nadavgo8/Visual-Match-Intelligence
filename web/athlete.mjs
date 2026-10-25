import * as T from "./vendor/three/three.module.js";
import { footballGait, legAngles } from "./football-gait.mjs?v=3.9";

export function validateAthlete(data) {
  const n = data?.positions?.length / 3, bones = data?.bones;
  if (!Number.isInteger(n) || n < 1000 || n > 20000 || !Array.isArray(bones) || bones.length > 32 || !bones.length) throw Error("Invalid athlete mesh");
  for (const [name, size] of [["positions", 3], ["skinIndices", 4], ["skinWeights", 4], ["regions", 1]]) {
    if (!Array.isArray(data[name]) || data[name].length !== n * size || !data[name].every(Number.isFinite)) throw Error(`Invalid athlete ${name}`);
  }
  if (!Array.isArray(data.indices) || data.indices.length > 100000 || data.indices.length % 3 || !data.indices.every(i => Number.isInteger(i) && i >= 0 && i < n)) throw Error("Invalid athlete faces");
  if (data.positions.some(value => Math.abs(value) > 3) || bones.filter(bone => bone.parent === -1).length !== 1) throw Error("Invalid athlete scale/root");
  if (!data.skinIndices.every(i => Number.isInteger(i) && i >= 0 && i < bones.length)) throw Error("Invalid athlete bone reference");
  if (!data.skinWeights.every(w => w >= 0 && w <= 1) || !data.regions.every(r => Number.isInteger(r) && r >= 0 && r <= 7)) throw Error("Invalid athlete weights/regions");
  for (let i = 0; i < n; i++) if (Math.abs(data.skinWeights.slice(i * 4, i * 4 + 4).reduce((a, b) => a + b, 0) - 1) > 0.001) throw Error("Unnormalised athlete weights");
  const names = new Set();
  bones.forEach((bone, index) => {
    if (typeof bone.name !== "string" || names.has(bone.name) || !Number.isInteger(bone.parent) || bone.parent < -1 || bone.parent >= bones.length || bone.parent === index || !Array.isArray(bone.head) || bone.head.length !== 3 || !bone.head.every(Number.isFinite)) throw Error("Invalid athlete skeleton");
    names.add(bone.name);
    const visited = new Set([index]); let parent = bone.parent;
    while (parent !== -1) { if (visited.has(parent) || !bones[parent]) throw Error("Cyclic athlete skeleton"); visited.add(parent); parent = bones[parent].parent; }
  });
  if (!["root", "head", "spine03", "upperleg01.L", "upperleg01.R", "lowerleg01.L", "lowerleg01.R", "foot.L", "foot.R", "upperarm01.L", "upperarm01.R", "lowerarm01.L", "lowerarm01.R"].every(name => names.has(name))) throw Error("Missing athlete joints");
  if (!Array.isArray(data.eyes) || data.eyes.length !== 2 || !data.eyes.every(p => p.length === 3 && p.every(Number.isFinite))) throw Error("Invalid athlete eyes");
  return data;
}

export async function loadAthlete() {
  const response = await fetch(new URL("./assets/athlete/athlete.json", import.meta.url));
  if (!response.ok) throw Error("Athlete asset unavailable");
  return validateAthlete(await response.json());
}
const skin = [0xd5a07b, 0x8c5b3f, 0x66432f, 0xb97d56, 0xe4bb97];
const hash = id => [...id].reduce((n, c) => (Math.imul(n, 31) + c.charCodeAt(0)) >>> 0, 0);

export function athleteGeometry(data) {
  const geometry = new T.BufferGeometry();
  geometry.setAttribute("position", new T.Float32BufferAttribute(data.positions, 3));
  geometry.setAttribute("skinIndex", new T.Uint16BufferAttribute(data.skinIndices, 4));
  geometry.setAttribute("skinWeight", new T.Float32BufferAttribute(data.skinWeights, 4));
  geometry.setAttribute("kitRegion", new T.Float32BufferAttribute(data.regions, 1));
  const shades = data.regions.flatMap((_region, index) => { const shade = 0.98 + (index * 19 % 7) * 0.004; return [shade, shade, shade]; });
  geometry.setAttribute("color", new T.Float32BufferAttribute(shades, 3));
  geometry.setIndex(data.indices); geometry.computeVertexNormals(); geometry.computeBoundingSphere();
  return geometry;
}

export function createAthlete(data, baseGeometry, player, teams, document) {
  const root = new T.Group(), bones = data.bones.map(b => { const bone = new T.Bone(); bone.name = b.name; return bone; });
  data.bones.forEach((definition, i) => {
    const parent = definition.parent;
    bones[i].position.set(...definition.head);
    if (parent >= 0) { bones[i].position.sub(new T.Vector3(...data.bones[parent].head)); bones[parent].add(bones[i]); }
  });
  const keeper = player.role === "GK", seed = hash(player.id);
  const shirt = keeper ? (player.team === "home" ? 0x47a978 : 0xe6b449) : teams[player.team].colour;
  const palette = [skin[seed % skin.length], shirt, keeper ? 0x284637 : player.team === "home" ? 0x172a43 : 0xe6e2d5,
    shirt, 0x1a2028, seed % 3 ? 0x241c17 : 0x4a3324, 0xe4ddd2, 0x171b18];
  const bodyMaterial = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.84, metalness: 0 });
  const kitPalette = palette.map(value => new T.Color(value));
  if (!keeper && player.team === "home") kitPalette[1].multiplyScalar(0.65);
  bodyMaterial.onBeforeCompile = shader => {
    shader.uniforms.kitPalette = { value: kitPalette };
    shader.vertexShader = "attribute float kitRegion; uniform vec3 kitPalette[8];\n" + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <color_vertex>", "#include <color_vertex>\nvColor.rgb *= kitPalette[int(kitRegion)];");
  };
  // One geometry owner for the entire squad: disposing a substitute cannot
  // delete GPU attribute buffers that the other 21 players still reference.
  const mesh = new T.SkinnedMesh(baseGeometry, bodyMaterial); mesh.castShadow = true; mesh.frustumCulled = false;
  for (let i = 0; i < bones.length; i++) if (data.bones[i].parent === -1) mesh.add(bones[i]);
  root.add(mesh); root.updateMatrixWorld(true); const skeleton = new T.Skeleton(bones); mesh.bind(skeleton);
  const joints = Object.fromEntries(bones.map(b => [b.name, b]));
  let numberTexture = null, numberMaterial = null, numberGeometry = null;
  if (document) {
    const canvas = document.createElement("canvas"); canvas.width = 128; canvas.height = 160;
    const c = canvas.getContext("2d"); c.fillStyle = player.team === "home" || keeper ? "#f8f3e9" : "#263443";
    c.textAlign = "center"; c.textBaseline = "middle"; c.font = "bold 112px sans-serif";
    c.fillText(Number.isInteger(player.n) && player.n > 0 && player.n < 100 ? String(player.n) : "", 64, 80);
    numberTexture = new T.CanvasTexture(canvas); numberTexture.colorSpace = T.SRGBColorSpace;
    numberMaterial = new T.MeshStandardMaterial({ map: numberTexture, transparent: true, roughness: 0.9, depthWrite: false });
    numberGeometry = new T.PlaneGeometry(0.18, 0.23);
    const number = new T.Mesh(numberGeometry, numberMaterial), spine = data.bones.find(b => b.name === "spine03").head;
    number.position.set(-spine[0], 1.32 - spine[1], -0.092 - spine[2]); number.rotation.y = Math.PI; joints.spine03.add(number);
  }
  const legRest = Object.fromEntries(["L", "R"].map(side => {
    const head = name => data.bones.find(b => b.name === `${name}.${side}`).head;
    const hip = head("upperleg01"), knee = head("lowerleg01"), foot = head("foot");
    return [side, { upper: knee.map((v, i) => v - hip[i]), lower: foot.map((v, i) => v - knee[i]), y: foot[1] - hip[1], z: foot[2] - hip[2] }];
  }));
  return { root, mesh, joints, skeleton, legRest, kitPalette, phase: (seed % 997) / 997,
    dispose() { bodyMaterial.dispose(); skeleton.dispose(); numberTexture?.dispose(); numberMaterial?.dispose(); numberGeometry?.dispose(); } };
}

export class DetailedFootballers {
  constructor(scene, data, document) { this.scene = scene; this.data = data; this.document = document; this.base = athleteGeometry(data); this.actors = new Map(); }
  update(frame, poses, teams) {
    const signature = JSON.stringify(teams);
    if (signature !== this.signature) { this.hide(); this.signature = signature; }
    const active = new Set(frame.players.map(p => p.id));
    for (const [id, actor] of this.actors) if (!active.has(id)) { actor.root.removeFromParent(); actor.dispose(); this.actors.delete(id); }
    for (const p of frame.players) {
      let actor = this.actors.get(p.id);
      if (!actor || actor.role !== p.role || actor.team !== p.team || actor.n !== p.n) {
        if (actor) { actor.root.removeFromParent(); actor.dispose(); }
        actor = Object.assign(createAthlete(this.data, this.base, p, teams, this.document), { role: p.role, team: p.team, n: p.n });
        this.actors.set(p.id, actor); this.scene.add(actor.root);
      }
      const pose = poses.get(p.id), gait = footballGait(pose.speed, pose.distance / 2.2 + actor.phase, p.role === "GK");
      const ball = frame.ball ?? [52.5, 34], look = Math.atan2(ball[0] - p.x, p.y - ball[1]);
      const holder = frame.possession?.holder_id === p.id;
      const facing = pose.speed > 0.1 || holder ? pose.heading : look;
      actor.root.position.set(p.x - 52.5, gait.pelvis, 34 - p.y); actor.root.rotation.y = facing;
      for (const [side, sign] of [["L", 1], ["R", -1]]) {
        const foot = side === "L" ? gait.left : gait.right, rest = actor.legRest[side];
        const leg = legAngles(rest.upper, rest.lower, rest.y - gait.pelvis + foot.lift, rest.z + foot.z);
        actor.joints[`upperleg01.${side}`].rotation.set(leg.hip, 0, 0);
        actor.joints[`lowerleg01.${side}`].rotation.x = leg.knee;
        actor.joints[`foot.${side}`].rotation.x = leg.ankle;
        actor.joints[`upperarm01.${side}`].rotation.set(gait.armSwing * sign, 0, -sign * gait.armSpread);
        actor.joints[`lowerarm01.${side}`].rotation.x = gait.elbow;
      }
      actor.joints.spine03.rotation.x = gait.lean;
      actor.joints.spine03.rotation.y = gait.twist;
      const lookDelta = Math.atan2(Math.sin(look - facing), Math.cos(look - facing));
      actor.joints.head.rotation.y = holder ? 0 : Math.max(-0.5, Math.min(0.5, lookDelta));
      actor.root.updateMatrixWorld(true);
    }
  }
  hide() { for (const actor of this.actors.values()) { actor.root.removeFromParent(); actor.dispose(); } this.actors.clear(); }
  dispose() { this.hide(); this.base.dispose(); }
}
