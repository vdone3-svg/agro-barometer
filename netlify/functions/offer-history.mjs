import { offerProblem, quoteFreshness } from './_offer_quality.mjs';
import { getStore } from '@netlify/blobs';
export default async ()=>{
 const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store'};
 try{
  const row=await getStore({name:'agro-public-market',consistency:'strong'}).get('unverified-offer-history-v1',{type:'json'});
  if(!row)return new Response(JSON.stringify({schema_version:1,status:'not_started',total_observations:0,changes:[],observations:[]}),{headers});
  const all=Array.isArray(row.observations)?row.observations:[];
  const safe=all.filter(x=>!offerProblem(x));
  const safeFingerprints=new Set(safe.map(x=>x.fingerprint));
  const safeChanges=(row.changes||[]).filter(c=>safe.some(x=>x.identity===c.identity));
  const visible=safe.slice(-300).reverse().map(o=>({...o,freshness:quoteFreshness(o)}));
  return new Response(JSON.stringify({...row,quality_control:{hidden_legacy_malformed:all.length-safe.length,visible_valid:visible.length,raw_archive_total:all.length},observations:visible,changes:safeChanges.slice(0,50)}),{headers});
 }catch(err){console.error('offer-history',err);return new Response(JSON.stringify({status:'error',message:'Offer history store unavailable'}),{status:503,headers});}
};
