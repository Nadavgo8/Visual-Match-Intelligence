import * as T from "./vendor/three/three.module.js";
import { buildStadium } from "./stadium.mjs?v=3.14";
import { DetailedFootballers, loadAthlete } from "./athlete.mjs?v=3.11";
import { updateCrowd, CrowdDynamics } from "./crowd.mjs?v=3.11";
import { loadAtlasMetadata } from "./crowd-atlas.mjs?v=3.11";
import { SceneMotion, worldPosition, cameraView, qualitySettings } from "./scene-state.mjs?v=3.14";

export async function prepareAssets() {
  const loader = new T.TextureLoader();
  const results = await Promise.allSettled([loadAthlete(), ...["color", "normal"].map(name => loader.loadAsync(new URL(`./assets/turf/${name}.jpg`, import.meta.url).href)),
    ...["a","b"].map(group=>loader.loadAsync(new URL(`./assets/crowd/spectators-${group}-v2.png`,import.meta.url).href)),
    loadAtlasMetadata("a"),loadAtlasMetadata("b")]);
  if (results.some(result => result.status === "rejected")) {
    for (const result of results) if (result.status === "fulfilled" && result.value?.isTexture) result.value.dispose();
    throw Error("Local 3D assets unavailable");
  }
  const [athlete, color, normal, crowdA, crowdB, metadataA, metadataB] = results.map(result => result.value);
  for (const texture of [color, normal]) {
    texture.wrapS = texture.wrapT = T.RepeatWrapping; texture.repeat.set(114 / 1.4, 76 / 1.4); texture.anisotropy = 8;
  }
  color.colorSpace = T.SRGBColorSpace;
  for(const crowd of [crowdA,crowdB]){crowd.colorSpace=T.SRGBColorSpace;crowd.anisotropy=4;}
  return { athlete, turfMaps: { color, normal }, crowdAtlas: [{texture:crowdA,metadata:metadataA},{texture:crowdB,metadata:metadataB}],
    dispose() { color.dispose(); normal.dispose(); crowdA.dispose();crowdB.dispose(); } };
}

export class Match3D {
  constructor(canvas, onLost, assets) {
    this.canvas = canvas; this.motion = new SceneMotion();this.crowdDynamics=new CrowdDynamics(); this.quality = "high"; this.reducedMotion = false;
    this.gpu = new T.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.gpu.outputColorSpace = T.SRGBColorSpace; this.gpu.toneMapping = T.ACESFilmicToneMapping;
    this.gpu.toneMappingExposure = 0.92; this.gpu.shadowMap.type = T.PCFShadowMap;
    this.scene = new T.Scene(); this.scene.background = new T.Color(0x929e9b);
    this.scene.fog = new T.Fog(0x929e9b, 150, 350);
    this.camera = new T.PerspectiveCamera(46, 16 / 9, 0.1, 500);
    this.scene.add(new T.HemisphereLight(0xe3e9ef, 0x687651, 1.6));
    this.sun = new T.DirectionalLight(0xfff8eb, 2.5); this.sun.position.set(-30, 70, 25);
    Object.assign(this.sun.shadow.camera, { left: -63, right: 63, top: 49, bottom: -49, near: 1, far: 150 });
    this.sun.shadow.normalBias = 0.035; this.sun.shadow.bias = -0.00015;
    this.scene.add(this.sun);
    const fill = new T.DirectionalLight(0xc5d7df, 0.65); fill.position.set(40, 35, -50); this.scene.add(fill);
    this.stadium = buildStadium(canvas.ownerDocument, assets.turfMaps, assets.crowdAtlas); this.scene.add(this.stadium);
    this.footballers = new DetailedFootballers(this.scene, assets.athlete, canvas.ownerDocument);
    this.ball = new T.Mesh(new T.IcosahedronGeometry(0.16, 2), new T.MeshStandardMaterial({ color: 0xf9f4e6, roughness: 0.45, flatShading: true }));
    this.ball.castShadow = true; this.ball.visible = false; this.scene.add(this.ball);
    // Dark panels stay on the ball surface and roll with delivered displacement.
    const panel = new T.Mesh(new T.IcosahedronGeometry(0.162, 0), new T.MeshStandardMaterial({ color: 0x172330, wireframe: true })); this.ball.add(panel);
    this.lost = event => { event.preventDefault(); onLost(); };
    canvas.addEventListener("webglcontextlost", this.lost);
    this.setQuality("high"); this.resize(); this.mode = "3D stadium";
  }
  setAtmosphere(value) { this.atmosphere = value; }
  setQuality(quality) {
    this.quality = quality; const q = qualitySettings(quality, window.devicePixelRatio || 1);
    this.gpu.setPixelRatio(q.pixelRatio); this.gpu.shadowMap.enabled = q.shadows;
    this.sun.castShadow = q.shadows;
    if (q.shadows) this.sun.shadow.mapSize.set(q.shadowSize, q.shadowSize);
    this.width = 0;
  }
  resize() {
    const w = Math.max(1, this.canvas.clientWidth), h = Math.max(1, this.canvas.clientHeight);
    if (w === this.width && h === this.height) return;
    this.width = w; this.height = h; this.gpu.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }
  draw(frame, teams) {
    this.resize();
    const view = cameraView(this.camera.aspect, this.reducedMotion, frame?.ball, this.cameraMode);
    this.camera.fov = view.fov; this.camera.updateProjectionMatrix();
    this.camera.position.set(...view.position); this.camera.lookAt(...view.target);
    const crowd = updateCrowd(this.stadium.userData.crowdUniforms, this.atmosphere, frame?.t ?? 0, this.reducedMotion,
      this.crowdDynamics,frame?`${frame.match_id}/${frame.run_id??""}`:"");
    if (frame && teams) {
      this.footballers.update(frame, this.motion.update(frame), teams);
      this.ball.visible = true; this.ball.position.set(...worldPosition(...frame.ball, frame.ball_height + 0.16));
      this.ball.rotation.set(this.motion.ballRoll.x, 0, this.motion.ballRoll.z);
    } else { this.footballers.hide(); this.motion.reset(); this.ball.visible = false; }
    this.gpu.render(this.scene, this.camera);
    this.canvas.dataset.renderer = "3d";
    this.canvas.dataset.drawCalls = String(this.gpu.info.render.calls);
    this.canvas.dataset.triangles = String(this.gpu.info.render.triangles);
    this.canvas.dataset.actors = String(this.footballers.actors.size);
    this.canvas.dataset.quality = this.quality;
    this.canvas.dataset.camera = this.reducedMotion ? "fixed" : this.cameraMode ?? "broadcast";
    this.canvas.dataset.crowdLevel = crowd.available ? String(crowd.level) : "unavailable";
    this.canvas.dataset.crowdStanding = String(crowd.standing);
    this.canvas.dataset.crowdRaised=String(crowd.raised);
  }
  dispose() {
    this.footballers.dispose();
    this.canvas.removeEventListener("webglcontextlost", this.lost);
    const geometries = new Set(), materials = new Set(), textures = new Set();
    this.scene.traverse(object => {
      if (object.isInstancedMesh) object.dispose();
      if (object.geometry) geometries.add(object.geometry);
      for (const mat of Array.isArray(object.material) ? object.material : [object.material]) if (mat) materials.add(mat);
    });
    for (const mat of materials) {
      for (const value of Object.values(mat)) if (value?.isTexture) textures.add(value);
      mat.dispose();
    }
    for (const geometry of geometries) geometry.dispose();
    for (const texture of textures) texture.dispose();
    this.sun.shadow.map?.dispose(); this.gpu.dispose();
  }
}
