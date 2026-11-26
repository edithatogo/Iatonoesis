'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {extract,compare,mutationMetrics}=require('./cql-runtime.cjs');
// Observe the real builder/executor without changing the reference or comparator.
async function evaluateWithDiagnostics(expressions,refs,build,makeContext){
 const traces=[];
 const result=await compare(expressions,refs,async expression=>{
   const trace={phase:'context',error_type:null};traces.push(trace);
   try{
     const ctx=makeContext();trace.phase='build';
     const instance=build(expression);
     if(instance==null||typeof instance.execute!=='function'){
       trace.phase='no_executable_node';throw new TypeError('no executable ELM node');
     }
     trace.phase='execute';const actual=await instance.execute(ctx);
     trace.phase='returned';return actual;
   }catch(e){
     trace.error_type=['Error','TypeError','RangeError','ReferenceError','SyntaxError'].includes(e?.name)?e.name:'OtherError';
     throw e;
   }
 });
 const diagnostics=result.cases.flatMap((row,i)=>row.match?[]:[{id:row.id,...traces[i],elm:expressions.get(row.id)}]);
 return {...result,diagnostics};
}

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
 const result=await evaluateWithDiagnostics(extract(elm),[...external,...authored],build,()=>{
   const ctx=new PatientContext(library);ctx.getExecutionDateTime().timezoneOffset=0;return ctx;
 });
 const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
 const receipt={...result,external_total:external.length,external_passed:result.cases.slice(0,external.length).filter(x=>x.match).length,
 authored_total:authored.length,authored_passed:result.cases.slice(external.length).filter(x=>x.match).length,
 statuses:frozen.statuses,freeze_sha256:sha(fs.readFileSync(freezePath)),elm_sha256:sha(bytes),
 mutation_metrics:result.passed===result.total?mutationMetrics(frozen.groups,result):null};
 fs.writeFileSync(out,JSON.stringify(receipt,null,2)+'\n');
 if(result.passed!==result.total)process.exitCode=1;
}
module.exports={evaluateWithDiagnostics};
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=1;});
