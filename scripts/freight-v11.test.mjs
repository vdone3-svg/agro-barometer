import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {normalizeFreightRate,mergeRates,publicView} from '../netlify/functions/_freight_rates.mjs';
const example={source_name:'Example carrier',source_url:'https://example.org/quote',observed_date:'2026-10-20',origin_city:'Олександрія',destination_city:'Ізмаїл',distance_km:648,vehicle_type:'grain_truck',cargo_type:'пшениця',load_tonnes:25,payment_type:'bank',vat_status:'unknown',evidence_status:'unverified_listing',trip_price_uah:50000};
test('calculates tonne freight from trip',()=>{const x=normalizeFreightRate(example,'2026-10-25');assert.equal(x.price_per_tonne_uah,2000);assert.equal(x.price_per_tonne_km_uah,3.0864);assert.equal(x.validated_for_market_model,false)});
test('supports tonne price',()=>{const {trip_price_uah,...a}=example;const x=normalizeFreightRate({...a,price_per_tonne_uah:2200},'2026-10-25');assert.equal(x.price_per_tonne_uah,2200)});
test('rejects missing distance',()=>assert.throws(()=>normalizeFreightRate({...example,distance_km:null},'2026-10-25')));
test('rejects fake future quote',()=>assert.throws(()=>normalizeFreightRate({...example,observed_date:'2030-01-01'},'2026-10-25')));
test('rejects two price bases',()=>assert.throws(()=>normalizeFreightRate({...example,price_per_tonne_uah:12},'2026-10-25')));
test('rejects non-http URLs',()=>assert.throws(()=>normalizeFreightRate({...example,source_url:'javascript:alert(1)'},'2026-10-25')));
test('refuses overwrite with different rate same id',()=>{const a=normalizeFreightRate(example,'2026-10-25');assert.throws(()=>mergeRates([a],[{...a,price_per_tonne_uah:1900}]))});
test('deduplicates same record',()=>{const a=normalizeFreightRate(example,'2026-10-25');assert.equal(mergeRates([a],[a]).length,1)});
test('public view does not recommend based on unverified data',()=>{const a=normalizeFreightRate(example,'2026-10-25');assert.equal(publicView([a]).approved_for_automatic_pricing,0)});

test('rejects impossible calendar dates',()=>{
 for(const observed_date of ['2026-02-30','2026-13-01','2026-00-10','2026-04-31'])
  assert.throws(()=>normalizeFreightRate({...example,observed_date},'2026-10-25'), /invalid observed_date/);
});
test('accepts real leap day only in leap year',()=>{
 assert.equal(normalizeFreightRate({...example,observed_date:'2024-02-29'},'2026-10-25').observed_date,'2024-02-29');
 assert.throws(()=>normalizeFreightRate({...example,observed_date:'2025-02-29'},'2026-10-25'));
});
