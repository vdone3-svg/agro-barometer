import { quoteFreshness, filterSourceOffers } from './_offer_quality.mjs';
import { cropCoverage } from './_crop_coverage.mjs';
import { saveOfferHistory } from './_offer_history.mjs';
import { extractOfferCandidates } from './_offers.mjs';
import { getStore } from '@netlify/blobs';

export const SOURCES = Object.freeze([
 {id:'grain',url:'https://e-zerno.com/trader-prices',title:'E-ZERNO — зернові'},
 {id:'fertilizer',url:'https://e-zerno.com/fertilizer-prices',title:'E-ZERNO — добрива'},
 {id:'fuel',url:'https://enkorr.ua/',title:'Enkorr — гуртові індикативи'}
]);
const timeoutMs=9000;
const nowIso=()=>new Date().toISOString();
const clean=s=>String(s).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,' ').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;|&#160;/gi,' ').replace(/&amp;/gi,'&').replace(/\s+/g,' ').trim();
const num=s=>Number(String(s).replace(/[\s\u00a0\u202f]/g,'').replace(',','.'));
const dateOk=s=>/^\d{2}\.\d{2}\.20\d{2}$/.test(s);
const dateToISO=s=>{const [d,m,y]=s.split('.');return `${y}-${m}-${d}`;};
const dateIsNotFuture=s=>dateOk(s)&&dateToISO(s)<=new Date().toISOString().slice(0,10);
const stamp=html=>{
 const text=clean(html);
 // Only ABSOLUTE source dates; never infer a quote date from "вчора" or page fetch time.
 return [...text.matchAll(/Ціни на\s+(\d{2}\.\d{2}\.20\d{2})/g)].map(m=>m[1]).filter(dateIsNotFuture);
};
export function parseEnkorr(html){
 const text=clean(html);
 // Source is a reference index, not a deliverable EXW/CPT quote.
 const section=text.match(/Ціни в Україні\s*\((\d{2}\.\d{2}\.\d{2,4})\)([\s\S]{0,800})/i);
 if(!section)throw Error('Missing dated Ukraine fuel reference table');
 let date=section[1];if(date.length===8)date=date.slice(0,6)+'20'+date.slice(6);
 if(!dateIsNotFuture(date))throw Error('Invalid or future price date');
 const part=section[2];
 const extract=(re,name)=>{
  const match=part.match(re);
  if(!match)throw Error('Missing '+name+' wholesale reference');
  const x=num(match[1]);
  if(!Number.isFinite(x)||x<10||x>250)throw Error('Out-of-range '+name+' value');
  return {price_uah_l:x,quote_date:dateToISO(date),basis:'Ukraine wholesale reference; not delivered Aleksandriia',vat:'not specified',source_url:'https://enkorr.ua/',kind:'market_reference'};
 };
 return {diesel:extract(/(?:Diesel|Дизель|ДП)\s+([\d.,]+)/i,'diesel'),gasoline_a95:extract(/(?:A[-–]?95|А[-–]?95)\s+([\d.,]+)/i,'A95')};
}
export function parseDirectory(html,kind){
 const text=clean(html);
 const expected=kind==='grain'?'Ціни на зерно':'Ціни на добрива';
 if(!text.includes(expected))throw Error('Unexpected directory content');
 const dates=stamp(html);
 // Directory inventory only. No automated trade quotes until seller/grade/location/VAT parser is verified.
 const offers=extractOfferCandidates(html,kind,kind==='grain'?'https://e-zerno.com/trader-prices':'https://e-zerno.com/fertilizer-prices').map(o=>({...o,freshness:quoteFreshness(o)}));
 return {listing_dates: [...new Set(dates)].sort().reverse().slice(0,12), dated_listing_count:dates.length, offers_status:'unverified_candidates',quote_values_published:0, quality_control:{published_candidates:offers.length, historical_over_30_days:offers.filter(o=>o.freshness==='archival_unverified').length, note:'Rejected malformed candidate rows are excluded; rejected-count is not currently measurable without parser instrumentation.'}, ...(kind==='grain'?{crop_coverage:cropCoverage(offers)}:{}), offers};
}
async function fetchSource(source){
 const controller=new AbortController(),t=setTimeout(()=>controller.abort(),timeoutMs);
 try{
  const res=await fetch(source.url,{signal:controller.signal,headers:{accept:'text/html,application/xhtml+xml','user-agent':'AGRO-BAROMETER-Market-Research/1.1'}});
  if(!res.ok)throw Error('HTTP '+res.status);
  const html=await res.text();
  if(html.length<500||html.length>2_000_000)throw Error('Unexpected HTML length');
  return html;
 }finally{clearTimeout(t);}
}
export async function collectPublicSources(label='morning'){
 const store=getStore({name:'agro-public-market',consistency:'strong'});
 const previous=await store.get('public-indicators-latest',{type:'json'}).catch(()=>null);
 const recorded=Object.fromEntries((previous?.sources||[]).map(x=>[x.id,x]));
 const results=[];
 for(const source of SOURCES){
  const checked_at=nowIso();
  try{
   const html=await fetchSource(source);
   const parsed=source.id==='fuel'?parseEnkorr(html):parseDirectory(html,source.id);
   const data=source.id==='fuel'?parsed:filterSourceOffers({...source,data:parsed}).data;
   results.push({...source,checked_at,last_success:checked_at,status:'ok',data,error:null});
  }catch(err){
   const old=recorded[source.id];
   results.push({...source,checked_at,last_success:old?.last_success||null,status:'error',data:old?.data||null,error:String(err?.message||err).slice(0,180)});
  }
 }
 const payload={schema_version:1,collector:'indicators_v2',run:label,last_attempt:nowIso(),sources:results,note:'E-ZERNO candidate quotes are UNVERIFIED. Relative dates skipped; VAT and basis unknown. Fuel is national wholesale reference. No effect on 0–100 scores.'};
 await store.setJSON('public-indicators-latest',payload);
 try { payload.history_write=await saveOfferHistory(results,payload.last_attempt); }
 catch(err) { payload.history_write={status:'error',message:String(err?.message||err).slice(0,180)}; console.error('offer history persist failed',err); }
 return payload;
}
