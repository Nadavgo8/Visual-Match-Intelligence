import * as T from "./vendor/three/three.module.js";

// These are visual encodings of delivered crowd amplitude, not a second metric.
// Attack never makes the crowd louder; missing observations never mean silence.
export function crowdPresentation(atmosphere, reducedMotion = false) {
  const level = atmosphere?.crowd;
  const available = typeof level === "number" && Number.isFinite(level) && level >= 0 && level <= 1;
  const amount = available ? level : 0;
  return { available, level: available ? level : null,
    standing: available ? amount * amount * 0.68 : 0,
    arms: reducedMotion || !available ? 0 : amount * 2.35,
    sway: reducedMotion || !available ? 0 : 0.004 + amount * 0.035 };
}

function personGeometry() {
  const positions = [], normals = [], colors = [], parts = [], tints = [], indices = [];
  const add = (geometry, position, scale, color, part = 0, tint = 0) => {
    geometry.scale(...scale); geometry.translate(...position);
    const base = positions.length / 3, p = geometry.getAttribute("position"), n = geometry.getAttribute("normal"), c = new T.Color(color);
    for (let i = 0; i < p.count; i++) {
      positions.push(p.getX(i), p.getY(i), p.getZ(i)); normals.push(n.getX(i), n.getY(i), n.getZ(i));
      colors.push(c.r, c.g, c.b); parts.push(part); tints.push(tint);
    }
    if (geometry.index) for (const index of geometry.index.array) indices.push(base + index);
    else for (let i = 0; i < p.count; i++) indices.push(base + i);
    geometry.dispose();
  };
  add(new T.SphereGeometry(1, 7, 5), [0, 1.02, 0], [0.09, 0.12, 0.09], 0xc2a38b);
  add(new T.SphereGeometry(1, 7, 4), [0, 1.09, -0.008], [0.092, 0.055, 0.092], 0x33302d);
  add(new T.CylinderGeometry(0.16, 0.12, 0.38, 7), [0, 0.71, 0], [1, 1, 0.65], 0xffffff, 0, 1);
  for (const side of [-1, 1]) {
    add(new T.CylinderGeometry(0.045, 0.04, 0.32, 5), [side * 0.19, 0.7, 0], [1, 1, 1], 0xc2a38b, side);
    add(new T.CylinderGeometry(0.06, 0.05, 0.32, 5), [side * 0.085, 0.32, 0.05], [1, 1, 1], 0x29333d);
  }
  const geometry = new T.BufferGeometry();
  geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3)); geometry.setAttribute("normal", new T.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("color", new T.Float32BufferAttribute(colors, 3)); geometry.setAttribute("crowdPart", new T.Float32BufferAttribute(parts, 1)); geometry.setIndex(indices);
  geometry.setAttribute("crowdTint", new T.Float32BufferAttribute(tints, 1));
  return geometry;
}

export function createCrowdUniforms() {
  return { crowdTime: { value: 0 }, crowdStanding: { value: 0 }, crowdArms: { value: 0 }, crowdSway: { value: 0 } };
}
export function updateCrowd(uniforms, atmosphere, t, reducedMotion) {
  const view = crowdPresentation(atmosphere, reducedMotion);
  uniforms.crowdTime.value = Number.isFinite(t) ? t : 0;
  uniforms.crowdStanding.value = view.standing; uniforms.crowdArms.value = view.arms; uniforms.crowdSway.value = view.sway;
  return view;
}

export function createCrowd(length, rows, uniforms) {
  const columns = Math.floor(length / 0.56), count = columns * rows, geometry = personGeometry();
  const seeds = new Float32Array(count);
  const material = new T.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: 1 });
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = `attribute float crowdPart; attribute float crowdSeed; attribute float crowdTint;
      uniform float crowdTime; uniform float crowdStanding; uniform float crowdArms; uniform float crowdSway;\n` + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <color_vertex>", T.ShaderChunk.color_vertex.replace(
      "vColor.rgb *= instanceColor.rgb;", "vColor.rgb *= mix(vec3(1.0), instanceColor.rgb, crowdTint);"));
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
      float standing = step(crowdSeed, crowdStanding);
      float phase = crowdTime * 2.1 + crowdSeed * 71.0;
      if (abs(crowdPart) > 0.5) {
        float a = crowdPart * standing * crowdArms * (0.9 + 0.1 * sin(phase));
        vec2 pivot = vec2(crowdPart * 0.18, 0.88);
        transformed.xy = mat2(cos(a), sin(a), -sin(a), cos(a)) * (transformed.xy - pivot) + pivot;
      }
      transformed.x += sin(phase) * crowdSway * transformed.y;
      transformed.y += standing * 0.22;`);
  };
  const crowd = new T.InstancedMesh(geometry, material, count), dummy = new T.Object3D(), color = new T.Color();
  const palette = [0x7e8a91, 0x233544, 0x52646b, 0xada69b, 0x353d40, 0x79877f, 0xada9a0, 0x234b65];
  for (let row = 0, index = 0; row < rows; row++) for (let col = 0; col < columns; col++, index++) {
    const seed = ((Math.imul(index + 1, 2654435761) >>> 0) % 10007) / 10007; seeds[index] = seed;
    dummy.position.set(-length / 2 + col * 0.56 + 0.28 + (seed - 0.5) * 0.12, 0.28 + row * 0.52, row * 0.76);
    dummy.rotation.y = (seed - 0.5) * 0.3; dummy.scale.setScalar(0.94 + seed * 0.12); dummy.updateMatrix();
    crowd.setMatrixAt(index, dummy.matrix); crowd.setColorAt(index, color.setHex(palette[Math.floor(seed * palette.length)]));
  }
  geometry.setAttribute("crowdSeed", new T.InstancedBufferAttribute(seeds, 1));
  crowd.instanceMatrix.needsUpdate = true; crowd.instanceColor.needsUpdate = true; crowd.frustumCulled = false;
  crowd.name = "Delivered-amplitude crowd"; return crowd;
}
