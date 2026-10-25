// Current situation only: five-year price charts MUST NOT determine buy/sell recommendations.
// Evidence observations must be sourced, dated, scoped and independently corroborated.
export const CURRENT_FACTORS=Object.freeze(['ukraine_crop','world_balance','export_demand','processing_demand','logistics','local_price']);
export const DECISION_STATES=Object.freeze(['Потребує даних','Ситуація неоднозначна','Є підстави розглянути продаж','Є підстави зачекати']);
const STALE_DAYS=Object.freeze({ukraine_crop:30,world_balance:45,export_demand:21,processing_demand:21,logistics:14,local_price:7});
const MILLIS=86400000;
function validDay(value){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
 const d=new Date(value+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===value;
}
function safeHttps(value){try{return new URL(value).protocol==='https:'}catch{return false}}
export function classifyObservation(entry,{crop,now=Date.now()}={}){
 const reasons=[];
 if(!entry||typeof entry!=='object')return {valid:false,reasons:['Відсутні дані']};
 if(!CURRENT_FACTORS.includes(entry.factor))reasons.push('Невідомий ринковий чинник');
 if(entry.crop!==crop)reasons.push('Інша культура');
 if(!['up','down','neutral'].includes(entry.impact))reasons.push('Вплив не підтверджений');
 if(!['official_data','verified_market_data','editorial_analysis'].includes(entry.evidence_type))reasons.push('Не зазначено тип доказу');
 if(typeof entry.publisher!=='string'||!entry.publisher.trim())reasons.push('Немає видавця');
 if(!safeHttps(entry.url))reasons.push('Немає захищеного посилання');
 if(!validDay(entry.event_date))reasons.push('Некоректна дата події');
 else {
  const delta=now-Date.parse(entry.event_date+'T00:00:00Z');
  if(delta < -MILLIS)reasons.push('Подія в майбутньому');
  if(delta > (STALE_DAYS[entry.factor]??0)*MILLIS)reasons.push('Дані застаріли');
 }
 if(entry.confirmed!==true)reasons.push('Факт не перевірено');
 if(typeof entry.description!=='string'||entry.description.trim().length<15)reasons.push('Немає пояснення факту');
 return {valid:reasons.length===0,reasons};
}
export function assessCurrentMarket(crop,observations,{now=Date.now()}={}){
 const items=Array.isArray(observations)?observations:[];
 const accepted=[],rejected=[];
 for(const o of items){const check=classifyObservation(o,{crop,now});(check.valid?accepted:rejected).push(check.valid?o:{observation:o,reasons:check.reasons});}
 const byFactor=new Map();for(const item of accepted){const a=byFactor.get(item.factor)||[];a.push(item);byFactor.set(item.factor,a)}
 const corroborated=[];const conflicts=[];
 for(const [factor,group] of byFactor){
  // No double count: a single publisher can syndicate many articles.
  const pubs=new Set(group.map(x=>x.publisher.trim().toLowerCase()));
  const impacts=new Set(group.filter(x=>x.impact!=='neutral').map(x=>x.impact));
  if(impacts.size>1)conflicts.push(factor);
  if(pubs.size>=2 && impacts.size===1)corroborated.push({factor,impact:[...impacts][0],publishers:pubs.size});
 }
 const namedFactors=new Set(corroborated.map(x=>x.factor));
 // Local price and economic feasibility are mandatory; journalism cannot prove them.
 const ready=namedFactors.has('local_price')&&namedFactors.has('logistics')&&corroborated.length>=3&&conflicts.length===0;
 const up=corroborated.filter(x=>x.impact==='up').length,down=corroborated.filter(x=>x.impact==='down').length;
 const signal=!ready?'Потребує даних':up&&down?'Ситуація неоднозначна':up>=3?'Є підстави розглянути продаж':down>=3?'Є підстави зачекати':'Ситуація неоднозначна';
 return {crop,signal,can_publish_direction:ready&&signal!=='Ситуація неоднозначна',score:null,
  evidence_count:accepted.length,corroborated_factors:corroborated,conflicting_factors:conflicts,
  rejected_count:rejected.length,reason:!ready?'Для висновку потрібні підтверджені поточні ціни, логістика та щонайменше три незалежно підтверджені ринкові чинники.':conflicts.length?'Джерела суперечать одне одному.':'Ринкові чинники узгоджені; рішення не є гарантією ціни.',
  source_links:accepted.slice(0,10).map(x=>x.url)};
}
