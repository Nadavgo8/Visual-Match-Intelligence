import test from "node:test";
import assert from "node:assert/strict";
import {BALL_RADIUS,ballDrawScale,createBall} from "../../web/ball-view.mjs";

test("small-ball treatment is bounded, camera-dependent and never changes a source position",()=>{
  assert.equal(ballDrawScale(80,20,1080),1,"broadcast ball is already readable");
  assert.ok(ballDrawScale(110,46,720)>1,"wide camera needs modest display size support");
  assert.equal(ballDrawScale(400,60,300),1.5,"no unbounded ball enlargement at small viewports");
  for(const args of [[NaN,45,720],[20,0,720],[20,180,720],[-1,45,720],[20,45,0]]) assert.equal(ballDrawScale(...args),1);
  const ball=createBall();ball.position.set(12,3,7);const source=ball.position.clone();
  ball.scale.setScalar(ballDrawScale(110,46,720));assert.deepEqual(ball.position,source);
  assert.equal(ball.geometry.parameters.radius,BALL_RADIUS);assert.equal(ball.children.length,2);
  for(const mesh of [ball,...ball.children]){mesh.geometry.dispose();mesh.material.dispose();}
});
