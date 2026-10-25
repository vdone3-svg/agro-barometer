// EU DG AGRI official weekly cereal market prices; MARKET CONTEXT ONLY.
// https://agridata.ec.europa.eu/extensions/API_Documentation/cereals.html
export const EU_CEREALS_URL='https://api.tech.ec.europa.eu/agrifood/api/cereal/prices';
export const MARKET_STORE='agro-eu-cereals-v13';
export const CROPS=['wheat','corn','barley'];
const PRODUCT_HINTS={wheat:/\bwheat\b|\bbl[eé]\b/i,corn:/\bmaize\b|\bcorn\b|\bmais\b/i,barley:/\bbarley\b|\bbarley\b|\bcebada\b/i};
export function isoFromEuDate(s){
 if(typeof s!=='string')return null;
 const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s);
 if(!m)return null;
 const iso=`${m[3]}-${m[2]}-${m[1]}`;
 const d=new Date(iso+'T00:00:00Z');
 return !isNaN(d)&&d.toISOString().slice(0,10)===iso?iso:null;
}
export function euroPrice(s){
 if(typeof s==='number')return Number.isFinite(s)&&s>0?s:null;
 if(typeof s!=='string')return null;
 let v=s.trim().replace(/[€\s\u00a0]/g,'');
 if(!/^[0-9.,]+$/.test(v))return null;
 const c=v.lastIndexOf(','),p=v.lastIndexOf('.');
 if(c>=0&&p>=0)v=c>p?v.replace(/\./g,'').replace(',','.'):v.replace(/,/g,'');
 else if(c>=0)v=v.replace(',','.');
 const n=Number(v);return Number.isFinite(n)&&n>0?n:null;
}
export function normalizeEuPrices(payload,asOf=new Date().toISOString()){
 if(!Array.isArray(payload))throw new Error('eu_response_not_array');
 if(payload.length>250000)throw new Error('eu_response_too_large');
 const rows=[],invalid={date:0,price:0,unit:0,product:0},seen=new Set();
 for(const o of payload){
  if(!o||typeof o!=='object')continue;
  const date=isoFromEuDate(o.beginDate),end=isoFromEuDate(o.endDate),price=euroPrice(o.price);
  const unit=String(o.unit||'').trim().toUpperCase();
  const product=String(o.productName||'').trim();
  const crop=Object.keys(PRODUCT_HINTS).find(c=>PRODUCT_HINTS[c].test(product));
  if(!date||!end||date>end){invalid.date++;continue;}
  if(!price){invalid.price++;continue;}
  // Only accept explicit prices per tonne, never per 100kg or head.
  if(!/^(TONNES?|T|TONS?|TONNE|€\s*\/\s*T|EUR\s*\/\s*(T|TONNE))$/.test(unit)){invalid.unit++;continue;}
  if(!crop){invalid.product++;continue;}
  const memberStateCode=String(o.memberStateCode||'').trim().toUpperCase();
  const market=String(o.marketName||'').trim().slice(0,150);
  const stage=String(o.stageName||'').trim().slice(0,220);
  if(!/^[A-Z]{2}$/.test(memberStateCode)||!market||!stage){invalid.product++;continue;}
  const key=[date,end,memberStateCode,product,market,stage].join('|');
  if(seen.has(key))continue;seen.add(key);
  rows.push({period_start:date,period_end:end,crop,product_name:product,member_state:memberStateCode,market,stage,price_eur_per_tonne:price,original_unit:o.unit,source:'EU Commission DG AGRI Agri-food Data Portal',source_url:EU_CEREALS_URL,scope:'EU_wholesale_market',comparison_with_ukraine_buyers:'not_comparable',observed_at:asOf});
 }
 rows.sort((a,b)=>b.period_start.localeCompare(a.period_start));
 return {schema_version:1,provider:'eu_dg_agri',series:'cereal_weekly_prices',as_of:asOf,raw_count:payload.length,records_total:rows.length,invalid,rows:rows.slice(0,8000),decision_grade:false,note:'EU wholesale price context in EUR/tonne; NOT Ukraine grain offers, USD values or freight rates.'};
}
export function euEndpoint(begin,end){
 if(!isoFromEuDate(begin)||!isoFromEuDate(end))throw new Error('invalid_eu_date');
 return EU_CEREALS_URL+`?beginDate=${encodeURIComponent(begin)}&endDate=${encodeURIComponent(end)}`;
}
export async function fetchEuCereals({fetchImpl=fetch,now=new Date(),timeoutMs=14000}={}){
 const end=now.toISOString().slice(0,10);
 const start=new Date(now.getTime()-60*86400000).toISOString().slice(0,10);
 const toEu=x=>x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4);
 const url=euEndpoint(toEu(start),toEu(end));
 const signal=AbortSignal.timeout(timeoutMs);
 const response=await fetchImpl(url,{headers:{'accept':'application/json'},signal});
 if(!response.ok)throw new Error('EU_HTTP_'+response.status);
 const length=Number(response.headers?.get?.('content-length')||0);
 if(length>10000000)throw new Error('EU_response_too_big');
 const payload=await response.json();
 const result=normalizeEuPrices(payload,now.toISOString());
 return {...result,period_requested:{start,end},query_url:url};
}
