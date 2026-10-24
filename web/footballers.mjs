import * as T from "./vendor/three/three.module.js";

// One bounded instanced batch per shape. Articulation is independent of draw calls.
const shapes = {
  rounded: new T.CapsuleGeometry(0.5, 1, 3, 8),
  sphere: new T.SphereGeometry(1, 10, 8),
  box: new T.BoxGeometry(1, 1, 1),
};
const skin = [0xe2b38e, 0x9f6948, 0x754832, 0xc68d64, 0x583728];
const hashId = id => [...id].reduce((n, c) => (Math.imul(n, 31) + c.charCodeAt(0)) >>> 0, 0);
function part(parent, kind, size, position, color, parts) {
  const object = new T.Object3D(); object.position.set(...position); object.scale.set(...size);
  parent.add(object); parts.push({ object, kind, color }); return object;
}
function limb(root, x, y, upperLength, lowerLength, color, lowerColor, parts, arm) {
  const joint = new T.Group(); joint.position.set(x, y, 0); root.add(joint);
  part(joint, "rounded", [arm ? 0.09 : 0.13, upperLength / 2, arm ? 0.09 : 0.13], [0, -upperLength / 2, 0], color, parts);
  const knee = new T.Group(); knee.position.y = -upperLength; joint.add(knee);
  part(knee, "rounded", [arm ? 0.075 : 0.1, lowerLength / 2, arm ? 0.075 : 0.1], [0, -lowerLength / 2, 0], lowerColor, parts);
  part(knee, arm ? "sphere" : "box", arm ? [0.075, 0.09, 0.065] : [0.14, 0.12, 0.3],
    [0, -lowerLength, arm ? 0 : 0.07], arm ? lowerColor : 0x17202b, parts);
  return { joint, knee };
}

export function buildFootballer(player, teams) {
  const root = new T.Group(), body = new T.Group(); root.add(body);
  const parts = [], keeper = player.role === "GK";
  const shirt = keeper ? (player.team === "home" ? 0xe9ae38 : 0x9cd964) : teams[player.team].colour;
  const shorts = keeper ? 0x253e37 : player.team === "home" ? 0x182939 : 0xddd9c9;
  const flesh = skin[hashId(player.id) % skin.length];
  part(body, "rounded", [0.36, 0.29, 0.23], [0, 1.27, 0], shirt, parts);
  part(body, "box", [0.36, 0.19, 0.23], [0, 0.92, 0], shorts, parts);
  part(body, "rounded", [0.08, 0.06, 0.08], [0, 1.59, 0], flesh, parts);
  part(body, "sphere", [0.135, 0.165, 0.135], [0, 1.76, 0], flesh, parts);
  part(body, "sphere", [0.14, 0.075, 0.14], [0, 1.88, -0.015], 0x251c19, parts);
  // Kit collar and centre panel are geometry, never floating player labels.
  part(body, "box", [0.14, 0.045, 0.03], [0, 1.51, 0.13], 0xf0ece1, parts);
  part(body, "box", [0.06, 0.35, 0.015], [0, 1.26, 0.125], keeper ? 0x27443b : 0x9abbd2, parts);
  const legs = [-1, 1].map(side => limb(body, side * 0.115, 0.85, 0.36, 0.36, shorts, shirt, parts, false));
  const arms = [-1, 1].map(side => {
    const arm = limb(body, side * 0.25, 1.48, 0.28, 0.25, shirt, flesh, parts, true);
    arm.joint.rotation.z = side * 0.12; return arm;
  });
  return { root, body, parts, legs, arms };
}

export class Footballers {
  constructor(scene) {
    this.scene = scene; this.actors = new Map(); this.batches = new Map();
    const material = new T.MeshStandardMaterial({ color: 0xffffff, roughness: 0.82 });
    for (const [kind, geometry] of Object.entries(shapes)) {
      const mesh = new T.InstancedMesh(geometry, material, 22 * 30);
      mesh.instanceMatrix.setUsage(T.DynamicDrawUsage); mesh.count = 0;
      mesh.castShadow = true; mesh.frustumCulled = false; scene.add(mesh); this.batches.set(kind, mesh);
    }
    this.color = new T.Color(); this.signature = null;
  }
  update(frame, poses, teams) {
    const signature = JSON.stringify(teams);
    if (signature !== this.signature) { this.actors.clear(); this.signature = signature; }
    const active = new Set(frame.players.map(p => p.id));
    for (const id of this.actors.keys()) if (!active.has(id)) this.actors.delete(id);
    const counts = { rounded: 0, sphere: 0, box: 0 };
    for (const p of frame.players) {
      let actor = this.actors.get(p.id);
      if (!actor || actor.role !== p.role || actor.team !== p.team) {
        actor = { ...buildFootballer(p, teams), role: p.role, team: p.team }; this.actors.set(p.id, actor);
      }
      const pose = poses.get(p.id);
      actor.root.position.set(p.x - 52.5, 0, 34 - p.y); actor.root.rotation.y = pose.heading;
      actor.body.position.y = pose.bob;
      for (let side = 0; side < 2; side++) {
        const sign = side ? 1 : -1;
        actor.legs[side].joint.rotation.x = pose.stride * sign;
        actor.legs[side].knee.rotation.x = Math.max(0, -pose.stride * sign) * 0.9;
        actor.arms[side].joint.rotation.x = -pose.stride * sign * 0.75;
        actor.arms[side].knee.rotation.x = -0.2 - Math.abs(pose.stride) * 0.3;
      }
      actor.root.updateMatrixWorld(true);
      for (const part of actor.parts) {
        const mesh = this.batches.get(part.kind), index = counts[part.kind]++;
        mesh.setMatrixAt(index, part.object.matrixWorld); mesh.setColorAt(index, this.color.set(part.color));
      }
    }
    for (const [kind, mesh] of this.batches) {
      mesh.count = counts[kind]; mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
  }
  hide() { for (const mesh of this.batches.values()) mesh.count = 0; this.actors.clear(); }
}
