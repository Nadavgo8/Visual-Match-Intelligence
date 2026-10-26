import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {LivePerformance,canvasVisibleRatio} from '../../web/live-performance.mjs';
import {MatchScreen} from '../../web/match-screen.mjs';
import {MeterTimeline} from '../../web/meter-timeline.mjs';
import {FrameMetrics} from '../../web/frame-metrics.mjs';
import {renderAtmosphere,renderMomentum,renderReplayTime} from '../../web/meter-view.mjs';

async function harness(){
  const nodes=new Map(),frames=new Map(),commands=[],events=new Map();let now=0,id=0,handlers,draws=0,scrolls=0;
  const node=key=>{
    if(!nodes.has(key))nodes.set(key,{dataset:{},checked:false,value:'1',textContent:'',hidden:false,
      style:{setProperty(key,value){this[key]=value;}},setAttribute(key,value){this[key]=value;},classList:{add(){},remove(){},toggle(){}},
      addEventListener(){},appendChild(){},scrollIntoView(){scrolls++;},removeAttribute(key){delete this.dataset[key];}});
    const result=nodes.get(key);if(key==='mom-fill')result.parentElement=node('momentum');return result;
  };
  const canvas={dataset:{quality:'high',camera:'broadcast',actors:'22'},width:1240,height:697,clientWidth:1240,clientHeight:697,
    getBoundingClientRect:()=>({left:0,top:0,right:1240,bottom:697,width:1240,height:697})};
  const listen=(name,fn)=>events.set(name,fn);
  const context={LivePerformance,canvasVisibleRatio,MatchScreen,MeterTimeline,FrameMetrics,URLSearchParams,structuredClone,console,
    location:{search:'?room=test&performance=live'},performance:{now:()=>now},innerWidth:2048,innerHeight:852,devicePixelRatio:1,
    document:{documentElement:node('root'),getElementById:node,querySelectorAll:()=>[],createElement:()=>node(`new${++id}`),
      visibilityState:'visible',hasFocus:()=>true,addEventListener:listen},window:{addEventListener:listen},
    matchMedia:()=>({matches:false,addEventListener(){},removeEventListener(){}}),
    navigator:{clipboard:{writeText:async()=>{}}},
    requestAnimationFrame:fn=>{frames.set(++id,fn);return id;},
    createRenderer:async()=>({canvas,mode:'3D stadium',draw(){draws++;},setQuality:q=>canvas.dataset.quality=q,
      setCamera:c=>canvas.dataset.camera=c,setAtmosphere(){},setReducedMotion(){},dispose(){}}),
    openSession:options=>{handlers=options;return {send:command=>commands.push(command)};},hostTokenStore:()=>null,
    SyntheticAudio:class{crowd(){}whistle(){}unlock(){}},renderAtmosphere,renderMomentum,renderReplayTime,
    clearTrace(){},prependTrace(){},bannerIcon:()=>''};
  const src=readFileSync(new URL('../../web/tv.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/gm,'');
  await runInNewContext(`(async()=>{${src}\n})()`,context);
  const state={seed:12,t:600,playing:false,speed:1,match_id:'m',run_id:'r',duration:5400,teams:{home:{short:'H'},away:{short:'A'}},chapters:[],score:{home:0,away:0}};
  const message=m=>handlers.onMessage(m);
  message({type:'snapshot',host:true,run_id:'r',state});
  return {node,frames,commands,state,canvas,draws:()=>draws,scrolls:()=>scrolls,message,status:s=>handlers.onStatus(s),dispatch:name=>events.get(name)?.(),
    clock:t=>{now=t;},step(t){now=t;const [key,fn]=frames.entries().next().value;frames.delete(key);fn(t);}};
}
const frame=t=>({type:'frame',match_id:'m',run_id:'r',t,ball:[50,34],ball_height:0,players:[]});

const meters=(t,level,run_id='r')=>({type:'meters',run_id,t,clock:String(t),score:{home:0,away:0},
  momentum:{home_index:.6},atmosphere:level===null?null:{available:true,level,crowd:level,attack:level}});
const edgeView=h=>{
  const edge=h.node('atmosphere-edges');return {fill:edge.style['--edge-fill'],color:edge.style['--edge-color'],
    transition:edge.style['--edge-transition'],available:edge.dataset.available,label:h.node('atmo-label').textContent};
};

test('real TV entry settles edge bars on pause, seek, replacement run and missing data while preserving ordinary transitions',async()=>{
  const h=await harness();h.message({type:'state',...h.state,playing:true});h.message(frame(600));
  h.message(meters(600,.2));h.step(0);assert.equal(edgeView(h).transition,'none');
  h.message(meters(600,.8));h.step(20);assert.match(edgeView(h).transition,/height .35s/);
  h.message({type:'state',...h.state,playing:false});
  const paused=edgeView(h);assert.equal(paused.transition,'none');assert.equal(paused.fill,'80%');
  h.step(1000);assert.deepEqual(edgeView(h),paused,'wall time cannot change paused meter presentation');
  h.node('scrub').onchange({target:{value:'20'}});
  assert.equal(edgeView(h).transition,'none');assert.equal(edgeView(h).available,'false');
  h.message({type:'state',...h.state,t:20,playing:false});h.message(frame(20));h.message(meters(20,.4));h.step(1020);
  const sought=edgeView(h);assert.equal(sought.fill,'40%');assert.equal(sought.transition,'none');
  const direct=await harness();direct.message({type:'snapshot',host:true,run_id:'r',state:{...direct.state,t:20},meters:meters(20,.4)});
  direct.message(frame(20));direct.step(0);assert.deepEqual(sought,edgeView(direct));
  h.message({type:'state',...h.state,t:20,playing:true});h.message(meters(20,.7));h.step(1040);
  assert.match(edgeView(h).transition,/height .35s/);
  h.message(meters(20,null));h.step(1060);assert.equal(edgeView(h).transition,'none');assert.equal(edgeView(h).available,'false');
  h.message(meters(20,.6));h.step(1080);assert.equal(edgeView(h).transition,'none','first recovery cannot animate from unavailable');
  h.message({type:'snapshot',host:true,run_id:'new',state:{...h.state,t:0}});
  assert.equal(edgeView(h).transition,'none');assert.equal(edgeView(h).available,'false');
  h.message(meters(0,.9,'r'));h.step(1100);assert.equal(edgeView(h).available,'false','old-run measurement cannot reappear');
});

test('real TV disconnect cancels any decorative edge transition immediately',async()=>{
  const h=await harness();h.message({type:'state',...h.state,playing:true});h.message(frame(600));
  h.message(meters(600,.2));h.step(0);h.message(meters(600,.8));h.step(20);
  assert.match(edgeView(h).transition,/height .35s/);h.status('disconnected');
  assert.equal(edgeView(h).transition,'none');assert.equal(edgeView(h).fill,'80%');
});

test('real TV entrypoint uses one render chain, rejects old-run frames and captures only accepted live delivery',async()=>{
  const h=await harness();h.node('live-perf').onclick();h.node('live-perf').onclick();
  assert.equal(h.node('presenter-tools').open,true);assert.equal(h.scrolls(),1);
  assert.equal(h.commands.filter(c=>c.cmd==='seek').length,1);assert.equal(h.frames.size,1);
  h.message({type:'state',...h.state});
  assert.deepEqual(h.commands.map(c=>c.cmd),['seek','speed','play']);
  h.message({type:'state',...h.state,playing:true});
  for(let t=0;t<=23000;t+=20){
    h.clock(t);h.message(frame(600+t/1000));h.message({...frame(600+t/1000),run_id:'old'});h.step(t);
  }
  const report=JSON.parse(h.node('live-perf-result').textContent);
  assert.equal(report.valid,true);assert.equal(report.fps,50);assert.equal(report.messages.counts.frame,1001);
  assert.equal(h.frames.size,1);assert.equal(h.draws(),1151);assert.equal(h.commands.at(-1).cmd,'pause');
  assert.equal(h.scrolls(),2,'show the game during capture and the copy button only after completion');
  assert.equal(h.canvas.dataset.quality,'high');assert.equal(h.node('overlay-on').checked,true);
});

test('real TV preparation failure presents a copyable result and can be retried',async()=>{
  const h=await harness();h.node('live-perf').onclick();h.dispatch('blur');h.step(20);
  assert.equal(JSON.parse(h.node('live-perf-result').textContent).valid,false);
  assert.equal(h.node('copy-live-perf').disabled,false);assert.equal(h.frames.size,1);
  h.node('live-perf').onclick();assert.equal(h.commands.filter(c=>c.cmd==='seek').length,2);
});
