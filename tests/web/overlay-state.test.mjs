import test from "node:test";
import assert from "node:assert/strict";
import { MarkerState, edgePresentation, MARKERS } from "../../web/overlay-state.mjs";
const cue = (id, banner = "whistle", t_start = 10, update = false) => ({ cue_id:id, banner, t_start, update });

test("ordinary symbols last exactly three simulation seconds; period end/penalty four", () => {
  for (const [kind, seconds] of Object.entries(MARKERS)) {
    const state = new MarkerState(); state.accept(cue(kind, kind), 10);
    assert.ok(state.at(10)); assert.ok(state.at(10 + seconds - 0.001));
    assert.equal(state.at(10 + seconds), null);
  }
});
test("repeated paused time freezes lifetime; dead-ball time still expires", () => {
  const state = new MarkerState(); state.accept(cue('a'), 10);
  for (let wallFrame = 0; wallFrame < 1000; wallFrame++) assert.ok(state.at(11));
  assert.equal(state.at(13), null); // source clock advances during a football stoppage
});
test("late reason updates the same cue and cannot renew or resurrect it", () => {
  const state = new MarkerState(); state.accept(cue('a'), 10);
  assert.ok(state.accept(cue('a','foul',10,true), 11));
  assert.equal(state.at(12).banner,'foul'); assert.equal(state.at(13),null);
  assert.equal(state.accept(cue('a','penalty',10,true),13.1),false);
  state.clear(); state.accept(cue('b'),10);
  assert.equal(state.accept(cue('b','foul',11,true),11),false);
});
test("one active marker preempts older cues; delayed updates never displace a newer cue", () => {
  const state = new MarkerState(); state.accept(cue('a'),10); state.accept(cue('b','offside',11),11);
  assert.equal(state.at(11).cue_id,'b');
  assert.equal(state.accept(cue('a','foul',10,true),11),false);
  assert.equal(state.accept(cue('c','whistle',9),11),false);
  assert.equal(state.at(12).cue_id,'b');
});
test("seek/reset clears active and retired state for the new playback", () => {
  const state = new MarkerState(); state.accept(cue('a'),10); state.at(13); state.clear();
  assert.equal(state.at(1),null); assert.ok(state.accept(cue('a','kick_off',1),1));
});
test("a delayed kick-off or generic whistle cannot hide an active specific decision", () => {
  const state = new MarkerState(); state.accept(cue('f','foul',10),10);
  assert.equal(state.accept(cue('k','kick_off',10.1),10.1),false);
  assert.equal(state.accept(cue('w','whistle',10.2),10.2),false);
  assert.equal(state.at(11).banner,'foul');
  assert.ok(state.accept(cue('end','half_time',11),11));
  assert.equal(state.at(11).banner,'half_time');
});
test("crowd/VAR/xG/dribble/card are never screen symbols; bad and duplicate input is safe", () => {
  const state = new MarkerState();
  assert.equal(state.accept(null,10),false);
  for (const kind of ['crowd','var','shot_xg','dribble','card','__proto__']) assert.equal(state.accept(cue(kind,kind),10),false);
  assert.equal(state.accept(cue('nan','whistle',NaN),10),false);
  state.accept(cue('a'),10); assert.equal(state.accept(cue('a'),11),false);
  assert.equal(state.at(13),null);
});
test("future markers stay hidden until source time and expired arrivals stay hidden", () => {
  const state = new MarkerState(); state.accept(cue('a'),9.95);
  assert.equal(state.at(9.99),null); assert.ok(state.at(10));
  assert.equal(state.accept(cue('old','foul',1),10),false);
});
test("memory is bounded and two edge bars have the same scalar presentation", () => {
  const state = new MarkerState();
  for(let t=0;t<1000;t++){state.accept(cue(String(t),'whistle',t),t);state.at(t+3);}
  assert.ok(state.retired.size<=64);
  const view=edgePresentation({level:0.55,available:true,mode:'combined'});
  assert.ok(Math.abs(view.height-55)<1e-9); assert.equal(view.percent,55);
  assert.equal(view.color,'rgb(149, 184, 125)');
  assert.equal(edgePresentation({level:null,available:false}).available,false);
  assert.equal(edgePresentation({level:0,available:true}).height,0);
});

test("atmosphere bars stay bright enough to read, rising with the level", () => {
  const b = level => edgePresentation({ level, available: true }).brightness;
  assert.ok(b(0) >= 1 && b(1) > b(0.5) && b(0.5) > b(0));
  assert.ok(Math.abs(b(1) - 1.5) < 1e-9);
  assert.equal(edgePresentation({ level: null, available: false }).brightness, 0.4);
});
