import test from "node:test";
import assert from "node:assert/strict";
import { FootballActions, nearbyBallPose } from "../../web/football-actions.mjs";
const player = {id:"p",role:"FW",team:"home",x:40,y:34};
const frame = (t,status,ball=[40,34],extra={}) => ({match_id:"m",run_id:"a",t,ball,ball_height:0,
  ball_in_play:true,players:[player],possession:{status,holder_id:status==="controlled"?"p":null},...extra});

test("a delivered ground release produces a bounded follow-through only after the ball departs",()=>{
  const actions=new FootballActions();
  assert.equal(actions.update(frame(0,"controlled")).size,0);
  const release=actions.update(frame(.05,"loose",[40.5,34]));
  assert.equal(release.get("p").kind,"release");assert.equal(release.get("p").heading,Math.PI/2);
  assert.equal(release.get("p").weight,1);
  assert.deepEqual(actions.update(frame(.05,"loose",[40.5,34])),release,"pause cannot advance the pose");
  assert.ok(actions.update(frame(.25,"loose",[42,34])).get("p").weight<.3);
  assert.equal(actions.update(frame(.47,"loose",[44,34])).size,0);
});

test("release animation cannot be inferred from a seek, missing possession, stoppage or remote player",()=>{
  for(const [first,next] of [
    [frame(0,"controlled"),frame(3,"loose",[42,34])],
    [frame(1,"controlled"),frame(0,"loose",[42,34])],
    [frame(0,"controlled"),frame(.05,"loose",[42,34],{run_id:"b"})],
    [frame(0,"controlled"),frame(.05,"stopped",[42,34],{ball_in_play:false})],
    [frame(0,"controlled"),frame(.05,"unknown",[42,34])],
    [frame(0,"controlled",[30,34]),frame(.05,"loose",[31,34])],
    [frame(0,"controlled"),frame(.05,"loose",[40.01,34])],
    [frame(0,"controlled",[40,34],{ball_height:1.7}),frame(.05,"loose",[41,34],{ball_height:1.8})],
    [frame(0,"controlled",[40,34],{ball:null}),frame(.05,"loose",[41,34])],
    [frame(0,"controlled",[40,34],{players:[player,{...player,id:"a",team:"away",x:40.8}]}),frame(.05,"loose",[41,34])],
  ]) {
    const actions=new FootballActions();actions.update(first);assert.equal(actions.update(next).size,0);
  }
});

test("a received ball softens the receiving foot, with no invented save or future outcome",()=>{
  const actions=new FootballActions();actions.update(frame(0,"loose",[39.8,34]));
  assert.equal(actions.update(frame(.05,"controlled")).get("p").kind,"receive");
  actions.reset();actions.update(frame(0,"loose",[39.8,34],{players:[{...player,role:"GK"}]}));
  assert.equal(actions.update(frame(.05,"controlled",[40,34],{players:[{...player,role:"GK"}]})).size,0);
});

test("a replacement roster clears gestures and history remains bounded through long playback",()=>{
  const actions=new FootballActions();actions.update(frame(0,"controlled"));actions.update(frame(.05,"loose",[41,34]));
  assert.equal(actions.update(frame(.1,"loose",[41.2,34],{players:[]})).size,0);
  for(let i=0;i<1000;i++) actions.update(frame(i/20,"loose",[40,34],{players:[{...player,id:`p${i}`}]}));
  assert.equal(actions.active.size,0);assert.equal(actions.previous.players.size,1);
});

test("a close loose ball gets a current-frame reach without requiring an unsampled control instant",()=>{
  const observed=frame(1,"loose",[40.4,34]);
  const pose=nearbyBallPose(observed,player);assert.equal(pose.kind,"reach");
  assert.ok(Math.abs(pose.weight-.325)<1e-12);assert.equal(pose.heading,Math.PI/2);
  assert.deepEqual(nearbyBallPose(observed,player),pose,"the same source frame remains static");
  assert.equal(nearbyBallPose(frame(1,"loose"),player).heading,null,"coincident points do not invent a facing direction");
  for(const bad of [frame(1,"loose",[41,34]),frame(1,"loose",[40.4,34],{ball_height:1.5}),
    frame(1,"controlled"),frame(1,"loose",[40.4,34],{ball_in_play:false}),
    frame(1,"loose",[40.4,34],{ball_height:NaN}),frame(1,"loose",null)]) assert.equal(nearbyBallPose(bad,player),null);
  assert.equal(nearbyBallPose(observed,{...player,role:"GK"}),null);
});
