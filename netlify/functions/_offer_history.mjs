import { offerProblem, quoteFreshness } from './_offer_quality.mjs';
import { createHash } from 'node:crypto';

// The quote's commercial identity deliberately excludes its price and observation time.
export function offerIdentity(o) {
 const parts=['kind','company','product','formula','currency','region','point','source_url'].map(k=>String(o?.[k]??'').trim().toLocaleLowerCase('uk-UA'));
 return createHash('sha256').update(JSON.stringify(parts)).digest('hex').slice(0,24);
}
export function validOffer(o){
 return o && ['grain','fertilizer'].includes(o.kind) && o.verification==='unverified' &&
 typeof o.company==='string' && o.company.trim() && typeof o.product==='string' && o.product.trim() &&
 Number.isFinite(o.price) && o.price>0 && ['USD','UAH','EUR'].includes(o.currency) &&
 /^20\d{2}-\d{2}-\d{2}$/.test(o.quote_date||'') && o.quote_date<=new Date().toISOString().slice(0,10) &&
 (o.quality==='partial'||o.quality==='complete');
}
export function updateHistory(previous, sources, observedAt) {
 const old=previous && Array.isArray(previous.observations)?previous.observations:[];
 const observations=old.slice();
 const existing=new Set(old.map(x=>x.fingerprint));
 let added=0, repeated=0;
 for(const src of sources||[]){
  // Never turn a failed source's reused prior data into a new observation.
  if(src.status!=='ok'||!['grain','fertilizer'].includes(src.id))continue;
  for(const raw of src.data?.offers||[]){
   const o={...raw,kind:src.id};
   if(!validOffer(o) || offerProblem(o))continue;
   const identity=offerIdentity(o);
   // Repeated daily snapshots of the same dated offer are not a new market price.
   const fingerprint=createHash('sha256').update(JSON.stringify([identity,o.quote_date,o.price])).digest('hex').slice(0,32);
   if(existing.has(fingerprint)){repeated++;continue;}
   observations.push({fingerprint,identity,first_seen_at:observedAt,quote_date:o.quote_date,
     kind:o.kind,company:o.company,product:o.product,formula:o.formula??null,price:o.price,
     currency:o.currency,region:o.region??null,point:o.point??null,source_url:o.source_url,
     vat:o.vat??'unknown',basis:o.basis??'unknown',verification:'unverified',quality:o.quality,freshness:quoteFreshness(o)});
   existing.add(fingerprint);added++;
  }
 }
 // Keep a bounded archive; unlike a transactional database, this JSON snapshot is not designed for simultaneous writers.
 observations.sort((a,b)=>(a.first_seen_at||'').localeCompare(b.first_seen_at||''));
 const retained=observations.slice(-3000);
 const ordered=retained.slice().sort((a,b)=>a.first_seen_at.localeCompare(b.first_seen_at));
 const byIdentity=new Map();
 for(const o of ordered){if(!byIdentity.has(o.identity))byIdentity.set(o.identity,[]);byIdentity.get(o.identity).push(o);}
 const changes=[];
 for(const entries of byIdentity.values()){
  for(let i=1;i<entries.length;i++){
   const from=entries[i-1],to=entries[i];
   if(from.price!==to.price)changes.push({identity:to.identity,kind:to.kind,company:to.company,product:to.product,
     previous_price:from.price,new_price:to.price,currency:to.currency,quote_date:to.quote_date,
     previous_quote_date:from.quote_date,observed_at:to.first_seen_at,source_url:to.source_url,
     verification:'unverified',note:'Unverified listing change, not a validated comparable price'});
  }
 }
 changes.sort((a,b)=>b.observed_at.localeCompare(a.observed_at));
 return {schema_version:1,collector:'offer_history_v1',updated_at:observedAt,status:'ok',total_observations:retained.length,
   total_distinct_offers:byIdentity.size,added_this_run:added,repeated_this_run:repeated,
   note:'UNVERIFIED candidate listing archive. Changes reflect source listings, not proven market price changes. No barometer effect.',
   observations:retained,changes:changes.slice(0,150)};
}
export async function saveOfferHistory(sources,observedAt=new Date().toISOString()){
 const { getStore } = await import('@netlify/blobs');
 const store=getStore({name:'agro-public-market',consistency:'strong'});
 const previous=await store.get('unverified-offer-history-v1',{type:'json'});
 const next=updateHistory(previous,sources,observedAt);
 await store.setJSON('unverified-offer-history-v1',next);
 return {status:'ok',added:next.added_this_run,total:next.total_observations,changes:next.changes.length};
}
