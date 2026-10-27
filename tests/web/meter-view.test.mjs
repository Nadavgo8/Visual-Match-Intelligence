import test from "node:test";
import assert from "node:assert/strict";
import { renderAtmosphere, renderMomentum, renderReplayTime } from "../../web/meter-view.mjs";
import { MatchScreen } from "../../web/match-screen.mjs";

const element = () => ({ style: { setProperty(key,value) { this[key]=value; } }, dataset: {},
  setAttribute(key,value) { this[key]=value; }, textContent: "", title: "" });
function viewFixture() {
  const edges=element(),label=element(),fill=element(); fill.parentElement=element();
  const reset=()=>{ renderAtmosphere(edges,label,null); renderMomentum(fill,null); };
  const measured=()=>{renderAtmosphere(edges,label,{available:true,level:0.8,why:'Measured'});renderMomentum(fill,0.75);};
  return {edges,label,fill,reset,measured};
}
test("snapshot with no meters clears both old edge measurements and team momentum", () => {
  const v=viewFixture(),screen=new MatchScreen(v.reset);
  screen.snapshot({seed:12,match_id:'m',run_id:'r1',t:10},0); v.measured();
  assert.equal(v.edges.style['--edge-fill'],'80%'); assert.equal(v.fill.style.width,'75.0%');
  screen.snapshot({seed:12,match_id:'m',run_id:'r2',t:0},1);
  assert.equal(v.edges.dataset.available,'false'); assert.equal(v.label.textContent,'Atmosphere unavailable');
  assert.equal(v.fill.parentElement.dataset.available,'false'); assert.equal(v.fill.parentElement['aria-label'],'Momentum unavailable');
  assert.equal(v.fill.style.width,'50.0%'); assert.doesNotMatch(v.edges['aria-label'],/80/);
});
test("pending local seek and remote rewind clear meters before replacement data arrives", () => {
  for (const action of [s=>s.beginJump(),s=>s.sync({seed:12,match_id:'m',t:0},1)]) {
    const v=viewFixture(),screen=new MatchScreen(v.reset);
    screen.sync({seed:12,match_id:'m',t:20},0); v.measured(); action(screen);
    assert.equal(v.edges.dataset.available,'false'); assert.equal(v.fill.parentElement.dataset.available,'false');
    v.measured(); assert.equal(v.edges.dataset.available,'true'); assert.equal(v.fill.parentElement.dataset.available,'true');
  }
});
test("missing or malformed momentum never fabricates a valid balance reading", () => {
  const v=viewFixture();
  for (const bad of [null,undefined,NaN,Infinity,-0.1,1.1,'0.5']) {
    renderMomentum(v.fill,bad); assert.equal(v.fill.parentElement['aria-label'],'Momentum unavailable');
  }
  renderMomentum(v.fill,0); assert.match(v.fill.parentElement['aria-label'],/home 0 percent/);
  renderMomentum(v.fill,1); assert.match(v.fill.parentElement['aria-label'],/home 100 percent/);
});

test("a replacement state updates replay position even before its first meters", () => {
  const input = {value: 51};
  renderReplayTime(input, 0); assert.equal(input.value, 0);
  renderReplayTime(input, 20.9); assert.equal(input.value, 20);
  renderReplayTime(input, 22, true); assert.equal(input.value, 20, "do not fight a user's active drag");
  for (const invalid of [null,NaN,Infinity,-1]) renderReplayTime(input, invalid);
  assert.equal(input.value, 20);
});
