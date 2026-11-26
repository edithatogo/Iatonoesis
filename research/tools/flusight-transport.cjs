'use strict';
function parseLocations(raw) {
  const [header,...lines]=raw.trim().split(/\r?\n/);
  if(!header.startsWith('abbreviation,location,location_name,population')) throw Error('location schema mismatch');
  const states=[],seen=new Set();
  for(const l of lines){
    const [abbr,id,name,pop]=l.split(',');
    if(['US','11','72'].includes(id)) continue;
    if(!/^[A-Z]{2}$/.test(abbr)||!/^\d{2}$/.test(id)||!name||!Number.isFinite(+pop)||+pop<=0) throw Error('invalid state metadata');
    if(seen.has(id))throw Error('duplicate state');seen.add(id);states.push({id,name,abbr});
  }
  return states.sort((a,b)=>a.id.localeCompare(b.id));
}

function partitionStates(states){
  const p={development:[],calibration:[],test:[]};
  [...states].sort((a,b)=>a.id.localeCompare(b.id)).forEach((s,i)=>p[i%5<3?'development':i%5===3?'calibration':'test'].push(s));
  return p;
}

function parseRates(raw,states){
  const [header,...lines]=raw.trim().split(/\r?\n/);
  if(header!=='"date","location","location_name","value","weekly_rate"')throw Error('rate schema mismatch');
  const names=new Map(states.map(s=>[s.id,s.name])),out=new Map();
  for(const l of lines){
    const m=/^"(\d{4}-\d{2}-\d{2})","([^"]+)","([^"]+)",([^,]+),([^,]+)$/.exec(l);
    if(!m)throw Error('malformed rate row');
    const [,date,id,name,value,rate]=m;
    if(!names.has(id))continue;
    if(names.get(id)!==name)throw Error('location name mismatch');
    if(!Number.isFinite(Date.parse(date))||new Date(Date.parse(date)).toISOString().slice(0,10)!==date||new Date(Date.parse(date)).getUTCDay()!==6)throw Error('invalid week date');
    const key=id+'|'+date;if(out.has(key))throw Error('duplicate state-week');
    const x=rate==='NA'?null:Number(rate),v=value==='NA'?null:Number(value);
    if((x===null)!==(v===null)||(x!==null&&(!Number.isFinite(x)||x<0||!Number.isFinite(v)||v<0)))throw Error('invalid rate');
    out.set(key,x);
  }
  return out;
}

function mean(xs){if(!xs.length)throw Error('empty mean');return xs.reduce((a,b)=>a+b,0)/xs.length;}

function buildEnvironment(rates,state,start){
  const record={state:state.id,name:state.name,start};
  const values=Array.from({length:20},(_,i)=>rates.get(state.id+'|'+new Date(Date.parse(start)+i*604800000).toISOString().slice(0,10)));
  const h=values.slice(0,8);
  if(h.some(x=>!Number.isFinite(x)))return {...record,status:'missing_history'};
  const mu=mean(h),changes=h.slice(1).map((x,i)=>Math.abs(x-h[i]));
  const features=[mu,Math.sqrt(mean(h.map(x=>(x-mu)**2))),h.at(-1),mean(changes)];
  if(values.slice(8).some(x=>!Number.isFinite(x)))return {...record,status:'missing_target',features};
  const actual=mean(values.slice(8).map((x,i)=>Math.abs(x-values[i+7])));
  return {...record,status:'eligible',features,actual};
}

function solve(a,b){
  a=a.map((row,i)=>[...row,b[i]]);
  for(let i=0;i<b.length;i++){
    let pivot=i;for(let j=i+1;j<b.length;j++)if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;
    [a[i],a[pivot]]=[a[pivot],a[i]];
    if(Math.abs(a[i][i])<1e-12)throw Error('singular fit');
    const v=a[i][i];a[i]=a[i].map(x=>x/v);
    for(let j=0;j<b.length;j++)if(i!==j){const d=a[j][i];a[j]=a[j].map((x,k)=>x-d*a[i][k]);}
  }
  return a.map(x=>x.at(-1));
}

function fit(train){
  if(train.length<5)throw Error('insufficient development environments');
  const centers=Array.from({length:4},(_,i)=>mean(train.map(r=>r.features[i])));
  const scales=centers.map((m,i)=>Math.max(1e-9,Math.sqrt(mean(train.map(r=>(r.features[i]-m)**2)))));
  const standard=f=>f.map((x,i)=>(x-centers[i])/scales[i]);
  const rows=train.map(r=>({x:standard(r.features),actual:r.actual,state:r.state,start:r.start}));
  const a=Array.from({length:5},(_,i)=>Array.from({length:5},(_,j)=>i===j&&i!==0?1:0)),b=Array(5).fill(0);
  for(const row of rows){const x=[1,...row.x];for(let i=0;i<5;i++){b[i]+=x[i]*row.actual;for(let j=0;j<5;j++)a[i][j]+=x[i]*x[j];}}
  return {centers,scales,rows,weights:solve(a,b),constant:mean(train.map(r=>r.actual))};
}

function estimate(features,model){
  const x=features.map((v,i)=>(v-model.centers[i])/model.scales[i]);
  const near=[...model.rows].sort((a,b)=>{
    const dist=r=>r.x.reduce((s,v,i)=>s+(v-x[i])**2,0);
    return dist(a)-dist(b)||a.state.localeCompare(b.state)||a.start.localeCompare(b.start);
  }).slice(0,3);
  return {source_constant:model.constant,history_change:features[3],knn:mean(near.map(r=>r.actual)),
          ridge:Math.max(0,model.weights[0]+x.reduce((s,v,i)=>s+v*model.weights[i+1],0))};
}

function conformal(values){
  const k=Math.ceil((values.length+1)*.9);return k>values.length?null:[...values].sort((a,b)=>a-b)[k-1];
}

function analyse(locText,rateText){
  const locations=parseLocations(locText);
  if(locations.length!==50)throw Error('expected fifty state identities');
  const parts=partitionStates(locations),rates=parseRates(rateText,locations);
  const seasons={development:['2022-10-08','2023-10-07'],calibration:['2022-10-08','2023-10-07'],test:['2024-10-05']};
  const env=Object.fromEntries(Object.keys(parts).map(p=>[p,parts[p].flatMap(s=>seasons[p].map(start=>buildEnvironment(rates,s,start)))]));
  const eligible=Object.fromEntries(Object.keys(env).map(k=>[k,env[k].filter(r=>r.status==='eligible')]));
  if(!eligible.calibration.length||!eligible.test.length)throw Error('empty eligible evaluation partition');
  const model=fit(eligible.development),arms=['source_constant','history_change','knn','ridge'];
  const cal=eligible.calibration.map(r=>({...r,estimate:estimate(r.features,model)}));
  const held=eligible.test.map(r=>({...r,estimate:estimate(r.features,model)}));
  const metrics={};
  for(const arm of arms){
    const residualByState=new Map();
    for(const r of cal){const e=Math.abs(r.actual-r.estimate[arm]);residualByState.set(r.state,Math.max(e,residualByState.get(r.state)||0));}
    const radius=conformal([...residualByState.values()]);
    const errors=held.map(r=>Math.abs(r.actual-r.estimate[arm]));
    metrics[arm]={n:held.length,calibration_state_clusters:residualByState.size,mae:mean(errors),
      interval_radius:radius,interval_coverage:radius===null?null:mean(errors.map(e=>Number(e<=radius))),
      mean_interval_width:radius===null?null:mean(held.map(r=>r.estimate[arm]+radius-Math.max(0,r.estimate[arm]-radius))),
      mean_paired_delta_vs_constant:mean(held.map((r,i)=>errors[i]-Math.abs(r.actual-r.estimate.source_constant)))};
  }
  const partitions=Object.fromEntries(Object.entries(env).map(([k,rows])=>[k,{states:parts[k].map(s=>s.id),planned:rows.length,eligible:eligible[k].length,missing_history:rows.filter(r=>r.status==='missing_history').length,missing_target:rows.filter(r=>r.status==='missing_target').length,excluded:rows.filter(r=>r.status!=='eligible').map(({state,start,status})=>({state,start,status}))}]));
  return {version:'0.1.0',scope:'retrospective_geographic_temporal_transportability',source_revision:'ff8f3b287029e3352ca5fc278d1184103e354455',rate_blob:'288572a3bc0da7ba707dfab310f3e66db19426e7',location_blob:'4533f7b5427b62aebc6ebcd34e0d0941e8324d35',target:'12-week mean absolute one-step persistence error, hospital admissions per 100000',partitions,metrics,test:held.map(({state,name,start,actual,estimate})=>({state,name,start,actual,estimate})),limitations:['Retrospectively revised snapshot; not real-time forecasts','Geographical state units, not hospital sites','Missing complete windows excluded; possible selection bias','Small held-out state count; descriptive only','No clinical validation or canonical task acceptance']};
}

module.exports={parseLocations,parseRates,buildEnvironment,partitionStates,conformal,analyse};
if(require.main===module){
  const fs=require('node:fs'),crypto=require('node:crypto');
  const [loc,rate,out]=process.argv.slice(2);
  const checked=(path,expected)=>{
    const bytes=fs.readFileSync(path);
    const git=crypto.createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');
    if(git!==expected)throw Error('source Git blob mismatch');
    return bytes.toString('utf8');
  };
  const result=analyse(checked(loc,'4533f7b5427b62aebc6ebcd34e0d0941e8324d35'),checked(rate,'288572a3bc0da7ba707dfab310f3e66db19426e7'));
  fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');
}
