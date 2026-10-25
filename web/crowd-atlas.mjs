import * as T from "./vendor/three/three.module.js";

// Pixel bounds are measured from the original generated alpha, not a promise
// that the image model obeyed a mathematically exact layout.
export function atlasRegions(data) {
  const identities=data?.sprites?.length/3;
  if (!Number.isInteger(data?.width) || !Number.isInteger(data?.height)
    || data.width < 1 || data.height < 1 || data.width > 4096 || data.height > 4096
    || !Array.isArray(data.sprites) || !Number.isInteger(identities) || identities<4 || identities>16
    || (data.identities!==undefined && data.identities!==identities)) throw Error("Invalid crowd atlas");
  return data.sprites.map((sprite, index) => {
    const r = sprite.rect;
    if (!Array.isArray(r) || r.length !== 4 || !r.every(Number.isInteger)
      || r[0] < 0 || r[1] < 0 || r[2] < 1 || r[3] < 1
      || r[0] + r[2] > data.width || r[1] + r[3] > data.height
      || !Number.isFinite(sprite.height) || sprite.height < 1 || sprite.height > 2.5
      || sprite.pose !== ["seated", "standing", "raised"][Math.floor(index / identities)]) throw Error("Invalid crowd sprite");
    return { uv: new T.Vector4(r[0] / data.width, 1 - (r[1] + r[3]) / data.height,
      r[2] / data.width, r[3] / data.height), size: new T.Vector2(sprite.height * r[2] / r[3], sprite.height) };
  });
}

export async function loadAtlasMetadata(group="a") {
  if(!["a","b"].includes(group))throw Error("Invalid crowd atlas group");
  const response = await fetch(new URL(`./assets/crowd/atlas-${group}-v2.json`, import.meta.url));
  if (!response.ok) throw Error("Crowd atlas metadata unavailable");
  const data = await response.json(); atlasRegions(data); return data;
}

export function createAtlasCrowd(seats, uniforms, atlas) {
  const regions = atlasRegions(atlas.metadata);
  const identities=regions.length/3;
  const geometry = new T.PlaneGeometry(1, 1); geometry.translate(0, 0.5, 0);
  const seeds = new Float32Array(seats.map(seat => seat.seed));
  geometry.setAttribute("crowdSeed", new T.InstancedBufferAttribute(seeds, 1));
  geometry.setAttribute("crowdIdentity", new T.InstancedBufferAttribute(new Float32Array(seats.map(seat => seat.identity ?? seat.shape)), 1));
  geometry.setAttribute("crowdGesture",new T.InstancedBufferAttribute(new Float32Array(seats.map(seat=>seat.gesture??seat.shape)),1));
  const palette = [0x364755, 0x666e62, 0x6b4545, 0x9a9685, 0x263e5c, 0x47555f, 0x343638, 0x77818a];
  const clothes = seats.flatMap(seat => new T.Color(palette[Math.floor((seat.clothing ?? seat.shape) * palette.length)]).toArray());
  geometry.setAttribute("crowdCloth", new T.InstancedBufferAttribute(new Float32Array(clothes), 3));
  const material = new T.MeshStandardMaterial({ map: atlas.texture, alphaTest: 0.35,
    side: T.DoubleSide, roughness: 1, alphaToCoverage: true });
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms, { crowdRects: {value: regions.map(r => r.uv)},
      crowdSizes: {value: regions.map(r => r.size)} });
    shader.vertexShader = `attribute float crowdSeed; attribute float crowdIdentity; attribute float crowdGesture;
      attribute vec3 crowdCloth; varying vec3 vCrowdCloth;
      uniform float crowdTime; uniform float crowdStanding; uniform float crowdArms; uniform float crowdSway;
      uniform float crowdRaised; uniform float crowdPulse;
      uniform vec2 crowdSizes[${regions.length}];
      varying vec2 vCrowdUv; varying vec3 vCrowdWeights; varying float vCrowdIdentity;\n` + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <uv_vertex>", `#include <uv_vertex>
      float standing = crowdStanding <= 0.0 ? 0.0 : (crowdStanding >= 1.0 ? 1.0 : smoothstep(crowdSeed-0.06,crowdSeed+0.06,crowdStanding));
      float raised = crowdRaised <= 0.0 ? 0.0 : standing*smoothstep(crowdGesture-0.06,crowdGesture+0.06,crowdRaised);
      int person = min(${identities-1}, int(floor(crowdIdentity * ${identities}.0)));
      vCrowdIdentity=float(person); vCrowdUv=uv;
      vCrowdWeights=vec3(1.0-standing,standing-raised,raised);`);
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
      vec2 size=crowdSizes[person]*vCrowdWeights.x+crowdSizes[person+${identities}]*vCrowdWeights.y+crowdSizes[person+${identities*2}]*vCrowdWeights.z;
      transformed.xy *= size;
      vCrowdCloth = crowdCloth;
      float phase=crowdTime*(3.8+crowdGesture*1.5)+crowdSeed*71.0;
      transformed.x += sin(phase) * crowdSway * transformed.y;
      transformed.y += pow(max(0.0,sin(phase)),2.0)*crowdPulse*standing;`);
    shader.fragmentShader = `varying vec3 vCrowdCloth;varying vec2 vCrowdUv;
      varying vec3 vCrowdWeights;varying float vCrowdIdentity;
      uniform vec4 crowdRects[${regions.length}];\n` + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace("#include <map_fragment>", `
      int person=int(vCrowdIdentity+0.1);
      vec4 a=crowdRects[person],b=crowdRects[person+${identities}],c=crowdRects[person+${identities*2}];
      vec4 seated=vec4(0.0),standing=vec4(0.0),raised=vec4(0.0);
      // A settled spectator needs one texture lookup; only a pose transition
      // samples the other rows. Zero-weight poses contribute exactly nothing.
      if(vCrowdWeights.x>0.0)seated=texture2D(map,a.xy+vCrowdUv*a.zw);
      if(vCrowdWeights.y>0.0)standing=texture2D(map,b.xy+vCrowdUv*b.zw);
      if(vCrowdWeights.z>0.0)raised=texture2D(map,c.xy+vCrowdUv*c.zw);
      // Tight source sheets can place the preceding row's boots above a raised
      // head. Only this empty top-centre gutter is masked; hands stay visible.
      if(vCrowdUv.y>0.94 && abs(vCrowdUv.x-0.5)<0.28)raised.a=0.0;
      vec3 weights=vCrowdWeights*vec3(seated.a,standing.a,raised.a);
      float alpha=weights.x+weights.y+weights.z;
      vec3 rgb=(seated.rgb*weights.x+standing.rgb*weights.y+raised.rgb*weights.z)/max(alpha,0.00001);
      diffuseColor*=vec4(rgb,alpha);
      // Only cool blue fabric is varied. Skin, hair and pale clothing retain
      // the source image; a global instance tint would recolour faces as well.
      float clothMask = smoothstep(0.005, 0.04, diffuseColor.b - diffuseColor.r);
      float clothLight = dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722));
      diffuseColor.rgb = mix(diffuseColor.rgb, vCrowdCloth * max(0.025, clothLight) * 2.3, clothMask * 0.8);`);
  };
  material.customProgramCacheKey=()=>`vmi-crowd-pose-blend-${identities}-v2`;
  const mesh = new T.InstancedMesh(geometry, material, seats.length), dummy = new T.Object3D(), color = new T.Color();
  for (const [index, seat] of seats.entries()) {
    dummy.position.set(seat.x, seat.y, seat.z); dummy.rotation.y = Math.PI + (seat.seed - 0.5) * 0.3;
    dummy.scale.set(0.94 + seat.shape * 0.14, 0.9 + seat.seed * 0.2, 1); dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix); mesh.setColorAt(index, color.setScalar(0.68 + seat.shape * 0.3));
  }
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor.needsUpdate = true; mesh.frustumCulled = false;
  mesh.name = "Delivered-amplitude crowd"; return mesh;
}
