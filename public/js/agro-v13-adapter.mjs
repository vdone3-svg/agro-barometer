/** Public-source adapter. Missing evidence is kept missing; NEVER inferred. */
import {destination} from './agro-decision-core-v9.mjs';
const map=[['пшениця','пшениця'],['кукурудза','кукурудза'],['соняшник','соняшник'],['ячмінь','ячмінь'],['соя','соя'],['ріпак','ріпак']];
export function identifyCrop(product){const p=String(product||'').trim().toLocaleLowerCase('uk-UA');return map.find(([prefix])=>p.startsWith(prefix))?.[1]||null;}
export function adaptPublicOffer(o){
 const crop=identifyCrop(o?.product),city=destination(o);
 if(o?.kind!=='grain'||!crop)return null;
 return {
  kind:'grain',crop,company:o.company||'Невідомий покупець',original_product:o.product||'',
  source_url:o.source_url||null,quote_date:o.quote_date||null,
  destination_city:city||null,destination_region:o.region||null,
  destination_accuracy:'city',destination_location_id:null,
  grade_or_spec:null,quality_basis_id:null,quality_conditions_verified:false,
  verification:'unverified',vat_rate:null,tax_treatment_verified:false,seller_vat_credit_on_freight_confirmed:false,freshness:o.freshness==='archival_unverified'?'archival_unverified':'unverified',
  price_uah_per_tonne:null, // Source parser does NOT establish units of price: do not copy raw `price` here.
  observed_quote_value:Number.isFinite(o.price)?o.price:null,observed_quote_currency:o.currency||null,
  observed_quote_price_unit:'unknown',vat_status:'unknown',delivery_mode:'unknown',
  payment_terms_verified:false,payment_terms_id:null,extra_seller_costs_confirmed:false,
  extra_seller_costs_uah_per_tonne:null,pickup_seller_freight_cost_confirmed_zero:false
 };
}
export function freightQualityReport(records=[]){
 const total=records.length;
 const counts={total,approved:0,with_date:0,with_vat:0,with_source:0,exact_destination:0};
 for(const r of records){if(r?.validated_for_market_model===true)counts.approved++;if(/^20\d\d-\d\d-\d\d$/.test(r?.observed_date||''))counts.with_date++;if(['included','excluded'].includes(r?.vat_status))counts.with_vat++;if(/^https?:\/\//.test(r?.source_url||''))counts.with_source++;if(r?.destination_location_id&&r?.destination_accuracy==='exact')counts.exact_destination++}
 return counts;
}
export function aggregateReasons(review){const counts=new Map();for(const r of review)for(const reason of new Set(r.reasons||[]))counts.set(reason,(counts.get(reason)||0)+1);return [...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'uk'));}
