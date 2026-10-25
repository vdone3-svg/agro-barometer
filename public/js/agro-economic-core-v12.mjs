import {destination} from './agro-decision-core-v9.mjs';
// Fail closed: archived/unverified quotes and unapproved transport observations never create an investment decision.
export function assessSales(offers=[], routes=[], freight=[], {today=new Date().toISOString().slice(0,10)}={}) {
 const ranked=[],review=[],outOfScope=[];
 for(const o of offers){
  if(o.kind!=='grain'||o.currency!=='UAH'||!(Number(o.price)>0)||!o.product)continue;
  if(o.freshness==='archival_unverified'){outOfScope.push({offer:o,reason:'Архівне оголошення'});continue;}
  const city=destination(o);
  const route=routes.find(r=>r.city===city&&r.region===o.region&&r.status==='planning_city_to_city'&&Number(r.km)>0);
  const reasons=[];
  if(!city)reasons.push('Неможливо однозначно визначити місто');
  else if(!route)reasons.push('Немає перевіреної міської відстані');
  if(o.verification!=='verified')reasons.push('Закупівельна пропозиція не підтверджена');
  if(o.vat!=='included'&&o.vat!=='excluded')reasons.push('Невідомі умови ПДВ');
  if(o.basis!=='delivered_seller_pays')reasons.push('Базис і оплата доставки не підтверджені');
  if(o.price_unit!=='UAH_per_tonne')reasons.push('Одиниця закупівельної ціни не підтверджена');
  if(o.quality!=='verified')reasons.push('Якість/клас продукції не підтверджені');
  // Matching observed route, direction, VAT, and approval only. No averaging incompatible offers.
  const matching=route?freight.filter(f=>
   f.validated_for_market_model===true&&f.vehicle_type==='grain_truck'&&
   f.origin_city==='Олександрія'&&f.destination_city===city&&
   f.vat_status===o.vat&&Number(f.price_per_tonne_uah)>0&&
   f.evidence_status==='verified_document'&&
   typeof f.observed_date==='string'&&f.observed_date<=today&&
   (Date.parse(today+'T00:00:00Z')-Date.parse(f.observed_date+'T00:00:00Z'))/(86400000)<=14
  ):[];
  if(!matching.length)reasons.push('Немає актуальної схваленої ставки зерновоза для цього напрямку');
  if(reasons.length){review.push({offer:o,city,reasons});continue;}
  // Conservative: require multiple independent corroborating rates before publishing a comparison.
  const uniqueSources=new Set(matching.map(f=>f.source_url));
  if(uniqueSources.size<2){review.push({offer:o,city,reasons:['Недостатньо незалежних транспортних джерел (потрібно щонайменше два)']});continue;}
  const sorted=matching.map(f=>Number(f.price_per_tonne_uah)).sort((a,b)=>a-b);
  const median=sorted.length%2?sorted[(sorted.length-1)/2]:(sorted[sorted.length/2-1]+sorted[sorted.length/2])/2;
  ranked.push({offer:o,city,km:route.km,freight:median,net:Number(o.price)-median,source_count:uniqueSources.size});
 }
 // Compare only same product and same VAT category; never blend wheat classes.
 const groups={};
 for(const row of ranked){const key=row.offer.product+'|'+row.offer.vat;(groups[key]??=[]).push(row);}
 const evaluated=[];
 for(const group of Object.values(groups)){
  group.sort((a,b)=>b.net-a.net);
  // No definitive 'unprofitable' without material difference beyond real observed tariff spread.
  for(const row of group)evaluated.push({...row,position:group.indexOf(row)+1,decision:'Порівняння за підтвердженими даними; перевірити перед договором'});
 }
 return {ranked:evaluated,review,outOfScope,summary:{eligible:evaluated.length,needs_review:review.length,archival:outOfScope.length},note:'No speculative transport estimates. No offer hidden as unprofitable without comparable verified price and freight evidence.'};
}
