import {getStore} from '@netlify/blobs';
import {MARKET_STORE} from './_eu_cereal_prices_v13.mjs';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'public, max-age=0, s-maxage=900'};
export default async ()=>{
 try{
  const store=getStore({name:MARKET_STORE,consistency:'strong'});
  const [health,data]=await Promise.all([store.get('health',{type:'json'}),store.get('observations',{type:'json'})]);
  const samples=(data?.rows||[]).slice(0,6);
  return new Response(JSON.stringify({provider:'European Commission DG AGRI',status:health?.status||'not_collected_yet',last_attempt:health?.last_attempt||null,last_success:health?.last_success||null,records_total:data?.records_total||0,crops:[...new Set((data?.rows||[]).map(r=>r.crop))],sample:samples,source:'https://agridata.ec.europa.eu/extensions/API_Documentation/cereals.html',decision_grade:false,warning:'EU market prices in EUR/tonne; not Ukrainian grain buyer quotes. Cannot infer Ukrainian farmgate profitability.'}),{headers});
 }catch(e){return new Response(JSON.stringify({status:'store_unavailable',records_total:0,decision_grade:false}),{status:503,headers});}
};
