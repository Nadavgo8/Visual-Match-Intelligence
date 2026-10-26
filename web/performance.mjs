import * as T from './vendor/three/three.module.js';
import {Match3D,prepareAssets} from './match-3d.mjs?v=3.23';
import {qualitySettings} from './scene-state.mjs?v=3.22';
import {interpolate} from './match-motion.mjs';
import {renderAtmosphere,renderMomentum} from './meter-view.mjs?v=3.3';
import {MarkerState} from './overlay-state.mjs';
import {bannerIcon} from './icons.js';
import {PerformanceCapture} from './performance-capture.mjs';

const $=id=>document.getElementById(id),canvases=['light','minimal','full'].map($);
const capture=new PerformanceCapture(),results=[],longTasks=[],visibility=[];
let assets,replay,active=false,stage=-1,stageStart=0,minimal=null,full=null,lastMeter=null,lastMarker=null;
let marker=new MarkerState(),bannerIndex=0,raf=null;
let longTaskObserver=null,longTaskMonitoring='unsupported',dprQuery=null;
let phases={},matchedSurface=null,bufferRatio=qualitySettings('high',devicePixelRatio).pixelRatio;
const environmentalNotes={cpuThrottling:'UNVERIFIED: inspect DevTools, No throttling required',powerSaving:'UNVERIFIED',
  remoteSharing:'UNVERIFIED',otherSystemLoad:'UNVERIFIED',otherVmiTabs:'UNVERIFIED',
  transport:'Pinned local replay, no WebSocket traffic during measurement'};
const environment=()=>({visible:document.visibilityState==='visible',focused:document.hasFocus(),
  viewport:[innerWidth,innerHeight],canvasCss:[$('stage').clientWidth,$('stage').clientHeight],
  drawingBuffer:[canvases[stage]?.width,canvases[stage]?.height],devicePixelRatio,bufferRatio,quality:'high',camera:'broadcast'});
function gpuInfo(gpu){
  const gl=gpu.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');
  return {renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
    vendor:ext?gl.getParameter(ext.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR),
    version:gl.getParameter(gl.VERSION),antialias:gl.getContextAttributes()?.antialias};
}
try{if(PerformanceObserver.supportedEntryTypes?.includes('longtask')){
longTaskObserver=new PerformanceObserver(list=>{if(active)for(const e of list.getEntries()){
  if(longTasks.length<2000)longTasks.push({start:e.startTime,duration:e.duration});else longTaskMonitoring='supported; record capacity exceeded';
}});longTaskObserver.observe({type:'longtask',buffered:false});longTaskMonitoring='supported';}}catch{longTaskMonitoring='unsupported';}
const invalidateConditions=reason=>{if(active&&capture.active)capture.invalidate(reason);};
function invalidateDimensions(){invalidateConditions('Viewport or device pixel ratio changed during the window.');}
window.addEventListener('resize',invalidateDimensions);
window.addEventListener('blur',()=>invalidateConditions('The page lost focus during the window.'));
document.addEventListener('visibilitychange',()=>{
  if(active)visibility.push({time:performance.now(),state:document.visibilityState});
  if(document.visibilityState!=='visible')invalidateConditions('The page was hidden during the window.');
});
function showResult(){
  $('result').textContent=JSON.stringify({protocolVersion:2,recordedAt:new Date().toISOString(),userAgent:navigator.userAgent,
    hardwareConcurrency:navigator.hardwareConcurrency,deviceMemoryGb:navigator.deviceMemory??null,
    notes:environmentalNotes,replay:{seed:replay.seed,generator:replay.generator_version,start:replay.start,duration:replay.duration},
    acceptance:{fullProduct30Fps:'NOT_VERIFIED',presentedFrames:'NOT_VERIFIED',tvCompanionTransport:'NOT_TESTED_IN_LOCAL_REPLAY'},
    results,visibilityChanges:visibility,longTaskMonitoring,longTasks},null,2);
  renderSummary(results);
  try{localStorage.setItem('vmi.performance.last',$('result').textContent);}catch{/* Copy/download remain available. */}
  $('copy').disabled=$('download').disabled=false;
}
function renderSummary(rows){
  const body=$('summary').querySelector('tbody');body.replaceChildren();
  for(const row of rows){const tr=document.createElement('tr');
    for(const value of [row.stage,row.valid?row.fps.toFixed(1):'INVALID',row.frameMs?.p95?.toFixed(1)??'—',row.renderSubmitCpuMs?.mean?.toFixed(2)??'—']){
      const td=document.createElement('td');td.textContent=value;tr.appendChild(td);
    }body.appendChild(tr);
  }
}
function instrumentCpu(owner,method,name){
  const original=owner[method];owner[method]=function(...args){const begin=performance.now();
    try{return original.apply(this,args);}finally{phases[name]=performance.now()-begin;}
  };
}
function makeMinimal(canvas){
  const gpu=new T.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
  gpu.setPixelRatio(bufferRatio);gpu.setSize(canvas.clientWidth,canvas.clientHeight,false);
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(45,canvas.clientWidth/canvas.clientHeight,.1,100);
  scene.background=new T.Color(0x153c2d);camera.position.z=5;
  const geometry=new T.BoxGeometry(),material=new T.MeshBasicMaterial({color:0x20bec4});
  const cube=new T.Mesh(geometry,material);scene.add(cube);
  return {gpu,draw(t){cube.position.x=Math.sin(t)*1.2;cube.rotation.set(t*.4,t*.7,0);gpu.render(scene,camera);},
    dispose(){geometry.dispose();material.dispose();gpu.dispose();}};
}
function beginStage(now){
  stage++;stageStart=now;lastMeter=null;lastMarker=null;bannerIndex=0;marker.clear();
  canvases.forEach((c,i)=>c.hidden=i!==stage);$('overlay').hidden=stage!==2;
  if(stage===0){const c=canvases[0];c.width=Math.round(c.clientWidth*bufferRatio);c.height=Math.round(c.clientHeight*bufferRatio);}
  if(stage===1)minimal=makeMinimal(canvases[1]);
  if(stage===2){minimal.dispose();minimal=null;full=new Match3D(canvases[2],()=>capture.invalidate('WebGL context lost'),assets);full.cameraMode='broadcast';
    instrumentCpu(full.motion,'update','poseSampling');instrumentCpu(full.footballers,'update','athleteAnimation');
    instrumentCpu(full.gpu,'render','threeRenderSubmit');
  }
  const current=environment();capture.start(now,current);
  const surface=JSON.stringify([current.canvasCss,current.drawingBuffer,current.devicePixelRatio,current.bufferRatio]);
  if(matchedSurface===null)matchedSurface=surface;
  else if(surface!==matchedSurface)capture.invalidate('Stage drawing surfaces differ; results cannot be compared.');
}
function finish(message){
  active=false;if(raf!==null)cancelAnimationFrame(raf);raf=null;
  for(const renderer of [full,minimal])try{renderer?.dispose();}catch(error){console.warn('Diagnostic cleanup failed',error);}
  full=minimal=null;$('phase').textContent=message;$('start').disabled=false;showResult();
}
function fail(error){
  const result=capture.active?capture.invalidate(String(error)):{valid:false,reason:String(error)};
  results.push({stage:['light-animation','minimal-webgl','full-local-replay'][stage],...result});
  finish('Test failed; copy the evidence.');
}
function localSample(t){
  const source=replay.start+Math.min(replay.duration,t),index=Math.min(replay.frames.length-2,Math.floor((source-replay.start)*20));
  return interpolate(replay.frames[index],replay.frames[index+1],source);
}
function drawFull(t){
  const start=performance.now(),frame=localSample(t);phases.localFrameSampling=performance.now()-start;
  const overlayStart=performance.now();let meter=null;
  // Fixture evidence is already delivered. Select only its current source sample.
  for(const candidate of replay.meters){if(candidate.t>frame.t || candidate.at>frame.t)break;meter=candidate;}
  if(meter!==lastMeter){
    full.setAtmosphere(meter?.atmosphere);renderAtmosphere($('edges'),$('meter-label'),meter?.atmosphere);
    renderMomentum($('momentum'),meter?.momentum?.home_index);
    if(meter){$('score').textContent=`${meter.score.home}–${meter.score.away}`;$('clock').textContent=meter.clock;}
    lastMeter=meter;
  }
  while(bannerIndex<replay.banners.length&&replay.banners[bannerIndex].at<=frame.t)marker.accept(replay.banners[bannerIndex++],frame.t);
  const cue=marker.at(frame.t);
  if(cue!==lastMarker){$('marker').hidden=!cue;if(cue){$('icon').innerHTML=bannerIcon(cue.banner??cue.type);$('label').textContent=cue.label;}lastMarker=cue;}
  phases.overlay=performance.now()-overlayStart;
  const drawStart=performance.now();full.draw(frame,replay.teams);
  phases.cameraCrowdBallAndOther=Math.max(0,performance.now()-drawStart-(phases.poseSampling??0)-(phases.athleteAnimation??0)-(phases.threeRenderSubmit??0));
  return frame.t;
}
function animate(now){
  if(!active){raf=null;return;}
  const t=(now-stageStart)/1000,begin=performance.now();let source=null;phases={};
  try{
    if(stage===0){const c=canvases[0],ctx=c.getContext('2d');ctx.fillStyle='#153c2d';ctx.fillRect(0,0,c.width,c.height);
      ctx.fillStyle='#20bec4';ctx.fillRect((.5+.35*Math.sin(t))*c.width,c.height*.45,60*bufferRatio,60*bufferRatio);}
    else if(stage===1)minimal.draw(t);
    else source=drawFull(t);
    const result=capture.observe(now,{environment:environment(),drawMs:performance.now()-begin,sourceTime:source,phases});
    if(result){
      const gpu=stage===1?minimal.gpu:full?.gpu;
      results.push({stage:['light-animation','minimal-webgl','full-local-replay'][stage],...result,
        gpu:gpu?gpuInfo(gpu):null,renderer:gpu?{...gpu.info.render,memory:{...gpu.info.memory}}:null});
      if(!result.valid||stage===2){finish(result.valid?'Finished. Copy or download the result.':'Stopped: conditions changed. Copy the evidence.');return;}
      beginStage(now);
    }
    // At most one status update per second; no capture/polling loop.
    const status=`${['Light animation','Minimal WebGL','Full local 3D'][stage]}: ${Math.floor((now-stageStart)/1000)} / 23s`;
    if($('phase').textContent!==status)$('phase').textContent=status;
    raf=requestAnimationFrame(animate);
  }catch(error){fail(error);}
}
$('start').onclick=()=>{
  if(active||raf!==null)return;results.length=longTasks.length=visibility.length=0;stage=-1;active=true;
  bufferRatio=qualitySettings('high',devicePixelRatio).pixelRatio;matchedSurface=null;
  $('start').disabled=$('copy').disabled=$('download').disabled=true;$('result').textContent='';renderSummary([]);
  dprQuery?.removeEventListener('change',invalidateDimensions);
  dprQuery=matchMedia(`(resolution: ${devicePixelRatio}dppx)`);dprQuery.addEventListener('change',invalidateDimensions);
  try{beginStage(performance.now());raf=requestAnimationFrame(animate);}catch(error){fail(error);}
};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText($('result').textContent);$('phase').textContent='Result copied.';}
  catch{$('phase').textContent='Clipboard unavailable. Use Download result.';}};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([$('result').textContent],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='vmi-performance.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
window.addEventListener('pagehide',()=>{active=false;if(raf!==null)cancelAnimationFrame(raf);raf=null;
  full?.dispose();minimal?.dispose();assets?.dispose();full=minimal=assets=null;longTaskObserver?.disconnect();});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
try{[assets,replay]=await Promise.all([prepareAssets(),fetch('./diagnostics/performance-replay.json').then(r=>{if(!r.ok)throw Error('Replay fixture unavailable');return r.json();})]);
  $('start').disabled=false;$('phase').textContent='Ready. About 70 seconds without interaction.';
  try{const saved=localStorage.getItem('vmi.performance.last');if(saved){const parsed=JSON.parse(saved);if(Array.isArray(parsed.results)){
    $('result').textContent=saved;renderSummary(parsed.results);$('copy').disabled=$('download').disabled=false;
    $('phase').textContent='Previous saved result shown. Start a new test when ready.';
  }}}catch{/* Corrupt or unavailable local storage is not a measurement. */}
}catch(error){$('phase').textContent=`Cannot start: ${error}`;}
