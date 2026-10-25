import test from 'node:test';
import assert from 'node:assert/strict';
import {evaluateV13,eligibleFreight,taxBasis,sourceIdentity} from '../public/js/agro-economics-core-v13.mjs';
const base={kind:'grain',crop:'кукурудза',grade_or_spec:'стандарт А',quality_basis_id:'spec-A',quality_conditions_verified:true,verification:'verified',freshness:'current',vat_status:'included',destination_city:'Одеса',destination_region:'Одеська область',destination_accuracy:'exact',destination_location_id:'terminal-A',price_uah_per_tonne:12000,delivery_mode:'seller_delivery',payment_terms_verified:true,payment_terms_id:'7days',extra_seller_costs_confirmed:true,extra_seller_costs_uah_per_tonne:0,tax_treatment_verified:true,seller_vat_credit_on_freight_confirmed:true,vat_rate:0.2};
const freight={validated_for_market_model:true,evidence_status:'verified_document',vehicle_type:'grain_truck',origin_city:'Олександрія',destination_city:'Одеса',destination_region:'Одеська область',destination_location_id:'terminal-A',vat_status:'included',cargo_type:'кукурудза',load_tonnes:25,price_per_tonne_uah:1200,vat_rate:0.2,rate_includes_waiting:true,observed_date:'2026-10-25',source_url:'https://a.example/1'};
const run=(o=[base],r=[freight],opts={})=>evaluateV13(o,r,{today:'2026-10-25',vat_rate:0.2,...opts});
test('blank freight fails closed',()=>{assert.equal(run([base],[]).ranked.length,0)});
test('one documented quote not enough',()=>{assert.equal(run().ranked.length,0)});
test('two independent sources normalize gross and net VAT',()=>{
 const out=run([base],[freight,{...freight,source_url:'https://b.example/2',price_per_tonne_uah:1400}]);
 assert.equal(out.ranked[0].freight_gross_uah_per_tonne,1300);
 assert.equal(out.ranked[0].net_revenue_uah_per_tonne,8916.67);
 assert.equal(out.ranked[0].gross_cash_before_other_costs_uah_per_tonne,10700);
});
test('many pages of same marketplace are not independent',()=>{assert.equal(run([base],[freight,{...freight,source_url:'https://a.example/2'}]).ranked.length,0)});
test('unapproved or undocumented rates are rejected',()=>{assert.equal(run([base],[freight,{...freight,source_url:'https://b.example/2',validated_for_market_model:false}]).ranked.length,0)});
test('older than 14 days are rejected',()=>{assert.equal(run([base],[freight,{...freight,source_url:'https://b.example/2',observed_date:'2026-09-01'}]).ranked.length,0)});
test('different crop, direction, terminal, loading size are rejected',()=>{
 for(const change of [{cargo_type:'пшениця'},{origin_city:'Одеса'},{destination_location_id:'terminal-B'},{load_tonnes:30}]){
  const out=run([base],[freight,{...freight,...change,source_url:'https://b.example/2'}]);assert.equal(out.ranked.length,0,JSON.stringify(change));
 }
});
test('city-only geocoding never certifies a particular terminal quote',()=>{assert.equal(run([{...base,destination_accuracy:'city'}],[freight,{...freight,source_url:'https://b.example'}]).ranked.length,0)});
test('self pickup works only when contractual terms and price VAT verified',()=>{
 const p={...base,delivery_mode:'pickup',price_uah_per_tonne:10800,pickup_seller_freight_cost_confirmed_zero:true};
 const x=run([p],[]);assert.equal(x.ranked.length,1);assert.equal(x.ranked[0].net_revenue_uah_per_tonne,9000);
 assert.equal(run([{...p,pickup_seller_freight_cost_confirmed_zero:false}],[]).ranked.length,0);
});
test('different grain quality and payment arrangements not mixed',()=>{
 const p={...base,delivery_mode:'pickup',pickup_seller_freight_cost_confirmed_zero:true};
 const x=run([p,{...p,grade_or_spec:'стандарт Б',price_uah_per_tonne:14000},{...p,payment_terms_id:'prepay',price_uah_per_tonne:15000}],[]);
 assert.equal(x.ranked.length,3);assert.equal(new Set(x.ranked.map(a=>a.comparison_group)).size,3);
});
test('unverified offer, missing VAT rate, unconfirmed extra costs fail closed',()=>{
 const p={...base,delivery_mode:'pickup',pickup_seller_freight_cost_confirmed_zero:true};
 assert.equal(run([{...p,verification:'unverified'}],[]).ranked.length,0);
 assert.equal(run([p],[],{vat_rate:null}).ranked.length,0);
 assert.equal(run([{...p,extra_seller_costs_confirmed:false}],[]).ranked.length,0);
});
test('archival offers are separated',()=>{assert.equal(run([{...base,freshness:'archival_unverified'}]).archived.length,1)});
test('VAT parsing never silently assumes a tax rate',()=>{assert.equal(taxBasis({amount:1200,vat_status:'included',vat_rate:null}).ok,false);assert.equal(taxBasis({amount:1200,vat_status:'included',vat_rate:0.2}).net,1000)});
test('source identity by organization, not individual quote URL',()=>{assert.equal(sourceIdentity({...freight,source_organization_id:'Carrier ABC'}),'carrier abc')});
test('waiting terms must be confirmed',()=>{assert.equal(eligibleFreight({...freight,rate_includes_waiting:false},base),false)});

test('wildly contradictory quotes do not create a market price',()=>{const r=run([base],[freight,{...freight,source_url:'https://b.example/2',price_per_tonne_uah:6000}]);assert.equal(r.ranked.length,0);assert.ok(r.review[0].reasons.some(x=>x.includes('розходяться')))});

test('tax credit is never assumed merely because farm is a VAT payer',()=>{const changed={...base,seller_vat_credit_on_freight_confirmed:false};assert.equal(run([changed],[freight,{...freight,source_url:'https://b.example/2'}]).ranked.length,0)});
test('freight with unspecified VAT rate is not comparable',()=>{assert.equal(run([base],[freight,{...freight,source_url:'https://b.example/2',vat_rate:undefined}]).ranked.length,0)});
test('missing verified payment identifier is not ranked',()=>{const p={...base,delivery_mode:'pickup',pickup_seller_freight_cost_confirmed_zero:true,payment_terms_id:null};assert.equal(run([p],[]).ranked.length,0)});
