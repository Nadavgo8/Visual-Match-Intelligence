import {PerformanceCapture} from './performance-capture.mjs';

export function canvasVisibleRatio(rect,width,height){
  const area=rect.width*rect.height;
  if(!(area>0))return 0;
  return Math.max(0,Math.min(rect.right,width)-Math.max(rect.left,0))
    *Math.max(0,Math.min(rect.bottom,height)-Math.max(rect.top,0))/area;
}

// Uses the existing TV animation chain and accepted WebSocket callbacks.
export class LivePerformance {
  constructor(){this.capture=new PerformanceCapture();this.phase='idle';this.result=null;}
  prepare(seed,now=0){this.seed=seed;this.preparedAt=now;this.phase='seek';this.result=null;this.messages=[];this.frameReceipts=[];}
  state(state){
    if(this.phase==='seek'&&state.seed===this.seed&&Math.abs(state.t-600)<.1){this.phase='play';return true;}
    return false;
  }
  message(message,now,cpuMs){
    if(!this.capture.active)return;
    if(this.messages.length>=4096||this.frameReceipts.length>=2048){this.invalidate('Live message capacity exceeded.');return;}
    this.messages.push({type:message.type,now,cpuMs});
    if(message.type==='frame')this.frameReceipts.push({now,t:message.t});
  }
  invalidate(reason){
    if(this.capture.active)this.capture.invalidate(reason);
    else if(this.phase==='seek'||this.phase==='play'){
      this.capture.result={valid:false,reason};this.capture.active=false;this.phase='capture';
    }
  }
  observe(now,{frame,state,environment,drawMs}){
    if((this.phase==='seek'||this.phase==='play')&&now-this.preparedAt>30000)this.invalidate('Live replay preparation exceeded 30 seconds.');
    if(this.phase==='play'&&frame&&state?.playing&&state.speed===1&&state.seed===this.seed){
      this.capture.start(now,environment);this.phase='capture';
      if(environment.renderer!=='3D stadium'||environment.quality!=='high'||!environment.visualSignals||!environment.sceneVisible
        ||environment.camera!==(environment.reducedMotion?'fixed':'broadcast')){
        this.capture.invalidate('The live test requires visible 3D High and its accessibility overlay. Keep the game in view; 2D fallback is a separate diagnostic.');
      }
    }
    if(this.phase!=='capture')return null;
    if((!Number.isFinite(frame?.t)||!state?.playing)&&this.capture.active)this.capture.invalidate('Playback stopped or valid tracking disappeared.');
    const result=this.capture.observe(now,{environment,drawMs,sourceTime:frame?.t});
    if(!result)return null;
    // Compare the SAME wall-time window, independent of rAF frequency. A slow
    // render loop can coexist with healthy 20Hz delivery, and vice versa.
    const begin=this.capture.begin??now;
    const messages=this.messages.filter(m=>m.now>=begin&&m.now<=now);
    const frames=this.frameReceipts.filter(m=>m.now>=begin&&m.now<=now);
    const counts={};for(const message of messages)counts[message.type]=(counts[message.type]??0)+1;
    const intervals=frames.slice(1).map((f,i)=>f.now-frames[i].now).sort((a,b)=>a-b);
    const callbacks=messages.map(m=>m.cpuMs);
    const first=frames[0],last=frames.at(-1),span=first?last.now-first.now:0;
    const deliveryMaxGap=Math.max(first?first.now-begin:now-begin,last?now-last.now:now-begin,intervals.at(-1)??0);
    const malformed=frames.some((f,i)=>!Number.isFinite(f.t)||(i&&f.t<=frames[i-1].t));
    const deliveryDrift=first?Math.max(...frames.map(f=>Math.abs((f.t-first.t)*1000-(f.now-first.now)))):null;
    let reason=null;
    if(result.valid){
      if(result.source.maxClockDriftMs>500||!(result.source.observationMs>0))reason='The displayed source clock stalled or had insufficient observations.';
      else if(frames.length<2||deliveryMaxGap>500)reason='Accepted tracking delivery was missing or exceeded the 500ms freshness bound.';
      else if(malformed||deliveryDrift>500)reason='Accepted tracking source time regressed or stalled against receipt time.';
    }
    this.result={mode:'LIVE TV: renderer + overlay + WebSocket delivery',seed:this.seed,...result,
      cameraCondition:environment.reducedMotion?'Fixed camera: reduced-motion preference preserved.':'Broadcast camera.',
      ...(reason?{valid:false,reason}:{}),
      messages:{counts,windowMs:result.durationMs??0,observationMs:span,
        frameReceiveP95Ms:intervals.length?intervals[Math.ceil(intervals.length*.95)-1]:null,
        frameReceiveMaxMs:intervals.at(-1)??null,frameBoundaryMaxGapMs:deliveryMaxGap,sourceReceiptMaxDriftMs:deliveryDrift,
        frameReceiveHz:span>0?(frames.length-1)*1000/span:null,
        callbackCpuMeanMs:callbacks.length?callbacks.reduce((a,b)=>a+b,0)/callbacks.length:null,
        callbackCpuMaxMs:callbacks.length?Math.max(...callbacks):null,
        limitation:'Same measurement window, warmup excluded. Only timeline-accepted frames count as tracking. Callback elapsed time excludes JSON parsing and network transit; source/wall clocks do not establish one-way latency.'},
      companionSync:'Verify the normal companion in the same room; not inferred from TV cadence.',presentedFrames:'NOT_VERIFIED'};
    this.phase='done';return this.result;
  }
}
