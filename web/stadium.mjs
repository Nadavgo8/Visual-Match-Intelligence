import * as T from "./vendor/three/three.module.js";
import { createCrowd, createCrowdUniforms, crowdLayout, standAisles } from "./crowd.mjs?v=3.9";

const boxGeometry = new T.BoxGeometry(1, 1, 1);
const materials = new Map();
export function material(color, roughness = 0.8) {
  const key = `${color}/${roughness}`;
  if (!materials.has(key)) materials.set(key, new T.MeshStandardMaterial({ color, roughness }));
  return materials.get(key);
}
export function box(parent, size, position, mat, shadow = false) {
  const mesh = new T.Mesh(boxGeometry, mat);
  mesh.scale.set(...size); mesh.position.set(...position);
  mesh.castShadow = shadow; mesh.receiveShadow = shadow; parent.add(mesh); return mesh;
}
function paintPitch(document) {
  const canvas = document.createElement("canvas"); canvas.width = 2048; canvas.height = 1360;
  const c = canvas.getContext("2d"), sx = canvas.width / 114, sy = canvas.height / 76;
  c.save(); c.translate(4.5 * sx, 4 * sy); c.scale(sx, sy);
  for (let i = 0; i < 14; i++) {
    c.fillStyle = i % 2 ? "#bfd0a00a" : "#07160b10"; c.fillRect(i * 7.5, 0, 7.5, 68);
  }
  // Fixed, subtle wear breaks up perfectly flat synthetic colour. It never
  // changes with amplitude or time and cannot masquerade as a game event.
  for (let i = 0; i < 12000; i++) {
    const x = ((i * 7919) % 12007) / 12007 * 105, y = ((i * 3571) % 12011) / 12011 * 68;
    c.fillStyle = i % 3 ? "#11291804" : "#ab996606"; c.fillRect(x, y, 0.3, 0.14);
  }
  c.strokeStyle = "#e7eee1"; c.fillStyle = "#e7eee1"; c.lineWidth = 0.12;
  c.strokeRect(0, 0, 105, 68); c.beginPath(); c.moveTo(52.5, 0); c.lineTo(52.5, 68); c.stroke();
  const circle = (x, y, r, a = 0, b = Math.PI * 2) => { c.beginPath(); c.arc(x, y, r, a, b); c.stroke(); };
  const dot = (x, y) => { c.beginPath(); c.arc(x, y, 0.16, 0, Math.PI * 2); c.fill(); };
  circle(52.5, 34, 9.15); dot(52.5, 34);
  for (const home of [true, false]) {
    c.strokeRect(home ? 0 : 88.5, 13.84, 16.5, 40.32);
    c.strokeRect(home ? 0 : 99.5, 24.84, 5.5, 18.32);
    const x = home ? 11 : 94, arc = Math.acos(5.5 / 9.15);
    dot(x, 34); circle(x, 34, 9.15, home ? -arc : Math.PI - arc, home ? arc : Math.PI + arc);
  }
  for (const [x, y, a] of [[0, 0, 0], [105, 0, Math.PI / 2], [105, 68, Math.PI], [0, 68, -Math.PI / 2]]) circle(x, y, 1, a, a + Math.PI / 2);
  c.restore();
  const texture = new T.CanvasTexture(canvas); texture.colorSpace = T.SRGBColorSpace;
  texture.anisotropy = 4; return texture;
}

function structuralSurface(document) {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 128;
  const c = canvas.getContext("2d");
  c.fillStyle = "#777e80"; c.fillRect(0, 0, 128, 128);
  for (let i = 0; i < 4096; i++) {
    const shade = 90 + i * 37 % 65;
    c.fillStyle = `rgba(${shade},${shade},${shade},0.18)`;
    c.fillRect(i * 71 % 128, Math.floor(i / 128) * 17 % 128, 1, 2);
  }
  c.fillStyle = "#434d4d"; c.fillRect(0, 0, 1, 128); c.fillRect(0, 0, 128, 1);
  const texture = new T.CanvasTexture(canvas); texture.colorSpace = T.SRGBColorSpace; texture.anisotropy = 4;
  return new T.MeshStandardMaterial({ map: texture, roughness: 1 });
}

function net(parent, x, direction) {
  const points = [], depth = 2.2, half = 3.66, height = 2.44;
  const add = (a, b) => points.push(...a, ...b);
  // Closed roof, back and sides; correctly sized 7.32 x 2.44 metre goal.
  for (let z = -half; z <= half; z += 0.22) {
    add([x + direction * depth, 0, z], [x + direction * depth, height, z]);
    add([x, height, z], [x + direction * depth, height, z]);
  }
  for (let y = 0; y <= height; y += 0.22) {
    add([x + direction * depth, y, -half], [x + direction * depth, y, half]);
    for (const z of [-half, half]) add([x, y, z], [x + direction * depth, y, z]);
  }
  const geometry = new T.BufferGeometry(); geometry.setAttribute("position", new T.Float32BufferAttribute(points, 3));
  parent.add(new T.LineSegments(geometry, new T.LineBasicMaterial({ color: 0xdde9e9, transparent: true, opacity: 0.36 })));
  const white = material(0xeaf1ec, 0.35);
  for (const z of [-half, half]) box(parent, [0.12, height, 0.12], [x, height / 2, z], white, true);
  box(parent, [0.12, 0.12, half * 2], [x, height, 0], white, true);
}

function beam(parent, a, b, width, mat) {
  const start = new T.Vector3(...a), end = new T.Vector3(...b), direction = end.clone().sub(start);
  const mesh = box(parent, [width, direction.length(), width], start.clone().add(end).multiplyScalar(0.5).toArray(), mat);
  mesh.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), direction.normalize());
  return mesh;
}

function stadiumSeats(group, length, seed) {
  const seats = crowdLayout(length, 24, seed);
  const mesh = new T.InstancedMesh(boxGeometry, material(0x344b5c, 0.7), seats.length * 2);
  mesh.name = "Individual stadium seats";
  const dummy = new T.Object3D(), color = new T.Color();
  seats.forEach((seat, i) => {
    for (const back of [false, true]) {
      dummy.position.set(seat.x, seat.y + (back ? 0.72 : 0.43), seat.z + (back ? 0.24 : 0.05));
      dummy.scale.set(0.44, back ? 0.42 : 0.07, back ? 0.065 : 0.42); dummy.updateMatrix();
      const index = i * 2 + Number(back); mesh.setMatrixAt(index, dummy.matrix);
      mesh.setColorAt(index, color.setScalar(0.7 + seat.shape * 0.3));
    }
  });
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor.needsUpdate = true; mesh.computeBoundingSphere(); group.add(mesh);
}

function stand(parent, length, x, z, rotation, uniforms, seed, atlas, concrete) {
  const group = new T.Group(); group.position.set(x, 0, z); group.rotation.y = rotation; parent.add(group);
  const roof = material(0x202c34), rail = material(0x6f7e84, 0.55);
  for (let row = 0; row < 24; row++) box(group, [length, 0.45, 0.76], [0, 0.3 + row * 0.52, row * 0.76], concrete);
  box(group, [length, 2.4, 0.3], [0, 13.5, 18], concrete);
  for (const side of [-1, 1]) for (let row = 0; row < 24; row++) {
    const height = 0.8 + row * 0.52;
    box(group, [0.2, height, 0.76], [side * length / 2, height / 2, row * 0.76], concrete);
  }
  // A cantilever canopy, rear wall and diagonal steelwork give the crowd a
  // physical home. The broadcast side remains an open cutaway.
  box(group, [length + 2, 0.28, 22], [0, 16.2, 7.4], roof);
  for (let x = -length / 2; x <= length / 2; x += 13) {
    box(group, [0.18, 16, 0.18], [x, 8, 18], rail);
    beam(group, [x, 15.95, -3], [x, 14.9, 18], 0.13, rail);
    for (let z = -3; z < 18; z += 3) {
      beam(group, [x, 15.95, z], [x, 15.1, z + 3], 0.065, rail);
      beam(group, [x, 15.1, z], [x, 15.95, z + 3], 0.065, rail);
    }
  }
  for (let z = -3; z < 18; z += 3) box(group, [length, 0.07, 0.07], [0, 16, z], rail);
  stadiumSeats(group, length, seed);
  group.add(createCrowd(length, 24, uniforms, seed, atlas));
  const aisleMaterial = material(0x555d5d), yellow = material(0xb6a878), dark = material(0x131d24);
  for (const aisle of standAisles(length)) {
    for (let row = 0; row < 24; row++) {
      box(group, [1.36, 0.05, 0.7], [aisle, 0.55 + row * 0.52, row * 0.76], aisleMaterial);
      box(group, [1.36, 0.035, 0.06], [aisle, 0.59 + row * 0.52, row * 0.76 - 0.32], yellow);
      if (row % 3 === 0) for (const side of [-1, 1]) {
        box(group, [0.035, 0.85, 0.035], [aisle + side * 0.7, 0.95 + row * 0.52, row * 0.76], rail);
        beam(group, [aisle + side * 0.7, 1.38 + row * 0.52, row * 0.76 - 0.4],
          [aisle + side * 0.7, 2.42 + row * 0.52, row * 0.76 + 1.12], 0.04, rail);
      }
    }
    // A real entry portal breaks up the repeated seating blocks.
    box(group, [2, 2.4, 0.18], [aisle, 1.4, -0.1], dark);
    box(group, [2.3, 0.2, 1.2], [aisle, 2.7, -0.2], concrete);
    // The recessed concourse repeats entrances, not identical black towers.
    box(group, [2.1, 2.4, 0.2], [aisle, 8.1, 9.3], dark);
    box(group, [2.4, 0.18, 0.9], [aisle, 9.4, 8.9], concrete);
  }
  box(group, [length, 0.08, 0.76], [0, 6.77, 9.12], aisleMaterial);
  box(group, [length, 0.08, 0.08], [0, 7.5, 8.7], rail);
  for (let post = -length / 2; post < length / 2; post += 4) box(group, [0.06, 0.8, 0.06], [post, 7.1, 8.7], rail);
  // Plain fascia, no real club, sponsor, league or broadcast marks.
  box(group, [length, 0.9, 0.25], [0, 0.5, -0.65], roof);
  for (let x = -length / 2 + 0.6; x < length / 2; x += 4) box(group, [0.035, 0.82, 0.03], [x, 0.5, -0.8], rail);
  return group;
}

function batchStaticBoxes(group) {
  group.updateMatrixWorld(true);
  const batches = new Map();
  group.traverse(object => {
    if (!object.isMesh || object.isInstancedMesh || object.geometry !== boxGeometry) return;
    const key = `${object.material.id}/${object.castShadow}/${object.receiveShadow}`;
    if (!batches.has(key)) batches.set(key, []);
    batches.get(key).push(object);
  });
  for (const objects of batches.values()) {
    const first = objects[0], batch = new T.InstancedMesh(boxGeometry, first.material, objects.length);
    batch.castShadow = first.castShadow; batch.receiveShadow = first.receiveShadow;
    objects.forEach((object, index) => { batch.setMatrixAt(index, object.matrixWorld); object.removeFromParent(); });
    batch.instanceMatrix.needsUpdate = true; batch.computeBoundingSphere(); group.add(batch);
  }
}

export function buildStadium(document, turfMaps = {}, crowdAtlas = null) {
  const group = new T.Group(); group.name = "Original procedural stadium";
  const concrete = structuralSurface(document);
  const uniforms = createCrowdUniforms(); group.userData.crowdUniforms = uniforms;
  const pitchTexture = paintPitch(document);
  const turf = new T.Mesh(new T.PlaneGeometry(114, 76), new T.MeshStandardMaterial({ color: turfMaps.color ? 0xb5d9bd : 0x476343,
    map: turfMaps.color ?? null, normalMap: turfMaps.normal ?? null, normalScale: new T.Vector2(0.22, 0.22), roughness: 1 }));
  turf.rotation.x = -Math.PI / 2; turf.receiveShadow = true; group.add(turf);
  const markings = new T.Mesh(new T.PlaneGeometry(114, 76), new T.MeshBasicMaterial({ map: pitchTexture, transparent: true, depthWrite: false }));
  markings.rotation.x = -Math.PI / 2; markings.position.y = 0.012; group.add(markings);
  box(group, [178, 0.3, 134], [0, -0.2, 0], material(0x394348));
  // Drainage and a neutral dark advertising rail frame the playing surface.
  for (const z of [-38.6, 38.6]) {
    box(group, [116, 0.012, 0.24], [0, 0.015, z], material(0x202c34));
    box(group, [116, 0.85, 0.16], [0, 0.5, z + Math.sign(z) * 1.4], material(0x202c34));
    for (let x = -57; x <= 57; x += 3.8) box(group, [0.035, 0.8, 0.18], [x, 0.5, z + Math.sign(z) * 1.4], material(0x6f7e84, 0.55));
  }
  net(group, -52.5, -1); net(group, 52.5, 1);
  // Broadcast cutaway: the camera-side roof would physically occlude the pitch.
  // Keep the three main stands and occupied corners; leave the near side open.
  stand(group, 132, 0, -43, Math.PI, uniforms, 1, crowdAtlas, concrete);
  stand(group, 78, -62, 0, -Math.PI / 2, uniforms, 2, crowdAtlas, concrete); stand(group, 78, 62, 0, Math.PI / 2, uniforms, 3, crowdAtlas, concrete);
  for (const x of [-62, 62]) {
    // Angled, occupied corner stands replace the opaque featureless cubes.
    stand(group, 14, x, -41, Math.sign(x) * Math.PI * 0.75, uniforms, x < 0 ? 4 : 5, crowdAtlas, concrete);
  }
  for (const x of [-52.5, 52.5]) for (const z of [-34, 34]) {
    box(group, [0.045, 1.6, 0.045], [x, 0.8, z], material(0xecede1));
    box(group, [0.45, 0.3, 0.025], [x + 0.22, 1.4, z], material(0xebba5a));
  }
  for (const x of [-47, 47]) for (const z of [-49, 49]) {
    box(group, [0.25, 23, 0.25], [x, 11.5, z], material(0x8d9aa1));
    box(group, [5.4, 1.5, 0.35], [x, 23, z], material(0x202c34));
    for (let lamp = 0; lamp < 8; lamp++) {
      box(group, [0.48, 0.48, 0.12], [x - 2.1 + (lamp % 4) * 1.4, 22.65 + Math.floor(lamp / 4) * 0.7, z + (z < 0 ? 0.24 : -0.24)], material(0xdce5df, 0.35));
    }
  }
  batchStaticBoxes(group); return group;
}
