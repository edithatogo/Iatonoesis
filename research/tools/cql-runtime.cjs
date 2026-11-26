'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function extract(elm) {
  const defs=elm.library?.statements?.def;
  if (!Array.isArray(defs) || !elm.library?.identifier?.id) throw new Error('invalid ELM library');
  const result=new Map();
  for(const suite of defs){
    if(suite.name==='Patient' && suite.expression?.type==='SingletonFrom') continue;
    if(suite.expression?.type!=='Tuple' || !Array.isArray(suite.expression.element)) throw new Error('unexpected ELM suite');
    for(const item of suite.expression.element){
      if(result.has(item.name)) throw new Error('duplicate ELM case');
      const fields=new Map(item.value.element.map(e=>[e.name,e.value]));
      if(!fields.has('expression') || fields.has('skipped')) throw new Error('unavailable ELM case');
      result.set(item.name,fields.get('expression'));
    }
  }
  return result;
}

async function compare(expressions,refs,execute){
  if(new Set(refs.map(r=>r.id)).size!==refs.length || expressions.size!==refs.length || refs.some(r=>!expressions.has(r.id))) throw new Error('case membership mismatch');
  const scalar=x=>x===null||typeof x==='boolean'||Number.isSafeInteger(x);
  const cases=[];
  for(const r of refs){
    if(!scalar(r.expected)) throw new Error('invalid reference type');
    try{
      const actual=await execute(expressions.get(r.id));
      cases.push({id:r.id,expected:r.expected,actual:scalar(actual)?actual:null,match:scalar(actual)&&actual===r.expected,status:scalar(actual)?'executed':'invalid_type'});
    }catch(e){cases.push({id:r.id,expected:r.expected,actual:null,match:false,status:'failed'});}
  }
  return {total:cases.length,passed:cases.filter(c=>c.match).length,cases};
}

// Three-valued truth tables independent of the CQL compiler and executor.
const VALUES=[true,false,null];
const AND=[[true,false,null],[false,false,false],[null,false,null]];
const OR=[[true,true,true],[true,false,null],[true,null,null]];
const and=(a,b)=>AND[VALUES.indexOf(a)][VALUES.indexOf(b)];
const or=(a,b)=>OR[VALUES.indexOf(a)][VALUES.indexOf(b)];
const not=a=>[false,true,null][VALUES.indexOf(a)];
const lit=x=>x===null?'(null as Boolean)':String(x);

function mutationFixture(){
  const families=[
    ['logic',[
      ['base',(a,b,c)=>'('+a+' and '+b+') or '+c,(a,b,c)=>or(and(a,b),c)],
      ['precedence',(a,b,c)=>a+' and ('+b+' or '+c+')',(a,b,c)=>and(a,or(b,c))],
      ['negated',(a,b,c)=>'(not ('+a+' and '+b+')) or '+c,(a,b,c)=>or(not(and(a,b)),c)],
      ['null_default',(a,b,c)=>'Coalesce(('+a+' and '+b+'), false) or '+c,(a,b,c)=>or(and(a,b)??false,c)]
    ]],
    ['conditional',[
      ['base',(a,b,c)=>'if '+a+' then '+b+' else '+c,(a,b,c)=>a===true?b:c],
      ['swap',(a,b,c)=>'if '+a+' then '+c+' else '+b,(a,b,c)=>a===true?c:b],
      ['null_true',(a,b,c)=>'if Coalesce('+a+', true) then '+b+' else '+c,(a,b,c)=>(a??true)?b:c],
      ['explicit_null',(a,b,c)=>'if ('+a+' is null) then (null as Boolean) else (if '+a+' then '+b+' else '+c+')',(a,b,c)=>a===null?null:a?b:c]
    ]]
  ];
  const groups=[],refs=[],suites=[];
  for(const [family,variants] of families){
    let i=0;const cases=[],lines=[];
    for(const a of VALUES)for(const b of VALUES)for(const c of VALUES){
      const ids={};
      for(const [name,expression,oracle] of variants){
        const id=family+'_'+i+'_'+name;ids[name]=id;
        refs.push({id,expected:oracle(a,b,c)});
        lines.push('  "'+id+'": Tuple{ expression: '+expression(lit(a),lit(b),lit(c))+' }');
      }
      cases.push(ids);i++;
    }
    groups.push({family,cases,variants:variants.map(v=>v[0])});
    suites.push('define "'+family+'": Tuple{\n'+lines.join(',\n')+'\n}');
  }
  return {cql:"library IatonoesisMutationCases version '1.0.0'\nusing QUICK version '3.3.0'\ncontext Patient\n\n"+suites.join('\n\n')+'\n',refs,groups};
}

function mutationMetrics(groups,results){
  const actual=new Map(results.cases.map(c=>[c.id,c.actual]));
  return groups.map(g=>{
    const sigs=[];let equivalent=0;
    for(const v of g.variants.filter(v=>v!=='base')){
      const s=g.cases.map((c,i)=>actual.get(c.base)!==actual.get(c[v])?i:-1).filter(i=>i>=0);
      if(!s.length) equivalent++; else sigs.push(JSON.stringify(s));
    }
    return {family:g.family,domain:g.cases.length,mutants:g.variants.length-1,equivalent,distinct_non_equivalent:new Set(sigs).size};
  });
}

async function replay(upstream,compiled,fixtures,mutationRef){
  const load=p=>JSON.parse(fs.readFileSync(p,'utf8'));
  const manifest=load(path.join(fixtures,'manifest.json'));
  if(manifest.upstream_revision!=='e87e3fa8a3802c69a760b2583d2306d7c66d9899') throw new Error('unexpected fixture source');
  const {PatientContext}=require(path.join(upstream,'lib/runtime/context'));
  require(path.join(upstream,'lib/elm/expressions'));
  const {build}=require(path.join(upstream,'lib/elm/builder'));
  const {Library}=require(path.join(upstream,'lib/elm/library'));
  const receipts=[];
  async function execute(name,refs){
    const bytes=fs.readFileSync(path.join(compiled,name+'.json'));
    const elm=JSON.parse(bytes);const library=new Library(elm);
    const result=await compare(extract(elm),refs,async expression=>{
      const ctx=new PatientContext(library);ctx.getExecutionDateTime().timezoneOffset=0;
      return await build(expression).execute(ctx);
    });
    return {suite:name,elm_sha256:sha(bytes),...result};
  }
  for(const suite of manifest.suites){
    const raw=fs.readFileSync(path.join(fixtures,suite.dataset_file));
    if(sha(raw)!==suite.dataset_sha256) throw new Error('frozen reference digest mismatch');
    const refs=JSON.parse(raw);
    if(refs.length!==suite.case_count||JSON.stringify(refs.map(r=>r.id))!==JSON.stringify(suite.case_ids)) throw new Error('frozen case mismatch');
    receipts.push(await execute(suite.suite,refs));
  }
  const bytes=fs.readFileSync(mutationRef),frozen=JSON.parse(bytes);
  const authored=await execute('IatonoesisMutationCases',frozen.refs);
  authored.reference_sha256=sha(bytes);authored.mutation_metrics=mutationMetrics(frozen.groups,authored);
  receipts.push(authored);
  return {scope:'upstream_scalar_and_authored_synthetic_conformance_only',runtime:'cql-execution 3.3.2',runtime_revision:'1991335e7ad490a8db88a05dd7f03dc3eecbda6d',translator:'org.cqframework:cql-to-elm-cli:4.2.0',node:process.version,suites:receipts,total:receipts.reduce((n,x)=>n+x.total,0),passed:receipts.reduce((n,x)=>n+x.passed,0),limitations:['not full CQL specification certification','published upstream labels exposed','new mutation oracle separately specified, not independently human adjudicated','Maven transitive hashes not fully locked; no patient data']};
}

async function main(){
  const [mode,...args]=process.argv.slice(2);
  if(mode==='generate'){
    const [cql,ref]=args;const fixture=mutationFixture();fs.writeFileSync(cql,fixture.cql);fs.writeFileSync(ref,JSON.stringify({refs:fixture.refs,groups:fixture.groups},null,2)+'\n');return;
  }
  if(mode!=='replay'||args.length!==5) throw new Error('invalid arguments');
  const [upstream,compiled,fixtures,ref,out]=args;
  const result=await replay(upstream,compiled,fixtures,ref);fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');
  if(result.passed!==result.total) process.exitCode=1;
}
module.exports={extract,compare,mutationFixture,mutationMetrics};
if(require.main===module) main().catch(e=>{console.error(e.message);process.exitCode=1;});
