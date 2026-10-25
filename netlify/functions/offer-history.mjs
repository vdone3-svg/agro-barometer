import { getStore } from '@netlify/blobs';
export default async ()=>{
 const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store'};
 try{
  const row=await getStore({name:'agro-public-market',consistency:'strong'}).get('unverified-offer-history-v1',{type:'json'});
  if(!row)return new Response(JSON.stringify({schema_version:1,status:'not_started',total_observations:0,changes:[],observations:[]}),{headers});
  return new Response(JSON.stringify({...row,observations:row.observations.slice(-300).reverse(),changes:row.changes.slice(0,50)}),{headers});
 }catch(err){console.error('offer-history',err);return new Response(JSON.stringify({status:'error',message:'Offer history store unavailable'}),{status:503,headers});}
};
