import test from "node:test";
import assert from "node:assert/strict";
import * as T from "../../web/vendor/three/three.module.js";
import { buildStadium } from "../../web/stadium.mjs";
import { cameraView, worldPosition } from "../../web/scene-state.mjs";

// The 2D texture API is the boundary fake. Actual geometry, transforms and raycasts run.
const context = new Proxy({}, { get: (_target,key) => key === 'createRadialGradient'
  ? () => ({addColorStop(){}}) : () => {} });
const document = { createElement: () => ({ width: 0, height: 0, getContext: () => context }) };
test("stadium batches static detail and leaves the broadcast line of sight open", () => {
  const stadium = buildStadium(document); stadium.updateMatrixWorld(true);
  let meshes = 0, spectators = 0, seats = 0;
  stadium.traverse(object => {
    if (object.isMesh) meshes++;
    if (object.isInstancedMesh && object.name === "Delivered-amplitude crowd") spectators += object.count;
    if (object.isInstancedMesh && object.name === "Individual stadium seats") seats += object.count / 2;
  });
  assert.ok(meshes < 30, `static draw count must stay bounded: ${meshes}`);
  assert.ok(spectators > 5000 && spectators < 15000);
  assert.equal(seats,spectators,"static batching must preserve every individual seat instance");
  const matrix=new T.Matrix4(),position=new T.Vector3(),scale=new T.Vector3(),rotation=new T.Quaternion();
  let masts=0;
  stadium.traverse(object=>{
    if(!object.isInstancedMesh || object.name) return;
    for(let i=0;i<object.count;i++) {
      object.getMatrixAt(i,matrix); matrix.decompose(position,rotation,scale);
      if(Math.abs(scale.y-23)<.001 && scale.x<.3 && scale.z<.3) {
        masts++; assert.ok(position.z<=-65,"near-side lighting poles must not cross the broadcast composition");
      }
    }
  });
  assert.equal(masts,2);
  for (const mode of ["broadcast", "wide"]) for (const x of [2, 52.5, 103]) for (const y of [2, 34, 66]) {
    const view = cameraView(16 / 9, false, [x, y], mode);
    const origin = new T.Vector3(...view.position), target = new T.Vector3(...worldPosition(x, y, 0.3));
    const ray = new T.Raycaster(origin, target.clone().sub(origin).normalize(), 0.1, origin.distanceTo(target) - 0.5);
    assert.equal(ray.intersectObject(stadium, true).length, 0, `${mode} camera occludes ${x},${y}`);
  }
});
