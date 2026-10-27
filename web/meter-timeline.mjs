// Align already-delivered evidence with the replay frame being displayed.
// This buffer neither reads future match truth nor derives another metric.
export class MeterTimeline {
  constructor(){this.reset();}
  reset(){this.items=[];this.run=null;}
  push(message,run){
    if(!message || !Number.isFinite(message.t) || message.t<0 || typeof run!=="string"
      || message.run_id!==run || (this.run!==null && this.run!==run))return false;
    const last=this.items.at(-1);
    if(last && message.t<last.t)return false;
    this.run=run;
    const copy=structuredClone(message);
    if(last?.t===message.t)this.items[this.items.length-1]=copy;else this.items.push(copy);
    if(this.items.length>64)this.items.shift();
    return true;
  }
  sample(t,run){
    if(!Number.isFinite(t) || run!==this.run)return null;
    for(let i=this.items.length-1;i>=0;i--)if(this.items[i].t<=t+1e-9)return this.items[i];
    return null;
  }
}
