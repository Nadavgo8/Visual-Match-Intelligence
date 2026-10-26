// One bounded measurement session, fed by the page's existing animation chain.
// Callback/render submission cadence is NOT proof of physical presentation.
export class PerformanceCapture {
  constructor({warmupMs=3000,durationMs=20000,capacity=10000}={}) {
    this.warmupMs=warmupMs;this.durationMs=durationMs;this.capacity=capacity;
  }
  start(now,environment) {
    this.environment=structuredClone(environment);this.signature=JSON.stringify(environment);
    this.warmUntil=now+this.warmupMs;this.begin=null;this.previous=null;
    this.intervals=[];this.draws=[];this.phases={};this.sources=new Set();this.firstSource=null;this.lastSource=null;
    this.result=null;this.active=true;
  }
  invalidate(reason) { this.result={valid:false,reason,environment:this.environment};this.active=false;return this.result; }
  observe(now,{environment,drawMs,sourceTime=null,phases={}}) {
    if(!this.active)return this.result;
    if(JSON.stringify(environment)!==this.signature)return this.invalidate('Visibility, focus, dimensions or display conditions changed.');
    if(!environment.visible || !environment.focused)return this.invalidate('The page was not visible and focused.');
    if(!Number.isFinite(now)||!Number.isFinite(drawMs)||drawMs<0)return this.invalidate('Invalid timing sample.');
    if(now<this.warmUntil)return null;
    if(this.begin===null){this.begin=now;this.previous=now;return null;}
    if(now<=this.previous)return this.invalidate('Nonmonotonic or duplicate callback timestamp.');
    this.intervals.push(now-this.previous);this.draws.push(drawMs);this.previous=now;
    for(const [name,value] of Object.entries(phases))if(Number.isFinite(value)&&value>=0){
      (this.phases[name]??=[]).push(value);
    }
    if(Number.isFinite(sourceTime)){
      this.firstSource??=sourceTime;this.lastSource=sourceTime;this.sources.add(sourceTime);
    }
    if(this.intervals.length>this.capacity)return this.invalidate('Measurement sample capacity exceeded.');
    const elapsed=now-this.begin;
    if(elapsed<this.durationMs)return null;
    const stats=values=>{
      const sorted=[...values].sort((a,b)=>a-b);
      const at=p=>sorted[Math.ceil(p*sorted.length)-1];
      return {mean:values.reduce((a,b)=>a+b,0)/values.length,p50:at(.5),p95:at(.95),p99:at(.99),max:sorted.at(-1)};
    };
    this.result={valid:true,environment:this.environment,warmupMs:this.warmupMs,durationMs:elapsed,
      submittedFrames:this.intervals.length,fps:this.intervals.length*1000/elapsed,
      frameMs:stats(this.intervals),renderSubmitCpuMs:stats(this.draws),
      cpuPhases:Object.fromEntries(Object.entries(this.phases).map(([name,values])=>[name,stats(values)])),
      source:{first:this.firstSource,last:this.lastSource,distinctSamples:this.sources.size},
      limitation:'Render submissions and rAF cadence; cross-check presented/dropped frames in DevTools. CPU submission time is not GPU completion time.'};
    this.active=false;return this.result;
  }
}
