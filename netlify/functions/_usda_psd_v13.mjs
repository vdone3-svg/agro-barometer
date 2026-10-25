// USDA FAS PSD: official, keyed supply/demand data. No fabricated series.
export const BASE='https://api.fas.usda.gov/api/psd';
export const STORE='agro-usda-psd-v13';
const cropNames={wheat:/^wheat$/i,corn:/^corn$/i,barley:/^barley$/i,soy:/^soybeans?$/i,rapeseed:/^rapeseed$/i,sunflower:/^sunflowerseed$/i};
const s=v=>String(v??'').trim();
const arr=x=>Array.isArray(x)?x:[];
export function identifyCrops(rows){
 const found={};
 for(const row of arr(rows)){
  const label=s(row.commodityName??row.commodityDescription??row.name);
  const code=s(row.commodityCode??row.code);
  if(!/^\d{5,8}$/.test(code))continue;
  for(const [crop,pattern] of Object.entries(cropNames))if(pattern.test(label)&&!found[crop])found[crop]={code,label};
 }
 return found;
}
export function normalizePSD(rows,{crop,marketYear,scope,sourceUrl,expectedCommodityCode,asOf=new Date().toISOString()}={}){
 if(!Array.isArray(rows))throw new Error('PSD_response_not_array');
 if(rows.length>100000)throw new Error('PSD_response_too_large');
 if(!cropNames[crop]||!Number.isInteger(marketYear)||marketYear<1960||marketYear>2100)throw new Error('PSD_request_invalid');
 const results=[],seen=new Set(),invalid={year:0,value:0,attribute:0,unit:0,commodity:0,country:0};
 for(const r of rows){
  if(!r||typeof r!=='object')continue;
  const year=Number(r.marketYear??r.MarketYear);
  if(year!==marketYear){invalid.year++;continue;}
  const raw=r.value??r.Value;
  if(raw===null||raw===undefined||raw===''){invalid.value++;continue;}
  const value=Number(raw);
  if(!Number.isFinite(value)||value<0){invalid.value++;continue;}
  const attribute=s(r.attributeName??r.attributeDescription??r.AttributeDescription??r.attributeId??r.AttributeId);
  const unit=s(r.unitDescription??r.UnitDescription??r.unitId??r.UnitId);
  if(!attribute){invalid.attribute++;continue;}
  if(!unit){invalid.unit++;continue;}
  const country=s(r.countryName??r.CountryName??(scope==='world'?'World':''));
  const countryCode=s(r.countryCode??r.CountryCode??(scope==='world'?'WORLD':''));
  const code=s(r.commodityCode??r.CommodityCode);
  // A response may contain unrelated commodity rows: never mislabel those as the requested crop.
  if(expectedCommodityCode && code && code!==expectedCommodityCode){invalid.commodity++;continue;}
  // USDA exposes aggregate world and individual-country endpoints. Reject mismatched geography.
  if(scope==='ukraine' && countryCode && !['UP','UA','UKR'].includes(countryCode.toUpperCase())){invalid.country++;continue;}
  if(scope==='world' && countryCode && !['WORLD','WO','00','WLD'].includes(countryCode.toUpperCase())){invalid.country++;continue;}
  const id=[crop,year,scope,countryCode,attribute,unit].join('|');
  if(seen.has(id))continue;seen.add(id);
  results.push({crop,market_year:year,scope,country,country_code:countryCode,commodity_code:code,attribute,unit,value,source:'USDA FAS Production Supply and Distribution',source_url:sourceUrl,observed_at:asOf,comparable_to_local_price:false});
 }
 return {records:results,invalid};
}
export async function requestPSD(url,{key,fetchImpl=fetch,timeoutMs=15000}={}){
 if(!key||key.length<8)throw new Error('USDA_API_KEY_missing');
 const rsp=await fetchImpl(url,{headers:{'accept':'application/json','api_key':key},signal:AbortSignal.timeout(timeoutMs)});
 if(!rsp.ok)throw new Error('USDA_HTTP_'+rsp.status);
 const len=Number(rsp.headers?.get?.('content-length')||0);
 if(len>12000000)throw new Error('USDA_response_too_large');
 return rsp.json();
}
export async function collectPSD({key,fetchImpl=fetch,year=new Date().getUTCFullYear()}={}){
 const catalogue=await requestPSD(BASE+'/commodities',{key,fetchImpl});
 const countries=await requestPSD(BASE+'/countries',{key,fetchImpl});
 const ukraine=arr(countries).find(c=>/^ukraine$/i.test(s(c.countryName??c.name)));
 const ukraineCode=s(ukraine?.countryCode??ukraine?.code);
 const crops=identifyCrops(catalogue);
 const records=[],issues=[];
 if(!ukraineCode)issues.push({scope:'ukraine',reason:'country_code_not_found'});
 // Two latest market years preserve revisions; country and world are distinct data contexts.
 for(const [crop,{code}] of Object.entries(crops)){
  for(const yr of [year-1,year]){
   for(const scope of ['world',...(ukraineCode?['ua']:[])]){
    const url=BASE+`/commodity/${encodeURIComponent(code)}/${scope==='world'?'world':'country/'+encodeURIComponent(ukraineCode)}/year/${yr}`;
    try{
     const payload=await requestPSD(url,{key,fetchImpl});
     const normalized=normalizePSD(payload,{crop,marketYear:yr,scope:scope==='world'?'world':'ukraine',sourceUrl:url,expectedCommodityCode:code});
     records.push(...normalized.records);
     if(!normalized.records.length)issues.push({crop,market_year:yr,scope,reason:'no_valid_rows'});
    }catch(e){issues.push({crop,market_year:yr,scope,reason:String(e?.message||'error').slice(0,90)});}
   }
  }
 }
 return {schema_version:1,provider:'usda_psd',as_of:new Date().toISOString(),market_years:[year-1,year],crops_found:Object.keys(crops),records_total:records.length,records,issues,decision_grade:false,note:'USDA world/Ukraine supply-demand balances; not local grain prices or a standalone sale recommendation.'};
}
