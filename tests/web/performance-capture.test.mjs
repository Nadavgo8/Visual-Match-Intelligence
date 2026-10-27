import test from 'node:test';
import assert from 'node:assert/strict';
import {PerformanceCapture} from '../../web/performance-capture.mjs';
const env={visible:true,focused:true,width:1280,height:720,dpr:1};
test('one session warms up, observes twenty seconds, and freezes its result',()=>{
  const c=new PerformanceCapture();c.start(0,env);
  for(let t=0;t<=23000;t+=20)c.observe(t,{environment:env,drawMs:2,sourceTime:600+t/1000});
  const r=c.result;assert.equal(r.valid,true);assert.equal(r.durationMs,20000);
  assert.equal(r.submittedFrames,1000);assert.equal(r.fps,50);
  assert.equal(r.frameMs.p95,20);assert.equal(r.renderSubmitCpuMs.mean,2);
  assert.ok(r.source.last-r.source.first>19.9);assert.equal(r.source.distinctSamples,1000);
  c.observe(99999,{environment:env,drawMs:100});assert.equal(c.result,r);
});
test('a genuine long frame stays in evidence rather than being filtered out',()=>{
  const c=new PerformanceCapture({warmupMs:0});c.start(0,env);
  c.observe(0,{environment:env,drawMs:2});
  for(let t=20;t<=19000;t+=20)c.observe(t,{environment:env,drawMs:2});
  c.observe(20000,{environment:env,drawMs:25});
  assert.equal(c.result.frameMs.max,1000);assert.equal(c.result.submittedFrames,951);
  assert.equal(c.result.fps,47.55);
});
test('changed conditions, hidden views, duplicate chains and capacity overflow invalidate a run',()=>{
  for(const changed of [{...env,visible:false},{...env,focused:false},{...env,width:640}]){
    const c=new PerformanceCapture();c.start(0,env);c.observe(1,{environment:changed,drawMs:1});assert.equal(c.result.valid,false);
  }
  const c=new PerformanceCapture({warmupMs:0,capacity:2});c.start(0,env);
  c.observe(0,{environment:env,drawMs:1});c.observe(0,{environment:env,drawMs:1});assert.equal(c.result.valid,false);
  c.start(0,env);for(let t=0;t<4;t++)c.observe(t,{environment:env,drawMs:1});assert.equal(c.result.valid,false);
});
test('a transient interruption remains invalid after conditions are restored before the next frame',()=>{
  const c=new PerformanceCapture({warmupMs:0});c.start(0,env);c.observe(0,{environment:env,drawMs:1});
  const invalid=c.invalidate('Hidden then restored between callbacks');
  for(let t=20;t<=20000;t+=20)c.observe(t,{environment:env,drawMs:1});
  assert.equal(c.result,invalid);assert.equal(c.result.valid,false);
  assert.equal(c.result.reason,'Hidden then restored between callbacks');
  c.start(30000,env);assert.equal(c.active,true);assert.equal(c.result,null);
});
test('CPU phases remain separate from frame cadence and missing observations',()=>{
  const c=new PerformanceCapture({warmupMs:0,durationMs:100});c.start(0,env);
  c.observe(0,{environment:env,drawMs:1});
  c.observe(50,{environment:env,drawMs:10,phases:{actors:4,submit:6,bad:NaN}});
  c.observe(100,{environment:env,drawMs:12,phases:{actors:6,submit:6}});
  assert.equal(c.result.fps,20);assert.equal(c.result.renderSubmitCpuMs.mean,11);
  assert.equal(c.result.cpuPhases.actors.mean,5);assert.equal(c.result.cpuPhases.submit.mean,6);
  assert.equal(c.result.cpuPhases.bad,undefined);
});
