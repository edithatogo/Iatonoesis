'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {extract,compare,mutationMetrics}=require('./cql-runtime.cjs');
async function main(){
 const [upstream,elmPath,freezePath,out]=process.argv.slice(2);
 const frozen=JSON.parse(fs.readFileSync(freezePath,'utf8'));
 const external=frozen.all_rows.filter(x=>x.status==='eligible').map(x=>({id:x.elm_id,expected:x.expected}));
 const authored=frozen.mutations.map(x=>({id:x.id,expected:x.expected}));
 const bytes=fs.readFileSync(elmPath),elm=JSON.parse(bytes);
 const {PatientContext}=require(path.join(upstream,'lib/runtime/context'));
 require(path.join(upstream,'lib/elm/expressions'));
 const {build}=require(path.join(upstream,'lib/elm/builder'));
 const {Library}=require(path.join(upstream,'lib/elm/library'));
 const library=new Library(elm);
 const result=await compare(extract(elm),[...external,...authored],async expression=>{
   const ctx=new PatientContext(library);ctx.getExecutionDateTime().timezoneOffset=0;
   return await build(expression).execute(ctx);
 });
 const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
 const receipt={...result,external_total:external.length,external_passed:result.cases.slice(0,external.length).filter(x=>x.match).length,
 authored_total:authored.length,authored_passed:result.cases.slice(external.length).filter(x=>x.match).length,
 statuses:frozen.statuses,freeze_sha256:sha(fs.readFileSync(freezePath)),elm_sha256:sha(bytes),
 mutation_metrics:result.passed===result.total?mutationMetrics(frozen.groups,result):null};
 fs.writeFileSync(out,JSON.stringify(receipt,null,2)+'\n');
 if(result.passed!==result.total)process.exitCode=1;
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
