import {getStore} from '@netlify/blobs';
import {fetchEuCereals,MARKET_STORE} from './_eu_cereal_prices_v13.mjs';
export default async ()=>{
 const store=getStore({name:MARKET_STORE,consistency:'strong'});
 const now=new Date().toISOString();
 try{
  const data=await fetchEuCereals();
  if(!data.records_total)throw new Error('EU_zero_valid_rows');
  const old=await store.get('observations',{type:'json'}).catch(()=>null);
  const combined=[...data.rows,...(old?.rows||[])];
  const seen=new Set(),rows=[];
  for(const r of combined.sort((a,b)=>b.period_start.localeCompare(a.period_start))){
   const k=[r.period_start,r.period_end,r.member_state,r.product_name,r.market,r.stage].join('|');
   if(seen.has(k))continue;seen.add(k);rows.push(r);
   if(rows.length>=16000)break;
  }
  await store.setJSON('observations',{...data,rows,records_total:rows.length,last_success:now});
  await store.setJSON('health',{status:'ok',last_attempt:now,last_success:now,latest_batch:data.records_total,stored:rows.length,invalid:data.invalid});
  console.log('EU cereal prices saved',{new:data.records_total,total:rows.length});
 }catch(e){
  const old=await store.get('health',{type:'json'}).catch(()=>null);
  await store.setJSON('health',{status:'error',last_attempt:now,last_success:old?.last_success||null,reason:String(e?.message||'error').slice(0,160)});
  console.error('EU cereal prices fetch failed',String(e?.message||'unknown'));
 }
};
export const config={schedule:'40 5 * * *'};
