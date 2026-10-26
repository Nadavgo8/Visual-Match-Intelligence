import test from "node:test";
import assert from "node:assert/strict";
import {MeterTimeline} from "../../web/meter-timeline.mjs";
const packet=(t,crowd,attack=0,run_id="r1")=>({t,run_id,atmosphere:{crowd,attack,level:crowd===null?null:.8*crowd+.2*attack}});

test("interpolated world and crowd/bar use one delivered observation at or before source time",()=>{
  const timeline=new MeterTimeline();timeline.push(packet(10,0,1),"r1");timeline.push(packet(10.05,1),"r1");
  assert.equal(timeline.sample(10.025,"r1").atmosphere.crowd,0,"latest delivery must not raise crowd before its displayed time");
  assert.equal(timeline.sample(10.025,"r1").atmosphere.level,.2);
  assert.equal(timeline.sample(10.05,"r1").atmosphere.crowd,1);
  assert.equal(timeline.sample(9.99,"r1"),null);
});

test("missing observations, pause, seek, stale runs and bounded memory stay explicit",()=>{
  const timeline=new MeterTimeline();const original=packet(1,.7);timeline.push(original,"r1");original.atmosphere.crowd=0;
  assert.equal(timeline.sample(1,"r1").atmosphere.crowd,.7);
  assert.strictEqual(timeline.sample(1,"r1"),timeline.sample(1,"r1"));
  assert.equal(timeline.push(packet(.5,1),"r1"),false);
  timeline.push(packet(2,null),"r1");assert.equal(timeline.sample(2,"r1").atmosphere.crowd,null);
  assert.equal(timeline.push(packet(3,1,0,"old"),"r1"),false);
  timeline.reset();assert.equal(timeline.sample(1,"r1"),null);
  timeline.push(packet(0,.2,0,"r2"),"r2");assert.equal(timeline.sample(0,"r2").atmosphere.crowd,.2);
  for(let t=1;t<1000;t++)timeline.push(packet(t,.2,0,"r2"),"r2");
  assert.equal(timeline.items.length,64);assert.equal(timeline.sample(10,"r2"),null);
  for(const t of [NaN,Infinity,-1])assert.equal(timeline.push(packet(t,1,0,"r2"),"r2"),false);
});
