import test from 'node:test';
import assert from 'node:assert/strict';
import {identifyCrops,normalizePSD,collectPSD,requestPSD} from '../netlify/functions/_usda_psd_v13.mjs';
test('catalog discovers exact commodities, excludes oils',()=>{
 const c=identifyCrops([{commodityCode:'0440000',commodityName:'Corn'},{commodityCode:'0420000',commodityName:'Wheat'},{commodityCode:'0001000',commodityName:'Sunflower Oil'}]);
 assert.equal(c.corn.code,'0440000');assert.equal(c.wheat.code,'0420000');assert.equal(c.sunflower,undefined);
});
test('empty and missing values are rejected, real zero production allowed',()=>{
 const o=normalizePSD([{marketYear:2026,value:0,attributeDescription:'Production',unitDescription:'1000 MT'},{marketYear:2026,value:'',attributeDescription:'Exports',unitDescription:'1000 MT'},{marketYear:2024,value:4,attributeDescription:'Imports',unitDescription:'1000 MT'}],{crop:'corn',marketYear:2026,scope:'world',sourceUrl:'https://api.fas.usda.gov'});
 assert.equal(o.records.length,1);assert.equal(o.records[0].value,0);assert.equal(o.invalid.value,1);assert.equal(o.invalid.year,1);
});
test('does not pretend unlabeled units are metric tonnes',()=>{const o=normalizePSD([{marketYear:2026,value:500,attributeDescription:'Production'}],{crop:'corn',marketYear:2026,scope:'world'});assert.equal(o.records.length,0);});
test('rejects missing key without network access',async()=>{await assert.rejects(requestPSD('https://api.fas.usda.gov/api/psd/commodities',{key:''}),/missing/)});
test('mocked USDA integration preserves scoped records',async()=>{
 const mock=async url=>({ok:true,headers:{get:()=>null},json:async()=>url.endsWith('/commodities')?[{commodityCode:'0440000',commodityName:'Corn'}]:url.endsWith('/countries')?[{countryCode:'UP',countryName:'Ukraine'}]:[{marketYear:Number(url.split('/').at(-1)),value:205,attributeDescription:'Production',unitDescription:'1000 MT',countryCode:url.includes('/world/')?'WORLD':'UP',countryName:url.includes('/world/')?'World':'Ukraine',commodityCode:'0440000'}]});
 const result=await collectPSD({key:'test-key-for-mocks',fetchImpl:mock,year:2026});
 assert.equal(result.records_total,4);assert.equal(result.issues.length,0);assert.equal(result.decision_grade,false);
});

test('USDA rejects unrelated crop observations rather than misclassifying them',()=>{
 const rows=[{marketYear:2026,value:500,attributeDescription:'Production',unitDescription:'1000 MT',commodityCode:'0420000',countryCode:'WORLD'}];
 const result=normalizePSD(rows,{crop:'corn',marketYear:2026,scope:'world',expectedCommodityCode:'0440000'});
 assert.equal(result.records.length,0); assert.equal(result.invalid.commodity,1);
});
test('USDA rejects world rows in Ukraine series and Ukraine rows in world series',()=>{
 const common={marketYear:2026,value:500,attributeDescription:'Production',unitDescription:'1000 MT',commodityCode:'0440000'};
 const ua=normalizePSD([{...common,countryCode:'WORLD'}],{crop:'corn',marketYear:2026,scope:'ukraine'});
 const world=normalizePSD([{...common,countryCode:'UP'}],{crop:'corn',marketYear:2026,scope:'world'});
 assert.equal(ua.records.length,0);assert.equal(world.records.length,0);
 assert.equal(ua.invalid.country,1);assert.equal(world.invalid.country,1);
});
