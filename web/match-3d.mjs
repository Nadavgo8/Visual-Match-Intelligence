import * as T from "./vendor/three/three.module.js";
import { buildStadium } from "./stadium.mjs";
import { Footballers } from "./footballers.mjs";
import { SceneMotion, worldPosition, cameraView, qualitySettings } from "./scene-state.mjs";

export class Match3D {
  constructor(canvas, onLost) {
    this.canvas = canvas; this.motion = new SceneMotion(); this.quality = "high"; this.reducedMotion = false;
    this.gpu = new T.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.gpu.outputColorSpace = T.SRGBColorSpace; this.gpu.toneMapping = T.ACESFilmicToneMapping;
    this.gpu.toneMappingExposure = 1.15; this.gpu.shadowMap.type = T.PCFShadowMap;
    this.scene = new T.Scene(); this.scene.background = new T.Color(0x182c42);
    this.scene.fog = new T.Fog(0x182c42, 130, 280);
    this.camera = new T.PerspectiveCamera(46, 16 / 9, 0.1, 500);
    this.scene.add(new T.HemisphereLight(0xcde8ff, 0x6d7f5e, 2));
    this.sun = new T.DirectionalLight(0xffe8c9, 3.1); this.sun.position.set(-30, 70, 25);
    Object.assign(this.sun.shadow.camera, { left: -63, right: 63, top: 49, bottom: -49, near: 1, far: 150 });
    this.sun.shadow.normalBias = 0.035; this.sun.shadow.bias = -0.00015;
    this.scene.add(this.sun);
    const fill = new T.DirectionalLight(0xa4cfff, 1.3); fill.position.set(40, 35, -50); this.scene.add(fill);
    this.scene.add(buildStadium(canvas.ownerDocument)); this.footballers = new Footballers(this.scene);
    this.ball = new T.Mesh(new T.IcosahedronGeometry(0.16, 2), new T.MeshStandardMaterial({ color: 0xf9f4e6, roughness: 0.45, flatShading: true }));
    this.ball.castShadow = true; this.ball.visible = false; this.scene.add(this.ball);
    // Small dark panels stay on the ball surface and rotate with its source time.
    const panel = new T.Mesh(new T.IcosahedronGeometry(0.162, 0), new T.MeshStandardMaterial({ color: 0x172330, wireframe: true })); this.ball.add(panel);
    this.lost = event => { event.preventDefault(); onLost(); };
    canvas.addEventListener("webglcontextlost", this.lost);
    this.setQuality("high"); this.resize(); this.mode = "3D stadium";
  }
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
    this.camera.position.set(...view.position); this.camera.lookAt(...view.target);
    if (frame && teams) {
      this.footballers.update(frame, this.motion.update(frame), teams);
      this.ball.visible = true; this.ball.position.set(...worldPosition(...frame.ball, frame.ball_height + 0.16));
      this.ball.rotation.set(frame.t * 2, 0, frame.t * 3);
    } else { this.footballers.hide(); this.motion.reset(); this.ball.visible = false; }
    this.gpu.render(this.scene, this.camera);
    this.canvas.dataset.renderer = "3d";
    this.canvas.dataset.drawCalls = String(this.gpu.info.render.calls);
    this.canvas.dataset.triangles = String(this.gpu.info.render.triangles);
    this.canvas.dataset.actors = String(this.footballers.actors.size);
    this.canvas.dataset.quality = this.quality;
    this.canvas.dataset.camera = this.reducedMotion ? "fixed" : this.cameraMode ?? "broadcast";
  }
  dispose() {
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
