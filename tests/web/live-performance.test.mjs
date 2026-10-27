import test from 'node:test';
import assert from 'node:assert/strict';
import {LivePerformance,canvasVisibleRatio} from '../../web/live-performance.mjs';
const environment={visible:true,focused:true,run:'r1',speed:1,renderer:'3D stadium',quality:'high',camera:'broadcast',visualSignals:true,reducedMotion:false,sceneVisible:true};
const state={seed:12,t:600,playing:true,speed:1};
test('live capture waits for the requested seek and normal-speed playback, then records active source and delivery',()=>{
  const p=new LivePerformance();p.prepare(12);
  assert.equal(p.state({...state,seed:13}),false);assert.equal(p.state({...state,t:0}),false);
  assert.equal(p.state(state),true);assert.equal(p.state(state),false);
  const observe=(now,playing=state)=>p.observe(now,{frame:{t:600+now/1000},state:playing,environment,drawMs:3});
  assert.equal(observe(0,{...state,speed:4}),null);
  observe(0);
  for(let t=20;t<=23000;t+=20){p.message({type:'frame',t:600+t/1000},t,1);observe(t);}
  assert.equal(p.result.valid,true);assert.equal(p.result.fps,50);
  assert.equal(p.result.messages.counts.frame,1001);assert.equal(p.result.messages.frameReceiveP95Ms,20);
  assert.ok(p.result.source.last-p.result.source.first>19.9);
  assert.equal(p.result.presentedFrames,'NOT_VERIFIED');
});

test('one late source jump cannot certify a frozen scene or missing transport',()=>{
  for(const receiptMode of ['none','stale','gap']){
    const p=new LivePerformance();p.prepare(12);p.state(state);
    for(let now=0;now<=23000;now+=20){
      const t=now<22900?603:600+now/1000;
      if(receiptMode==='stale'||(receiptMode==='gap'&&(now<5000||now>22000)))p.message({type:'frame',t},now,1);
      p.observe(now,{frame:{t},state,environment,drawMs:3});
    }
    assert.equal(p.result.valid,false,receiptMode);
  }
});

test('slow render cadence remains valid evidence when accepted tracking advances continuously',()=>{
  const p=new LivePerformance();p.prepare(12);p.state(state);
  for(let now=0;now<=23000;now+=50){
    p.message({type:'frame',t:600+now/1000},now,1);
    if(now%1000===0)p.observe(now,{frame:{t:600+now/1000},state,environment,drawMs:3});
  }
  assert.equal(p.result.valid,true);assert.equal(p.result.fps,1);
  assert.equal(p.result.messages.frameReceiveMaxMs,50);
});

test('accepted source regressions and delivery gaps remain failures even after a burst catches up',()=>{
  for(const fault of ['regression','gap']){
    const p=new LivePerformance();p.prepare(12);p.state(state);
    for(let now=0;now<=23000;now+=20){
      if(fault!=='gap'||now<10000||now>11000)p.message({type:'frame',t:600+now/1000-(fault==='regression'&&now===10000?1:0)},now,1);
      p.observe(now,{frame:{t:600+now/1000},state,environment,drawMs:3});
    }
    assert.equal(p.result.valid,false,fault);
  }
});

test('missing displayed tracking time cannot be replaced by a few valid late samples',()=>{
  const p=new LivePerformance();p.prepare(12);p.state(state);
  for(let now=0;now<=23000&&p.phase!=='done';now+=20){
    p.message({type:'frame',t:600+now/1000},now,1);
    p.observe(now,{frame:{t:now<22900?undefined:600+now/1000},state,environment,drawMs:3});
  }
  assert.equal(p.result.valid,false);assert.match(p.result.reason,/tracking/);
});

test('fallback cannot certify 3D High, and reduced motion is an explicit fixed-camera condition',()=>{
  for(const settings of [{renderer:'2D fallback'},{quality:'low'},{camera:'fixed'},{visualSignals:false},{sceneVisible:false}]){
    const p=new LivePerformance();p.prepare(12);p.state(state);
    assert.equal(p.observe(0,{frame:{t:600},state,environment:{...environment,...settings},drawMs:3}).valid,false);
  }
  const p=new LivePerformance();p.prepare(12);p.state(state);
  const reduced={...environment,reducedMotion:true,camera:'fixed'};
  for(let now=0;now<=23000;now+=50){p.message({type:'frame',t:600+now/1000},now,1);p.observe(now,{frame:{t:600+now/1000},state,environment:reduced,drawMs:3});}
  assert.equal(p.result.valid,true);assert.match(p.result.cameraCondition,/reduced-motion preference preserved/);
});

test('a visible document does not imply a visible match canvas',()=>{
  const r={left:100,right:1100,top:0,bottom:600,width:1000,height:600};
  assert.equal(canvasVisibleRatio(r,1200,800),1);
  assert.equal(canvasVisibleRatio({...r,top:-300,bottom:300},1200,800),.5);
  assert.equal(canvasVisibleRatio({...r,top:-700,bottom:-100},1200,800),0);
  assert.equal(canvasVisibleRatio({...r,width:0},1200,800),0);
});
test('disconnect or a pause invalidates the live result without replacing the existing animation loop',()=>{
  for(const stop of ['disconnect','pause']){
    const p=new LivePerformance();p.prepare(12);p.state(state);
    p.observe(0,{frame:{t:600},state,environment,drawMs:3});
    if(stop==='disconnect')p.invalidate('disconnected');
    const r=p.observe(100,{frame:{t:600.1},state:{...state,playing:stop!=='pause'},environment,drawMs:3});
    assert.equal(r.valid,false);assert.equal(p.phase,'done');
  }
});
test('a failed preparation returns an invalid result and permits retry after reconnection',()=>{
  const p=new LivePerformance();p.prepare(12);p.invalidate('disconnected before seek completed');
  const r=p.observe(1,{frame:null,state:{...state,playing:false},environment,drawMs:0});
  assert.equal(r.valid,false);assert.equal(r.reason,'disconnected before seek completed');assert.equal(p.phase,'done');
  p.prepare(12);assert.equal(p.state(state),true);
});
test('preparation has a bounded timeout and callbacks cannot pass by redrawing stale source time',()=>{
  const p=new LivePerformance();p.prepare(12,100);
  assert.equal(p.observe(30200,{frame:null,state,environment,drawMs:0}).valid,false);
  p.prepare(12,0);p.state(state);
  for(let now=0;now<=23000;now+=20)p.observe(now,{frame:{t:600},state,environment,drawMs:3});
  assert.equal(p.result.valid,false);assert.match(p.result.reason,/source clock/);
});
