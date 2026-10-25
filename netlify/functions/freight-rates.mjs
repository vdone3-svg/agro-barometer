import {getStore} from '@netlify/blobs';
import {normalizeFreightRate,mergeRates,publicView} from './_freight_rates.mjs';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'};
function respond(body,status=200){return new Response(JSON.stringify(body),{status,headers});}
export default async (request)=>{
 const method=request.method.toUpperCase();
 if(method!=='GET'&&method!=='POST')return respond({error:'method_not_allowed'},405);
 if(method==='POST'){
  const secret=process.env.FREIGHT_ADMIN_TOKEN;
  if(!secret||secret.length<24)return respond({error:'write_access_not_configured'},503);
  if(request.headers.get('authorization')!==`Bearer ${secret}`)return respond({error:'unauthorized'},401);
  const contentType=request.headers.get('content-type')||'';
  if(!contentType.startsWith('application/json'))return respond({error:'JSON_required'},415);
 }
 try{
  const store=getStore({name:'agro-freight-rates',consistency:'strong'});
  const current=await store.get('freight-v11',{type:'json'})||{records:[]};
  if(method==='GET')return respond(publicView(current.records||[]));
  const raw=await request.text();
  if(raw.length>120000)return respond({error:'payload_too_large'},413);
  let body;
  try{body=JSON.parse(raw)}catch{return respond({error:'invalid_json'},400)}
  if(!Array.isArray(body.records)||body.records.length<1||body.records.length>50)return respond({error:'provide_1_to_50_records'},400);
  let normalized;
  try{normalized=body.records.map(o=>normalizeFreightRate(o))}catch(e){return respond({error:'invalid_record',detail:e.message},400)}
  let merged;
  try{merged=mergeRates(current.records||[],normalized)}catch(e){return respond({error:'duplicate_conflict_or_limit',detail:e.message},409)}
  await store.setJSON('freight-v11',{schema_version:1,updated_at:new Date().toISOString(),records:merged});
  return respond({status:'saved',records_total:merged.length,accepted_this_request:normalized.length,eligible_for_auto_pricing:0});
 }catch(e){console.error('freight-rates',e);return respond({error:'freight_database_unavailable'},503)}
};
