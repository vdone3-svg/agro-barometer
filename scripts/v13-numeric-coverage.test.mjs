import test from 'node:test';
import assert from 'node:assert/strict';
import {summarizeCoverage,CULTURES} from '../netlify/functions/_source_coverage_v13.mjs';
const now=new Date('2026-10-25T12:00:00Z');
test('empty data does not invent grades',()=>{
 const r=summarizeCoverage({now});assert.equal(r.ready_for_trade_decision,false);assert.equal(r.crops.length,6);
 assert.ok(r.crops.every(c=>c.analysis_status==='context_only'&&c.eu_prices.records===0&&c.usda.records===0));
});
test('preserve six crop names and no hidden extra',()=>assert.deepEqual(CULTURES,['wheat','corn','sunflower','barley','soy','rapeseed']));
test('EU dated prices are separated from USDA market-year balances',()=>{
 const r=summarizeCoverage({now,usda:{records:[{crop:'corn',market_year:2026,scope:'world',attribute:'Production',unit:'1000 MT',value:100}]},eu:{rows:[{crop:'corn',period_start:'2026-10-20',price_eur_per_tonne:200,member_state:'FR'},{crop:'corn',period_start:'2026-13-20',price_eur_per_tonne:200,member_state:'FR'}]}});
 const c=r.crops.find(c=>c.crop==='corn');assert.equal(c.usda.records,1);assert.equal(c.eu_prices.records,1);assert.equal(c.eu_prices.latest_age_days,5);
 assert.equal(r.ready_for_trade_decision,false);
});
test('bad, negative or mismatched records are not counted',()=>{
 const r=summarizeCoverage({now,usda:{records:[{crop:'wheat',market_year:'junk',scope:'world',attribute:'A',unit:'U',value:5},{crop:'wheat',market_year:2026,scope:'world',attribute:'A',unit:'U',value:-1}]},eu:{rows:[{crop:'soy',period_start:'2026-02-30',price_eur_per_tonne:100},{crop:'soy',period_start:'2026-10-21',price_eur_per_tonne:-2}]}});
 assert.equal(r.crops.find(c=>c.crop==='wheat').usda.records,0);
 assert.equal(r.crops.find(c=>c.crop==='soy').eu_prices.records,0);
});
test('source health shown even without observations',()=>{
 const r=summarizeCoverage({now,usdaHealth:{status:'not_configured'},euHealth:{status:'error',last_success:'2026-10-01T00:00:00Z'}});
 assert.equal(r.sources.usda_psd.status,'not_configured'); assert.equal(r.sources.eu_dg_agri.status,'error');
});
