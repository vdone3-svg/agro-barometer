import { getStore } from '@netlify/blobs';
export default async ()=>{
 const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store'};
 try {
  const row=await getStore({name:'agro-public-market',consistency:'strong'}).get('public-indicators-latest',{type:'json'});
  return new Response(JSON.stringify(row||{schema_version:1,status:'not_started',sources:[]}),{headers});
 }catch(error){return new Response(JSON.stringify({status:'error',message:'Market indicators store unavailable'}),{status:503,headers});}
};
