import {getStore} from '@netlify/blobs';
import {STORE} from './_usda_psd_v13.mjs';
export default async()=>{
 try{
  const store=getStore({name:STORE,consistency:'strong'});
  const health=await store.get('health',{type:'json'}).catch(()=>null);
  const latest=await store.get('observations',{type:'json'}).catch(()=>null);
  return Response.json({schema_version:1,provider:'usda_psd',status:health?.status||'not_yet_run',health,records_total:latest?.records_total||0,crops_found:latest?.crops_found||[],market_years:latest?.market_years||[],note:'No USDA API key or private observations exposed. Balances are context, not purchasing offers.'},{headers:{'cache-control':'no-store'}});
 }catch(e){return Response.json({error:'status_unavailable'},{status:503});}
};
