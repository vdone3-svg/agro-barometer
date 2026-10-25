/**
 * V13: conservative economic comparison for grain procurement offers.
 * No source observations are promoted into validated transport quotes.
 * No unknown VAT, discounts, expenses, terminal locations or loading costs are assumed to be zero.
 * This module is pure and intentionally independent of existing 11 barometers.
 */
const str=x=>typeof x==='string'?x.trim():'';
const finitePositive=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
const dayMs=86400000;
export const CONFIG_V13=Object.freeze({origin:'Олександрія',region:'Кіровоградська область',referencePayloadTonnes:25,maxRateAgeDays:14,minIndependentSources:2,maxFreightSpreadRatio:0.35});
export const CROPS_V13=Object.freeze(['пшениця','кукурудза','соняшник','ячмінь','соя','ріпак']);
export function moneyUAH(v){return Math.round((v+Number.EPSILON)*100)/100;}
export function taxBasis({amount,vat_status,vat_rate,credit_eligible=false}){
 if(!finitePositive(amount))return {ok:false,reason:'Невідома сума'};
 if(!['included','excluded'].includes(vat_status))return {ok:false,reason:'Не визначено ПДВ'};
 if(typeof vat_rate!=='number'||!Number.isFinite(vat_rate)||vat_rate<0||vat_rate>1)return {ok:false,reason:'Не підтверджена ставка ПДВ'};
 if(vat_status==='excluded')return {ok:true,gross:moneyUAH(amount*(1+vat_rate)),net:moneyUAH(amount),vat:moneyUAH(amount*vat_rate)};
 const net=moneyUAH(amount/(1+vat_rate));
 // credit eligibility is tracked, NOT inferred from the taxpayer status.
 return {ok:true,gross:moneyUAH(amount),net,vat:moneyUAH(amount-net),credit_eligible:credit_eligible===true};
}
export function sourceIdentity(rate){
 // Multiple URLs on one marketplace are NOT independent sources.
 const id=str(rate?.source_organization_id)||str(rate?.carrier_id);
 if(id)return id.toLocaleLowerCase('uk-UA');
 try{return new URL(rate?.source_url).hostname.toLowerCase().replace(/^www\./,'');}catch{return '';}
}
const ageDays=(date,today)=>{
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^\d{4}-\d{2}-\d{2}$/.test(today||''))return null;
 const d=Date.parse(date+'T00:00:00Z'),t=Date.parse(today+'T00:00:00Z');
 return Number.isFinite(d)&&Number.isFinite(t)?(t-d)/dayMs:null;
};
export function eligibleFreight(rate,offer,{today='2026-10-25',maxRateAgeDays=14}={}){
 if(rate?.validated_for_market_model!==true || rate?.evidence_status!=='verified_document')return false;
 if(rate?.vehicle_type!=='grain_truck'||rate?.origin_city!=='Олександрія')return false;
 if(rate?.destination_city!==offer?.destination_city || str(rate?.destination_region)!==str(offer?.destination_region))return false;
 if(rate?.vat_status!==offer?.vat_status||rate?.vat_status==='unknown')return false;
 if(typeof rate?.vat_rate!=='number'||rate.vat_rate!==offer?.vat_rate)return false;
 if(rate?.cargo_type!==offer?.crop)return false;
 if(!finitePositive(rate?.price_per_tonne_uah))return false;
 if(!finitePositive(rate?.load_tonnes)||rate.load_tonnes<22||rate.load_tonnes>28)return false;
 if(offer?.destination_accuracy!=='exact')return false;
 // Rates without explicit exact delivery address identity cannot be applied to a specific terminal.
 if(!str(offer?.destination_location_id)||rate?.destination_location_id!==offer.destination_location_id)return false;
 if(rate?.rate_includes_waiting!==true)return false;
 const age=ageDays(rate.observed_date,today);
 return age!==null&&age>=0&&age<=maxRateAgeDays;
}
const median=values=>{const s=values.slice().sort((a,b)=>a-b);return s.length%2?s[(s.length-1)/2]:(s[s.length/2-1]+s[s.length/2])/2;};
export function evaluateV13(offers=[],rates=[],{today='2026-10-25',minIndependentSources=2,vat_rate=null,maxFreightSpreadRatio=0.35}={}){
 const comparable=[],review=[],archived=[];
 for(const offer of offers){
  const reasons=[];
  if(offer?.kind!=='grain'||!CROPS_V13.includes(offer?.crop))continue;
  if(offer?.freshness==='archival_unverified'){archived.push({offer,reason:'Архівне оголошення'});continue;}
  if(offer?.verification!=='verified')reasons.push('Ціна покупця не підтверджена');
  if(!finitePositive(offer?.price_uah_per_tonne))reasons.push('Невідома ціна у грн/т');
  if(!str(offer?.grade_or_spec))reasons.push('Не визначений клас або специфікація культури');
  if(!str(offer?.quality_basis_id)||offer?.quality_conditions_verified!==true)reasons.push('Умови якості й перерахунку ціни не підтверджені');
  if(!['included','excluded'].includes(offer?.vat_status))reasons.push('Не визначено ПДВ у ціні');
  if(typeof vat_rate!=='number'||offer?.vat_rate!==vat_rate)reasons.push('Не підтверджено ставку ПДВ для конкретної пропозиції');
  if(!['pickup','seller_delivery'].includes(offer?.delivery_mode))reasons.push('Невідомо, хто оплачує доставку');
  if(!str(offer?.destination_city))reasons.push('Місце приймання не визначено');
  if(offer?.delivery_mode==='pickup'&&offer?.pickup_seller_freight_cost_confirmed_zero!==true)reasons.push('Покупець не підтвердив оплату самовивозу');
  if(offer?.delivery_mode==='seller_delivery'&&offer?.destination_accuracy!=='exact')reasons.push('Лише місто: невідомий точний елеватор/термінал');
  if(offer?.payment_terms_verified!==true||!str(offer?.payment_terms_id))reasons.push('Не перевірені умови та строк оплати');
  if(offer?.tax_treatment_verified!==true)reasons.push('Не підтверджено податкову основу економічного розрахунку');
  if(offer?.delivery_mode==='seller_delivery'&&offer?.seller_vat_credit_on_freight_confirmed!==true)reasons.push('Не підтверджено право на податковий кредит за послугами перевізника');
  const vat=taxBasis({amount:offer?.price_uah_per_tonne,vat_status:offer?.vat_status,vat_rate});
  if(!vat.ok)reasons.push('Неможливо нормалізувати ПДВ закупівельної ціни: '+vat.reason);
  let freightGross=0,freightNet=0,freightSources=0,freightRange=null;
  if(offer?.delivery_mode==='seller_delivery'){
   const matches=rates.filter(r=>eligibleFreight(r,offer,{today}));
   const unique=new Map();for(const r of matches){const id=sourceIdentity(r);if(id&&!unique.has(id))unique.set(id,r)}
   freightSources=unique.size;
   if(unique.size<minIndependentSources)reasons.push(`Недостатньо незалежних підтверджених ставок (є ${unique.size}, потрібно ${minIndependentSources})`);
   else {
    const prices=[...unique.values()].map(r=>r.price_per_tonne_uah);
    freightGross=moneyUAH(median(prices));freightRange=[Math.min(...prices),Math.max(...prices)];
    if((freightRange[1]-freightRange[0])/freightGross>maxFreightSpreadRatio)reasons.push('Ставки занадто розходяться: потрібне уточнення умов перевезення');
    const freightTax=taxBasis({amount:freightGross,vat_status:offer.vat_status,vat_rate});
    if(freightTax.ok)freightNet=freightTax.net;
    else reasons.push('Не можна привести транспортний тариф до порівнюваної основи ПДВ');
   }
  }
  // All other seller-specific costs must explicitly be accounted for or confirmed equal across alternatives.
  if(offer?.extra_seller_costs_confirmed!==true||typeof offer?.extra_seller_costs_uah_per_tonne!=='number'||offer.extra_seller_costs_uah_per_tonne<0)
   reasons.push('Інші витрати продавця не підтверджені');
  if(reasons.length){review.push({offer,reasons,freight_sources:freightSources});continue;}
  const extra=offer.extra_seller_costs_uah_per_tonne;
  // Extras must be supplied on the same net-of-VAT economic basis; no automatic credit assumed.
  comparable.push({offer,net_revenue_uah_per_tonne:moneyUAH(vat.net-freightNet-extra),gross_cash_before_other_costs_uah_per_tonne:moneyUAH(vat.gross-freightGross),freight_gross_uah_per_tonne:freightGross,freight_net_uah_per_tonne:freightNet,freight_sources:freightSources,freight_range_gross:freightRange});
 }
 // No cross-grade or cross-quality group sorting.
 const groups=new Map();for(const row of comparable){const o=row.offer,k=[o.crop,o.grade_or_spec,o.quality_basis_id,o.vat_status,o.payment_terms_id||''].join('|');if(!groups.has(k))groups.set(k,[]);groups.get(k).push(row)}
 const ranked=[];for(const [group,rows]of groups){rows.sort((a,b)=>b.net_revenue_uah_per_tonne-a.net_revenue_uah_per_tonne);rows.forEach((r,i)=>ranked.push({...r,comparison_group:group,position:i+1}));}
 return {ranked,review,archived,summary:{comparable:ranked.length,review:review.length,archived:archived.length},caveat:'Це розрахунок за підтвердженими вихідними даними, не гарантія кінцевої ціни чи виконання рейсу. Не знижувати видимість пропозицій без порівнюваних доказів.'};
}
