import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import * as T from "../../web/vendor/three/three.module.js";
import {atlasRegions, createAtlasCrowd, loadAtlasMetadata} from "../../web/crowd-atlas.mjs";
import {createCrowdUniforms, crowdLayout, updateCrowd} from "../../web/crowd.mjs";

const base = new URL("../../web/assets/crowd/", import.meta.url);
const metadata = JSON.parse(await readFile(new URL("atlas.json", base)));

test("original synthetic crowd PNG has real alpha, recorded hash and twelve separate complete regions", async () => {
  const png = await readFile(new URL("spectators-v1.png", base));
  const provenance = JSON.parse(await readFile(new URL("provenance.json", base)));
  assert.equal(createHash("sha256").update(png).digest("hex"), provenance.sha256);
  assert.equal(png.readUInt32BE(16), metadata.width); assert.equal(png.readUInt32BE(20), metadata.height);
  assert.equal(png[25], 6, "RGBA, rather than an opaque fake checkerboard");
  const regions = atlasRegions(metadata);
  assert.equal(regions.length, 12);
  assert.deepEqual(metadata.sprites.map(s => s.pose), [...Array(4).fill("seated"), ...Array(4).fill("standing"), ...Array(4).fill("raised")]);
  for (let i=0;i<12;i++) for (let j=i+1;j<12;j++) {
    const [x,y,w,h]=metadata.sprites[i].rect, [a,b,c,d]=metadata.sprites[j].rect;
    assert.ok(x+w<a || a+c<x || y+h<b || b+d<y, "alpha regions must not include another spectator");
  }
  assert.equal(regions[0].uv.x, 136/1448);
  assert.equal(regions[0].uv.y, 1-345/1086, "flip image top-origin to WebGL UV origin");
  assert.equal(regions[4].size.y, 1.82); assert.equal(regions[8].size.y, 2.08);
});

test("malformed or out-of-bounds atlas is rejected before geometry allocation", () => {
  for (const change of [d=>{d.width=0;},d=>{d.height=Infinity;},d=>{d.sprites.pop();},
    d=>{d.sprites[0].rect[0]=-1;},d=>{d.sprites[0].rect[2]=5000;},d=>{d.sprites[0].height=NaN;},
    d=>{d.sprites[0].pose="raised";},d=>{d.sprites[0].rect=[1.5,1,2,3];}]) {
    const bad=structuredClone(metadata); change(bad); assert.throws(()=>atlasRegions(bad),/Invalid crowd/);
  }
});

test("metadata loader requests only the local atlas and rejects missing or corrupt data", async () => {
  const oldFetch=globalThis.fetch;
  try {
    globalThis.fetch=async url=>{assert.ok(String(url).endsWith('/web/assets/crowd/atlas.json'));return {ok:true,json:async()=>metadata};};
    assert.strictEqual(await loadAtlasMetadata(),metadata);
    globalThis.fetch=async()=>({ok:false}); await assert.rejects(loadAtlasMetadata(),/unavailable/);
    globalThis.fetch=async()=>({ok:true,json:async()=>({})}); await assert.rejects(loadAtlasMetadata(),/Invalid crowd atlas/);
  } finally {globalThis.fetch=oldFetch;}
});

test("photographic crowd stays instanced, pitch-facing and controlled by the existing source uniforms", () => {
  const texture = new T.Texture(), uniforms=createCrowdUniforms();
  const mesh=createAtlasCrowd(crowdLayout(78,24,2),uniforms,{texture,metadata});
  assert.equal(mesh.count,2921); assert.equal(mesh.geometry.index.count,6);
  assert.strictEqual(mesh.material.map,texture); assert.equal(mesh.material.alphaTest,.65);
  assert.equal(mesh.material.transparent,false); assert.equal(mesh.material.depthWrite,true);
  const matrix=new T.Matrix4(); mesh.getMatrixAt(0,matrix);
  assert.ok(new T.Vector3(0,0,1).transformDirection(matrix).z<-.95);
  const shader={uniforms:{},vertexShader:T.ShaderLib.standard.vertexShader}; mesh.material.onBeforeCompile(shader);
  assert.strictEqual(shader.uniforms.crowdStanding,uniforms.crowdStanding);
  assert.equal(shader.uniforms.crowdRects.value.length,12);
  assert.match(shader.vertexShader,/vMapUv = region.xy \+ vMapUv \* region.zw/);
  assert.match(shader.vertexShader,/crowdArms > 0.01 \? 2 : 1/);
  updateCrowd(uniforms,{crowd:1,attack:0},10,false); assert.equal(uniforms.crowdStanding.value,.68);
  updateCrowd(uniforms,{crowd:1,attack:0},10,true); assert.equal(uniforms.crowdArms.value,0); assert.equal(uniforms.crowdSway.value,0);
  updateCrowd(uniforms,{crowd:0,attack:1},10,false); assert.equal(uniforms.crowdStanding.value,0);
  mesh.dispose(); mesh.geometry.dispose(); mesh.material.dispose(); texture.dispose();
});
