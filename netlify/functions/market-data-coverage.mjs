import {getStore} from '@netlify/blobs';
import {coverageReport} from './_market_archive_v13.mjs';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'public, max-age=0, s-maxage=900'};
export default async ()=>{
 try{
  const store=getStore({name:'agro-market-evidence-v13',consistency:'strong'});
  const archive=await store.get('news-archive',{type:'json'});
  return new Response(JSON.stringify({schema_version:1,status:archive?'archived':'not_collected_yet',news:coverageReport(archive),structured_market_data:{usda_psd:'pending_api_key_and_mapping',eu_agrifood:'collector_created_pending_live_netlify_validation',world_bank_monthly:'pending_verified_import'},decision_grade:false,note:'Archive coverage only; no claims about actual buyer or carrier prices.'}),{headers});
 }catch(err){return new Response(JSON.stringify({status:'archive_unavailable',error:'read_failed'}),{status:503,headers});}
};
