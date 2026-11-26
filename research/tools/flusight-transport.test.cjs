const test=require('node:test');
const assert=require('node:assert/strict');
const {parseLocations,parseRates,buildEnvironment,partitionStates,conformal,analyse}=require('./flusight-transport.cjs');

test('state partition is disjoint and ignores non-state rows',()=>{
  const locations=parseLocations('abbreviation,location,location_name,population\nAL,01,Alabama,10\nDC,11,District of Columbia,10\nAK,02,Alaska,10\nUS,US,US,20\n');
  assert.deepEqual(locations.map(x=>x.id),['01','02']);
  const p=partitionStates(Array.from({length:50},(_,i)=>({id:String(i).padStart(2,'0')})));
  assert.equal(p.development.length,30);assert.equal(p.calibration.length,10);assert.equal(p.test.length,10);
  assert.equal(new Set(Object.values(p).flat().map(x=>x.id)).size,50);
});

test('one-step persistence and pre-target features are separated',()=>{
  const state={id:'01',name:'Alabama'};
  const header='"date","location","location_name","value","weekly_rate"\n';
  const start='2024-10-05';
  const date=i=>new Date(Date.parse(start)+i*604800000).toISOString().slice(0,10);
  const rows=Array.from({length:20},(_,i)=>'"'+date(i)+'","01","Alabama",'+i+','+i).join('\n');
  const a=buildEnvironment(parseRates(header+rows,[state]),state,start);
  assert.equal(a.status,'eligible');assert.equal(a.actual,1);
  assert.deepEqual(a.features,[3.5,Math.sqrt(5.25),7,1]);
  const changed=rows.replace(/,19,19$/,',99,99');
  const b=buildEnvironment(parseRates(header+changed,[state]),state,start);
  assert.deepEqual(a.features,b.features);assert.notEqual(a.actual,b.actual);
  const missing=buildEnvironment(parseRates(header+rows.replace(/,19,19$/,',NA,NA'),[state]),state,start);
  assert.equal(missing.status,'missing_target');
});

test('duplicate rates and mismatched location names fail closed',()=>{
  const st=[{id:'01',name:'Alabama'}], h='"date","location","location_name","value","weekly_rate"\n';
  const line='"2024-10-05","01","Alabama",2,3';
  assert.throws(()=>parseRates(h+line+'\n'+line,st),/duplicate/);
  assert.throws(()=>parseRates(h+line.replace('Alabama','other'),st),/name/);
  assert.throws(()=>parseLocations('abbreviation,location,location_name,population\nAL,01,Alabama,10\nAL,01,Alabama,10'),/duplicate/);
});

test('finite conformal radius uses cluster count not row count',()=>{
  assert.equal(conformal([1,2,3,4,5,6,7,8]),null);
  assert.equal(conformal([1,2,3,4,5,6,7,8,9,10]),10);
});
