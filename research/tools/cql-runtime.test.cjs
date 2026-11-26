const test = require('node:test');
const assert = require('node:assert/strict');
const {extract,compare,mutationFixture} = require('./cql-runtime.cjs');

test('only expressions from complete named tuple cases are extracted',()=>{
  const elm={library:{identifier:{id:'Fixture'},statements:{def:[
    {name:'Patient',expression:{type:'SingletonFrom'}},
    {name:'Cases',expression:{type:'Tuple',element:[{name:'a',value:{element:[{name:'expression',value:{type:'Literal'}},{name:'output',value:{type:'Null'}}]}}]}}
  ]}}};
  const result=extract(elm);assert.deepEqual([...result.keys()],['a']);assert.deepEqual(result.get('a'),{type:'Literal'});
  elm.library.statements.def[1].expression.element.push(elm.library.statements.def[1].expression.element[0]);
  assert.throws(()=>extract(elm),/duplicate/);
});

test('strict scalar equality and exact membership; null is not false or zero',async()=>{
  const refs=[{id:'a',expected:null},{id:'b',expected:false},{id:'c',expected:0}];
  const expressions=new Map([['a',null],['b',false],['c',0]]);
  const result=await compare(expressions,refs,async x=>x);
  assert.equal(result.passed,3);
  const bad=await compare(expressions,refs,async x=>x===null?false:x);
  assert.equal(bad.passed,2);assert.equal(bad.cases[0].match,false);
  await assert.rejects(compare(new Map([['a',null]]),refs,async x=>x),/membership/);
});

test('three-valued oracle covers new families without embedding expected results into CQL',()=>{
  const {cql,refs,groups}=mutationFixture();
  assert.equal(refs.length,216);assert.equal(new Set(refs.map(r=>r.id)).size,216);
  assert.equal(groups.length,2);assert.equal(groups[0].cases.length,27);
  assert.match(cql,/library IatonoesisMutationCases/);assert.doesNotMatch(cql,/output:/);
  const ref=Object.fromEntries(refs.map(r=>[r.id,r.expected]));
  assert.equal(ref['logic_0_base'],true); // true and true or true
  assert.equal(ref['logic_26_base'],null);
  assert.equal(ref['conditional_18_base'],true); // null condition, else true
  assert.equal(ref['conditional_19_base'],false);
  assert.equal(ref['conditional_18_explicit_null'],null);
});
