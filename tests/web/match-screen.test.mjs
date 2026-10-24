import test from "node:test";
import assert from "node:assert/strict";
import { MatchScreen } from "../../web/match-screen.mjs";
const state = (extra = {}) => ({ seed:12, match_id:'m1', t:0, playing:true, speed:1, ...extra });
const frame = (t, extra = {}) => ({ match_id:'m1', t, ball:[20,34], ball_height:0,
  ball_in_play:false, players:[], ...extra });
const cue = { cue_id:'cue1', banner:'foul', t_start:1, label:'Foul' };

test("same-run reconnect snapshot replaces frozen poses and markers before new tracking", () => {
  const screen = new MatchScreen(); screen.snapshot(state({run_id:'r1'}),0);
  screen.frame(frame(1,{run_id:'r1'}),1); screen.accept(cue); screen.freeze(2);
  assert.ok(screen.marker()); assert.ok(screen.sample(2));
  assert.ok(screen.snapshot(state({t:1,run_id:'r1',playing:false}),3));
  assert.equal(screen.marker(),null); assert.equal(screen.sample(3),null);
  assert.equal(screen.frame(frame(1,{run_id:'r0'}),4),false);
  assert.ok(screen.frame(frame(1,{run_id:'r1'}),5));
  assert.equal(screen.sample(5).t,1);
});

test("seek clears both layers and ignores in-flight frames and symbols until state", () => {
  const screen = new MatchScreen(); screen.sync(state(),0); screen.frame(frame(1),1); screen.accept(cue);
  screen.beginJump(); assert.equal(screen.sample(2),null); assert.equal(screen.marker(),null);
  assert.equal(screen.frame(frame(2),3),false); assert.equal(screen.accept(cue),false);
  screen.sync(state({t:0,playing:false}),4); assert.ok(screen.frame(frame(0),5));
  assert.equal(screen.sample(5).t,0); assert.equal(screen.marker(),null);
});
test("same-seed run reset clears a paused marker and rejects old transport frames", () => {
  const screen = new MatchScreen(); screen.sync(state({run_id:'r1'}),0);
  screen.frame(frame(1,{run_id:'r1'}),1); screen.accept(cue);
  assert.ok(screen.marker());
  assert.ok(screen.sync(state({t:1,run_id:'r2',playing:false}),2));
  assert.equal(screen.marker(),null); assert.equal(screen.frame(frame(1,{run_id:'r1'}),3),false);
  assert.ok(screen.frame(frame(1,{run_id:'r2'}),4));
});
test("pause freezes both layers; stopped football still consumes symbol lifetime", () => {
  const screen = new MatchScreen(); screen.sync(state(),0); screen.frame(frame(1),1); screen.accept(cue);
  screen.sync(state({t:1,playing:false}),2);
  assert.deepEqual(screen.sample(2),screen.sample(50000)); assert.ok(screen.marker());
  screen.sync(state({t:1,playing:true}),50001); screen.frame(frame(4),50002);
  assert.equal(screen.marker(),null); assert.equal(screen.sample(60000).t,4);
});
test("foreign or malformed frames cannot advance either presentation clock", () => {
  const screen = new MatchScreen(); screen.sync(state(),0); screen.frame(frame(1),1); screen.accept(cue);
  assert.equal(screen.frame(frame(6,{match_id:'other'}),2),false);
  assert.equal(screen.frame(frame(6,{ball_height:NaN}),3),false);
  assert.equal(screen.liveTime,1); assert.ok(screen.marker());
});
test("state-only remote rewind clears stale symbols and football positions", () => {
  const screen = new MatchScreen(); screen.sync(state(),0); screen.frame(frame(2),1); screen.accept(cue);
  assert.ok(screen.sync(state({t:0}),2));
  assert.equal(screen.sample(2),null); assert.equal(screen.marker(),null);
});
test("a forward state jump clears the marker whenever it clears the frame buffer", () => {
  const screen = new MatchScreen(); screen.sync(state(),0); screen.frame(frame(1),1); screen.accept(cue);
  assert.ok(screen.sync(state({t:2.5}),2));
  assert.equal(screen.sample(2),null); assert.equal(screen.marker(),null);
});
