import test from "node:test";
import assert from "node:assert/strict";
import {crowdPresentation, CrowdDynamics, crowdLayout} from "../../web/crowd.mjs";

test("quiet, mixed and peak crowd have distinct, proportional postures without attack-driven cheering",()=>{
  const quiet=crowdPresentation({crowd:0,attack:1,level:.2});
  assert.equal(quiet.standing,0);assert.equal(quiet.raised,0);assert.equal(quiet.pulse,0);assert.equal(quiet.sway,0);
  const mixed=crowdPresentation({crowd:.5,attack:0,level:.4});
  assert.equal(mixed.standing,.5,"mid-level crowd must contain a half-seated/half-standing mixture");
  assert.ok(mixed.raised>0 && mixed.raised<.25,"raised hands are a minority at mid-level");
  const peak=crowdPresentation({crowd:1,attack:0,level:.8});
  assert.equal(peak.standing,1);assert.ok(peak.raised>.8 && peak.raised<1);assert.ok(peak.pulse>0);
  assert.deepEqual(crowdPresentation({crowd:.5,attack:1}),mixed);
  for(const level of [null,NaN,Infinity,-1,2]) {
    const missing=crowdPresentation({crowd:level});assert.equal(missing.available,false);
    assert.equal(missing.raised,0);assert.equal(missing.pulse,0);
  }
});

test("population activation remains distributed across both appearance cohorts at mid-level",()=>{
  const seats=crowdLayout(132,24,1),counts=[0,0],standing=[0,0];
  for(const seat of seats){const group=Math.min(1,Math.floor(seat.identity*2));counts[group]++;if(seat.seed<.5)standing[group]++;}
  for(let i=0;i<2;i++)assert.ok(standing[i]/counts[i]>.45 && standing[i]/counts[i]<.55);
});

test("crowd transitions are driven by source time and clear immediately on missing data, seek or new run",()=>{
  const d=new CrowdDynamics();
  assert.equal(d.sample({crowd:0},0,"m/a").renderLevel,0);
  const first=d.sample({crowd:1},.05,"m/a");assert.ok(first.renderLevel>0 && first.renderLevel<.5);
  const paused=d.sample({crowd:1},.05,"m/a");assert.deepEqual(paused,first);
  const later=d.sample({crowd:1},.6,"m/a");assert.ok(later.renderLevel>.95);
  assert.equal(d.sample({crowd:null},.61,"m/a").available,false);
  assert.equal(d.sample({crowd:.8},.62,"m/a").renderLevel,.8);
  assert.equal(d.sample({crowd:.2},0,"m/a").renderLevel,.2);
  assert.equal(d.sample({crowd:.9},.1,"m/b").renderLevel,.9);
  const reduce=d.sample({crowd:1},.2,"m/b",true);
  assert.equal(reduce.renderLevel,1);assert.equal(reduce.sway,0);assert.equal(reduce.pulse,0);assert.equal(reduce.raised,0);
});

test("source-time crowd smoothing is independent of the display refresh rate",()=>{
  const sample=hz=>{const d=new CrowdDynamics();d.sample({crowd:0},0,"m/a");for(let i=1;i<=hz;i++)d.sample({crowd:1},i/hz,"m/a");return d.sample({crowd:1},1,"m/a");};
  assert.ok(Math.abs(sample(20).renderLevel-sample(60).renderLevel)<1e-12);
});

test("discontinuities and invalid source clocks cannot retain a previous crowd reaction",()=>{
  const d=new CrowdDynamics(); d.sample({crowd:1},1,"m/a");
  assert.equal(d.sample({crowd:0},4,"m/a").renderLevel,0);
  const invalid=d.sample({crowd:1},NaN,"m/a");
  assert.equal(invalid.renderLevel,null);assert.equal(invalid.available,false);assert.equal(invalid.standing,0);
  assert.equal(d.sample({crowd:.4},5,"m/a").renderLevel,.4);
  assert.equal(d.sample({crowd:.7},5,"m/a").renderLevel,.7,"a new explicit source snapshot at the same clock replaces the previous observation");
  d.reset(); assert.equal(d.sample({crowd:0},0,"m/a").renderLevel,0);
});
