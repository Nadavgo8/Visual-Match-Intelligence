import * as T from "./vendor/three/three.module.js";

// Pixel bounds are measured from the original generated alpha, not a promise
// that the image model obeyed a mathematically exact layout.
export function atlasRegions(data) {
  if (!Number.isInteger(data?.width) || !Number.isInteger(data?.height)
    || data.width < 1 || data.height < 1 || data.width > 4096 || data.height > 4096
    || !Array.isArray(data.sprites) || data.sprites.length !== 12) throw Error("Invalid crowd atlas");
  return data.sprites.map((sprite, index) => {
    const r = sprite.rect;
    if (!Array.isArray(r) || r.length !== 4 || !r.every(Number.isInteger)
      || r[0] < 0 || r[1] < 0 || r[2] < 1 || r[3] < 1
      || r[0] + r[2] > data.width || r[1] + r[3] > data.height
      || !Number.isFinite(sprite.height) || sprite.height < 1 || sprite.height > 2.5
      || sprite.pose !== ["seated", "standing", "raised"][Math.floor(index / 4)]) throw Error("Invalid crowd sprite");
    return { uv: new T.Vector4(r[0] / data.width, 1 - (r[1] + r[3]) / data.height,
      r[2] / data.width, r[3] / data.height), size: new T.Vector2(sprite.height * r[2] / r[3], sprite.height) };
  });
}

export async function loadAtlasMetadata() {
  const response = await fetch(new URL("./assets/crowd/atlas.json", import.meta.url));
  if (!response.ok) throw Error("Crowd atlas metadata unavailable");
  const data = await response.json(); atlasRegions(data); return data;
}

export function createAtlasCrowd(seats, uniforms, atlas) {
  const regions = atlasRegions(atlas.metadata);
  const geometry = new T.PlaneGeometry(1, 1); geometry.translate(0, 0.5, 0);
  const seeds = new Float32Array(seats.map(seat => seat.seed));
  geometry.setAttribute("crowdSeed", new T.InstancedBufferAttribute(seeds, 1));
  const material = new T.MeshStandardMaterial({ map: atlas.texture, alphaTest: 0.65,
    side: T.DoubleSide, roughness: 1, alphaToCoverage: true });
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms, { crowdRects: {value: regions.map(r => r.uv)},
      crowdSizes: {value: regions.map(r => r.size)} });
    shader.vertexShader = `attribute float crowdSeed;
      uniform float crowdTime; uniform float crowdStanding; uniform float crowdArms; uniform float crowdSway;
      uniform vec4 crowdRects[12]; uniform vec2 crowdSizes[12];\n` + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <uv_vertex>", `#include <uv_vertex>
      float standing = step(crowdSeed, crowdStanding);
      int pose = standing > 0.5 ? (crowdArms > 0.01 ? 2 : 1) : 0;
      int sprite = pose * 4 + int(floor(crowdSeed * 4.0));
      vec4 region = crowdRects[sprite];
      vMapUv = region.xy + vMapUv * region.zw;`);
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
      transformed.xy *= crowdSizes[sprite];
      transformed.x += sin(crowdTime * 2.1 + crowdSeed * 71.0) * crowdSway * transformed.y;`);
  };
  const mesh = new T.InstancedMesh(geometry, material, seats.length), dummy = new T.Object3D(), color = new T.Color();
  for (const [index, seat] of seats.entries()) {
    dummy.position.set(seat.x, seat.y, seat.z); dummy.rotation.y = Math.PI + (seat.seed - 0.5) * 0.3;
    dummy.scale.set(0.94 + seat.shape * 0.14, 0.9 + seat.seed * 0.2, 1); dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix); mesh.setColorAt(index, color.setScalar(0.82 + seat.shape * 0.18));
  }
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor.needsUpdate = true; mesh.frustumCulled = false;
  mesh.name = "Delivered-amplitude crowd"; return mesh;
}
