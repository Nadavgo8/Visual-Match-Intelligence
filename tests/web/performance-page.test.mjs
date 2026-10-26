import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {PerformanceCapture} from '../../web/performance-capture.mjs';
import {qualitySettings} from '../../web/scene-state.mjs';
import {MarkerState} from '../../web/overlay-state.mjs';

// Execute the real entrypoint with DOM/GPU/scheduler boundaries controlled.
// The renderer intentionally fails in stage two to exercise error recovery.
async function pageHarness(){
  const nodes=new Map(),events=new Map(),frames=new Map();let time=0,id=0,reloads=0;
  const node=key=>{
    if(!nodes.has(key))nodes.set(key,{disabled:false,textContent:'',hidden:false,width:1,height:1,clientWidth:640,clientHeight:360,
      getContext:()=>({fillRect(){}}),querySelector:selector=>node(selector),replaceChildren(){},appendChild(){},click(){}});
    return nodes.get(key);
  };
  const listen=(name,fn)=>{const list=events.get(name)??[];list.push(fn);events.set(name,list);};
  const context={PerformanceCapture,qualitySettings,MarkerState,structuredClone,console,JSON,URL,Blob,Date,Math,Number,Set,
    devicePixelRatio:1,innerWidth:1280,innerHeight:720,navigator:{userAgent:'test'},location:{reload(){reloads++;}},
    document:{visibilityState:'visible',hasFocus:()=>true,getElementById:node,createElement:()=>node(`new${++id}`),addEventListener:listen},
    window:{addEventListener:listen},performance:{now:()=>time},
    requestAnimationFrame:fn=>{frames.set(++id,fn);return id;},cancelAnimationFrame:key=>frames.delete(key),
    matchMedia:()=>({addEventListener:listen,removeEventListener(){}}),
    prepareAssets:async()=>({dispose(){}}),fetch:async()=>({ok:true,json:async()=>({seed:12,generator_version:'2.3.0',start:600,duration:30})}),
    localStorage:{getItem:()=>null,setItem(){}},T:{WebGLRenderer:class{constructor(){throw Error('Test GPU unavailable');}}}};
  const src=readFileSync(new URL('../../web/performance.mjs',import.meta.url),'utf8').replace(/^import .*;\r?\n/gm,'');
  await runInNewContext(`(async()=>{${src}\n})()`,context);
  return {node,context,frames,start:()=>node('start').onclick(),dispatch:(name,event={})=>{for(const fn of events.get(name)??[])fn(event);},
    reloads:()=>reloads,step(now){time=now;const [key,fn]=frames.entries().next().value;frames.delete(key);fn(now);}};
}
test('transient blur and hidden events latch failure even when restored before the next callback',async()=>{
  for(const event of ['blur','visibilitychange']){
    const h=await pageHarness();h.start();
    if(event==='visibilitychange')h.context.document.visibilityState='hidden';h.dispatch(event);
    h.context.document.visibilityState='visible';h.step(3000);
    const report=JSON.parse(h.node('result').textContent);
    assert.equal(report.results[0].valid,false);assert.equal(h.frames.size,0);
  }
});
test('DPR is read at Start rather than captured at module load',async()=>{
  const h=await pageHarness();h.context.devicePixelRatio=2;h.start();
  assert.equal(h.node('light').width,960);assert.equal(h.node('light').height,540);
});
test('GPU stage failure releases the animation chain and allows a fresh Start',async()=>{
  const h=await pageHarness();h.start();h.step(3000);h.step(23000);
  const report=JSON.parse(h.node('result').textContent);
  assert.equal(report.results.at(-1).valid,false);assert.match(report.results.at(-1).reason,/Test GPU unavailable/);
  assert.equal(h.node('start').disabled,false);assert.equal(h.frames.size,0);
  h.start();assert.equal(h.frames.size,1);assert.equal(h.node('start').disabled,true);
});
test('a persisted back/forward restoration reloads after cleanup instead of retaining disposed renderers',async()=>{
  const h=await pageHarness();h.start();h.dispatch('pagehide');assert.equal(h.frames.size,0);
  h.dispatch('pageshow',{persisted:false});assert.equal(h.reloads(),0);
  h.dispatch('pageshow',{persisted:true});assert.equal(h.reloads(),1);
});
