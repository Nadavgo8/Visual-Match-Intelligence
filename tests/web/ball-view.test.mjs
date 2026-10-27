import test from "node:test";
import assert from "node:assert/strict";
import * as T from '../../web/vendor/three/three.module.js';
import {BALL_RADIUS,ballDrawScale,createBall} from "../../web/ball-view.mjs";

test("small-ball treatment is bounded, camera-dependent and never changes a source position",()=>{
  assert.equal(ballDrawScale(80,20,1080),1,"broadcast ball is already readable");
  assert.ok(ballDrawScale(110,46,720)>1,"wide camera needs modest display size support");
  assert.equal(ballDrawScale(400,60,300),1.6,"display size has a strict maximum even at small viewports");
  for(const args of [[NaN,45,720],[20,0,720],[20,180,720],[-1,45,720],[20,45,0]]) assert.equal(ballDrawScale(...args),1);
  const ball=createBall();ball.position.set(12,3,7);const source=ball.position.clone();
  ball.scale.setScalar(ballDrawScale(110,46,720));assert.deepEqual(ball.position,source);
  assert.equal(ball.geometry.parameters.radius,BALL_RADIUS);assert.equal(ball.children.length,2);
  for(const mesh of [ball,...ball.children]){mesh.geometry.dispose();mesh.material.dispose();}
});

test('the broadcast ball has a readable CSS-pixel silhouette with ordinary depth occlusion',()=>{
  for(const [depth,fov,height] of [[70,23,752],[98,17,827],[60,28,720]]){
    const physicalPixels=BALL_RADIUS*height/(depth*Math.tan(fov*Math.PI/360));
    const scale=ballDrawScale(depth,fov,height);
    assert.ok(physicalPixels*scale>=9.49,`ball falls below 9.5 CSS pixels: ${physicalPixels*scale}`);
    assert.ok(scale<=1.6);
  }
  const ball=createBall();
  for(const mesh of [ball,...ball.children]){
    assert.equal(mesh.material.depthTest,true,'do not paint the ball through players or stands');
    assert.equal(mesh.material.transparent,false,'no glow or halo layer');
    mesh.geometry.dispose();mesh.material.dispose();
  }
});

test('dark panel interiors stay above the white sphere instead of disappearing inside it',()=>{
  const ball=createBall(),positions=ball.children[0].geometry.getAttribute('position');
  const centre=new T.Vector3(),point=new T.Vector3();
  for(let i=0;i<positions.count;i+=3){
    centre.set(0,0,0);
    for(let j=0;j<3;j++)centre.add(point.fromBufferAttribute(positions,i+j));
    assert.ok(centre.multiplyScalar(1/3).length()>BALL_RADIUS,'a black panel triangle is hidden inside the white shell');
  }
  for(const mesh of [ball,...ball.children]){mesh.geometry.dispose();mesh.material.dispose();}
});
