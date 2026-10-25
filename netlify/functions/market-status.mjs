import { getStore } from '@netlify/blobs';
export default async () => {
 try {
  const store = getStore({name:'agro-public-market',consistency:'strong'});
  const row = await store.get('latest',{type:'json'});
  return new Response(JSON.stringify(row || {schema_version:1,last_success:null,fx:{},status:'not_started'}),{headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
 }catch(err){return new Response(JSON.stringify({status:'error',message:'Live store unavailable'}),{status:503,headers:{'content-type':'application/json','cache-control':'no-store'}});}
};
