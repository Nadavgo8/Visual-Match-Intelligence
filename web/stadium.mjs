import * as T from "./vendor/three/three.module.js";

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
  c.fillStyle = "#285d32"; c.fillRect(0, 0, canvas.width, canvas.height);
  let seed = 47;
  // Fixed-seed grain: original texture, stable across reloads, no image download.
  for (let i = 0; i < 110000; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const x = seed % canvas.width; seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    c.fillStyle = i % 2 ? "#ffffff0b" : "#0000000d";
    c.fillRect(x, seed % canvas.height, 1, 2);
  }
  c.save(); c.translate(4.5 * sx, 4 * sy); c.scale(sx, sy);
  for (let i = 0; i < 14; i++) {
    c.fillStyle = i % 2 ? "#85a85516" : "#061c1210"; c.fillRect(i * 7.5, 0, 7.5, 68);
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

function stand(parent, length, x, z, rotation) {
  const group = new T.Group(); group.position.set(x, 0, z); group.rotation.y = rotation; parent.add(group);
  const concrete = material(0x27323d), roof = material(0x17232e), rail = material(0x7b8b96, 0.4);
  for (let row = 0; row < 18; row++) box(group, [length, 0.6, 0.9], [0, 0.65 + row * 0.62, row * 0.86], concrete);
  box(group, [length + 2, 0.4, 21], [0, 16, 6], roof);
  for (let x = -length / 2; x <= length / 2; x += 13) {
    box(group, [0.2, 16, 0.2], [x, 8, 14.6], rail);
    box(group, [0.16, 0.16, 20], [x, 15.6, 6], rail);
  }
  const count = Math.floor(length / 0.7) * 18;
  const crowd = new T.InstancedMesh(new T.IcosahedronGeometry(0.25, 0), material(0xffffff), count);
  const dummy = new T.Object3D(), color = new T.Color(); let i = 0;
  const palette = [0x172c40, 0x2c5b79, 0x879ba7, 0x5a6875, 0xd1c3ad, 0x2c3f51];
  for (let row = 0; row < 18; row++) for (let col = 0; col < Math.floor(length / 0.7); col++) {
    dummy.position.set(-length / 2 + col * 0.7 + 0.35, 1.25 + row * 0.62, row * 0.86);
    dummy.scale.set(0.85, 1.65, 0.85); dummy.updateMatrix(); crowd.setMatrixAt(i, dummy.matrix);
    crowd.setColorAt(i, color.setHex(palette[(col * 7 + row * 13) % palette.length])); i++;
  }
  crowd.instanceMatrix.needsUpdate = true; crowd.instanceColor.needsUpdate = true;
  crowd.computeBoundingSphere(); group.add(crowd);
  // Continuous luminous fascia, no real club, sponsor, league or broadcast marks.
  box(group, [length, 0.5, 0.2], [0, 0.75, -0.65], new T.MeshStandardMaterial({ color: 0x12394a, emissive: 0x207f95, emissiveIntensity: 0.4 }));
  return group;
}

function batchStaticBoxes(group) {
  group.updateMatrixWorld(true);
  const batches = new Map();
  group.traverse(object => {
    if (!object.isMesh || object.geometry !== boxGeometry) return;
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

export function buildStadium(document) {
  const group = new T.Group(); group.name = "Original procedural stadium";
  const pitchTexture = paintPitch(document);
  const turf = new T.Mesh(new T.PlaneGeometry(114, 76), new T.MeshStandardMaterial({ map: pitchTexture, roughness: 0.98 }));
  turf.rotation.x = -Math.PI / 2; turf.receiveShadow = true; group.add(turf);
  box(group, [158, 0.3, 118], [0, -0.2, 0], material(0x18282b));
  net(group, -52.5, -1); net(group, 52.5, 1);
  // Broadcast cutaway: the camera-side roof would physically occlude the pitch.
  // Keep the three visible stands; the near touchline stays open to the camera.
  stand(group, 132, 0, -43, Math.PI);
  box(group, [116, 0.7, 0.25], [0, 0.35, 39], material(0x173d4b));
  stand(group, 78, -62, 0, -Math.PI / 2); stand(group, 78, 62, 0, Math.PI / 2);
  for (const x of [-52.5, 52.5]) for (const z of [-34, 34]) {
    box(group, [0.045, 1.6, 0.045], [x, 0.8, z], material(0xecede1));
    box(group, [0.45, 0.3, 0.025], [x + 0.22, 1.4, z], material(0xebba5a));
  }
  for (const x of [-47, 47]) for (const z of [-49, 49]) {
    box(group, [0.25, 23, 0.25], [x, 11.5, z], material(0x8d9aa1));
    box(group, [5, 1.3, 0.3], [x, 23, z], new T.MeshStandardMaterial({ color: 0xe5f3ff, emissive: 0xd7eaff, emissiveIntensity: 2 }));
  }
  batchStaticBoxes(group); return group;
}
