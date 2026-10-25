import { getStore } from '@netlify/blobs';
import { filterSourceOffers } from './_offer_quality.mjs';
export default async ()=>{
 const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store'};
 try {
  const row=await getStore({name:'agro-public-market',consistency:'strong'}).get('public-indicators-latest',{type:'json'});
  if(!row)return new Response(JSON.stringify({schema_version:1,status:'not_started',sources:[]}),{headers});
  const sources=(row.sources||[]).map(filterSourceOffers);
  return new Response(JSON.stringify({...row,quality_filter_version:'unified_v62',sources}),{headers});
 }catch(error){console.error('public-indicators',error);return new Response(JSON.stringify({status:'error',message:'Market indicators store unavailable'}),{status:503,headers});}
};
