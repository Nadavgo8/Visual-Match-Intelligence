import * as T from "./vendor/three/three.module.js";
import { createAtlasCrowd } from "./crowd-atlas.mjs?v=3.22";

const smooth = (a,b,x) => {const u=Math.max(0,Math.min(1,(x-a)/(b-a)));return u*u*(3-2*u);};

// These are visual encodings of delivered crowd amplitude, not a second metric.
// Attack never makes the crowd louder; missing observations never mean silence.
export function crowdPresentation(atmosphere, reducedMotion = false) {
  const level = atmosphere?.crowd;
  const available = typeof level === "number" && Number.isFinite(level) && level >= 0 && level <= 1;
  const amount = available ? level : 0;
  return { available, level: available ? level : null,
    standing: available ? smooth(.55,1,amount) : 0,
    raised: available ? smooth(.15,.65,amount) : 0,
    // Pose conveys amplitude even with reduced motion. Only oscillation stops.
    arms: available && amount > .15 ? 2.35 : 0,
    sway: reducedMotion || !available ? 0 : .002*amount+.026*amount*amount,
    pulse: reducedMotion || !available ? 0 : .055*smooth(.6,1,amount) };
}

export class CrowdDynamics {
  constructor(){this.reset();}
  reset(){this.t=null;this.identity=null;}
  sample(atmosphere,t,identity,reducedMotion=false){
    const raw=crowdPresentation(atmosphere,reducedMotion);
    if(!raw.available || !Number.isFinite(t)){this.reset();return {...crowdPresentation(null,reducedMotion),renderLevel:null};}
    // C is already the engine's average of up to three delivered samples. An
    // extra renderer IIR depended on the frames visited before a seek, and
    // could disagree with the meter at the same source time. Soft population
    // thresholds blend postures without adding another history-dependent C.
    this.t=t;this.identity=identity;
    return {...raw,renderLevel:raw.level};
  }
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
  add(new T.SphereGeometry(1, 7, 5), [0, 1.02, 0], [0.09, 0.12, 0.09], 0xc2a38b, 0, 2);
  add(new T.SphereGeometry(1, 7, 4), [0, 1.09, -0.008], [0.092, 0.055, 0.092], 0x33302d);
  add(new T.CylinderGeometry(0.16, 0.12, 0.38, 7), [0, 0.71, 0], [1, 1, 0.65], 0xffffff, 0, 1);
  for (const side of [-1, 1]) {
    add(new T.CylinderGeometry(0.045, 0.04, 0.32, 5), [side * 0.19, 0.7, 0], [1, 1, 1], 0xc2a38b, side, 2);
    add(new T.CylinderGeometry(0.06, 0.05, 0.32, 5), [side * 0.085, 0.32, 0.05], [1, 1, 1], 0x29333d);
  }
  const geometry = new T.BufferGeometry();
  geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3)); geometry.setAttribute("normal", new T.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("color", new T.Float32BufferAttribute(colors, 3)); geometry.setAttribute("crowdPart", new T.Float32BufferAttribute(parts, 1)); geometry.setIndex(indices);
  geometry.setAttribute("crowdTint", new T.Float32BufferAttribute(tints, 1));
  return geometry;
}

export function createCrowdUniforms() {
  return { crowdTime: { value: 0 }, crowdStanding: { value: 0 }, crowdArms: { value: 0 }, crowdSway: { value: 0 },crowdRaised:{value:0},crowdPulse:{value:0} };
}
export function updateCrowd(uniforms, atmosphere, t, reducedMotion, dynamics=null, identity="") {
  const view = dynamics ? dynamics.sample(atmosphere,t,identity,reducedMotion) : crowdPresentation(atmosphere, reducedMotion);
  uniforms.crowdTime.value = reducedMotion ? 0 : Number.isFinite(t) ? t : 0;
  uniforms.crowdStanding.value = view.standing; uniforms.crowdArms.value = view.arms; uniforms.crowdSway.value = view.sway;
  uniforms.crowdRaised.value=view.raised;uniforms.crowdPulse.value=view.pulse;
  return view;
}

export function standAisles(length) {
  if (!Number.isFinite(length) || length < 12 || length > 160) throw RangeError("Invalid stand length");
  return Array.from({ length: Math.floor((length - 4) / 12.32) }, (_, i) => -length / 2 + (i + 1) * 12.32);
}

function noise(index) {
  let value = index >>> 0;
  value = Math.imul(value ^ value >>> 16, 0x7feb352d);
  value = Math.imul(value ^ value >>> 15, 0x846ca68b);
  return ((value ^ value >>> 16) >>> 0) / 4294967296;
}

export function crowdLayout(length, rows, standSeed = 0) {
  const aisles = standAisles(length), columns = Math.floor(length / 0.56), seats = [];
  if (!Number.isInteger(rows) || rows < 1 || rows > 32) throw RangeError("Invalid stand rows");
  for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
    const x = -length / 2 + col * 0.56 + 0.28;
    // Physical stairs and the middle concourse stay clear even at peak amplitude.
    if (row === 12 || aisles.some(aisle => Math.abs(x - aisle) < 0.7)) continue;
    const index = row * columns + col, seed = noise(index + 1 + standSeed * 65537);
    seats.push({ x: x + (seed - 0.5) * 0.08, y: 0.28 + row * 0.52,
      z: row * 0.76, seed, shape: noise(index + 7919 + standSeed * 31337),
      identity: noise(index + 104729 + standSeed * 99991), clothing: noise(index + 15485863 + standSeed * 49999),
      gesture:noise(index+32452843+standSeed*67867967) });
  }
  return seats;
}

export function createCrowd(length, rows, uniforms, standSeed = 0, atlas = null) {
  const seats = crowdLayout(length, rows, standSeed);
  if(Array.isArray(atlas)){
    const group=new T.Group();
    atlas.forEach((sheet,i)=>{
      const members=seats.filter(s=>Math.min(atlas.length-1,Math.floor(s.identity*atlas.length))===i)
        .map(s=>({...s,identity:s.identity*atlas.length-i}));
      group.add(createAtlasCrowd(members,uniforms,sheet));
    });
    return group;
  }
  if (atlas) return createAtlasCrowd(seats, uniforms, atlas);
  const count = seats.length, geometry = personGeometry();
  const seeds = new Float32Array(count);
  const material = new T.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: 1 });
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = `attribute float crowdPart; attribute float crowdSeed; attribute float crowdTint; attribute float crowdGesture;
      uniform float crowdTime; uniform float crowdStanding; uniform float crowdArms; uniform float crowdSway;
      uniform float crowdRaised; uniform float crowdPulse;\n` + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <color_vertex>", T.ShaderChunk.color_vertex.replace(
      "vColor.rgb *= instanceColor.rgb;", `vColor.rgb *= crowdTint < 0.5 ? vec3(1.0) :
        (crowdTint < 1.5 ? instanceColor.rgb : mix(vec3(0.48, 0.34, 0.25), vec3(1.1, 1.04, 0.96), crowdSeed));`));
    const angle = "crowdPart * step(crowdSeed,crowdRaised) * crowdArms";
    shader.vertexShader = shader.vertexShader.replace("#include <beginnormal_vertex>", `#include <beginnormal_vertex>
      if (abs(crowdPart) > 0.5) {
        float normalAngle = ${angle};
        objectNormal.xy = mat2(cos(normalAngle), sin(normalAngle), -sin(normalAngle), cos(normalAngle)) * objectNormal.xy;
      }`);
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
      float standing = crowdStanding <= 0.0 ? 0.0 : step(crowdSeed, crowdStanding);
      float phase = crowdTime * 2.1 + crowdSeed * 71.0;
      if (abs(crowdPart) > 0.5) {
        float a = ${angle};
        vec2 pivot = vec2(crowdPart * 0.18, 0.88);
        transformed.xy = mat2(cos(a), sin(a), -sin(a), cos(a)) * (transformed.xy - pivot) + pivot;
      }
      transformed.x += sin(phase) * crowdSway * transformed.y;
      transformed.y += standing * (0.22 + pow(max(0.0,sin(phase)),2.0)*crowdPulse);`);
  };
  const crowd = new T.InstancedMesh(geometry, material, count), dummy = new T.Object3D(), color = new T.Color();
  const palette = [0x7e8a91, 0x233544, 0x52646b, 0xada69b, 0x353d40, 0x79877f, 0xada9a0, 0x234b65];
  for (const [index, seat] of seats.entries()) {
    const { seed, shape } = seat; seeds[index] = seed;
    dummy.position.set(seat.x, seat.y, seat.z);
    // Stand rows extend toward +Z; their audience looks toward the -Z pitch edge.
    dummy.rotation.y = Math.PI + (seed - 0.5) * 0.3;
    dummy.scale.set(0.94 + shape * 0.14, 0.9 + seed * 0.2, 0.94 + shape * 0.14); dummy.updateMatrix();
    crowd.setMatrixAt(index, dummy.matrix); crowd.setColorAt(index, color.setHex(palette[Math.floor(seed * palette.length)]));
  }
  geometry.setAttribute("crowdSeed", new T.InstancedBufferAttribute(seeds, 1));
  geometry.setAttribute("crowdGesture",new T.InstancedBufferAttribute(new Float32Array(seats.map(seat=>seat.gesture)),1));
  crowd.instanceMatrix.needsUpdate = true; crowd.instanceColor.needsUpdate = true; crowd.frustumCulled = false;
  crowd.name = "Delivered-amplitude crowd"; return crowd;
}
