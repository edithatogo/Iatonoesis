'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {compare}=require('./cql-runtime.cjs');
const {evaluateWithDiagnostics}=require('./cql-extended-runtime.cjs');

test('diagnostics preserve exact comparator results including negative and non-scalar cases',async()=>{
 const refs=[{id:'ok',expected:null},{id:'null_mismatch',expected:null},{id:'missing_node',expected:5},{id:'throw',expected:null},{id:'wrong_type',expected:0},{id:'false_mismatch',expected:false}];
 const expressions=new Map(refs.map(r=>[r.id,{type:r.id}]));
 function build(e){
   if(e.type==='missing_node')return null;
   return {execute:async()=>{
     if(e.type==='throw')throw new RangeError('private diagnostic text');
     return {ok:null,null_mismatch:true,wrong_type:{value:0},false_mismatch:0}[e.type];
   }};
 }
 const baseline=await compare(expressions,refs,e=>build(e).execute({}));
 const {diagnostics,...result}=await evaluateWithDiagnostics(expressions,refs,build,()=>({}));
 assert.deepEqual(result,baseline);
 assert.equal(result.passed,1);
 assert.deepEqual(diagnostics.map(x=>[x.id,x.phase,x.error_type]),[
   ['null_mismatch','returned',null],['missing_node','no_executable_node','TypeError'],
   ['throw','execute','RangeError'],['wrong_type','returned',null],['false_mismatch','returned',null]]);
 assert.deepEqual(diagnostics[1].elm,expressions.get('missing_node'));
 assert.doesNotMatch(JSON.stringify(diagnostics),/private diagnostic text/);
});

test('context and builder failures stay failed and membership still fails closed',async()=>{
 const expr={type:'Literal'},expressions=new Map([['a',expr]]),refs=[{id:'a',expected:null}];
 const ctx=await evaluateWithDiagnostics(expressions,refs,()=>{throw Error('unexpected')},()=>{throw Error('context')});
 assert.equal(ctx.passed,0);assert.equal(ctx.diagnostics[0].phase,'context');
 const built=await evaluateWithDiagnostics(expressions,refs,()=>{throw Error('builder')},()=>({}));
 assert.equal(built.passed,0);assert.equal(built.diagnostics[0].phase,'build');
 await assert.rejects(evaluateWithDiagnostics(new Map(),refs,()=>null,()=>({})),/membership/);
});
