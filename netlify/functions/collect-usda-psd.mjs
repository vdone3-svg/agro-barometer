import {getStore} from '@netlify/blobs';
import {collectPSD,STORE} from './_usda_psd_v13.mjs';
export default async()=>{
 const store=getStore({name:STORE,consistency:'strong'});
 const now=new Date().toISOString();
 const key=process.env.USDA_API_KEY;
 if(!key){await store.setJSON('health',{status:'not_configured',last_attempt:now,note:'USDA_API_KEY required; no data fabricated.'});return;}
 try{
  const data=await collectPSD({key});
  if(data.records_total===0)throw new Error('USDA_no_valid_records');
  const prior=await store.get('observations',{type:'json'}).catch(()=>null);
  const keep=new Map();
  for(const row of [...(prior?.records||[]),...data.records]){
   const id=[row.crop,row.market_year,row.scope,row.country_code,row.attribute,row.unit].join('|');
   keep.set(id,row);
  }
  const records=[...keep.values()].slice(-16000);
  await store.setJSON('observations',{...data,records,records_total:records.length,last_success:now});
  await store.setJSON('health',{status:'ok',last_attempt:now,last_success:now,new_records:data.records_total,stored:records.length,issues:data.issues.length});
 }catch(e){
  const old=await store.get('health',{type:'json'}).catch(()=>null);
  await store.setJSON('health',{status:'error',last_attempt:now,last_success:old?.last_success||null,reason:String(e?.message||'error').slice(0,120)});
 }
};
export const config={schedule:'25 7 * * 2'};
