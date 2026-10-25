// V13 horizons: prospective evidence, NOT past-year seasonality. No automated trade or fabricated score.
import {classifyObservation, CURRENT_FACTORS} from './agro-current-evidence-v13.mjs';

export const HORIZONS = Object.freeze([
 Object.freeze({id:'7-14d',label:'7–14 днів',min_days:7,max_days:14}),
 Object.freeze({id:'30d',label:'30 днів',min_days:15,max_days:30}),
 Object.freeze({id:'90d',label:'3 місяці',min_days:31,max_days:90})
]);
const VALID_HORIZONS=new Set(HORIZONS.map(h=>h.id));
const VALID_IMPACTS=new Set(['up','down','neutral']);
const DATE_MS=86400000;
function utcDate(s){if(typeof s!=='string'|| !/^\d{4}-\d{2}-\d{2}$/.test(s))return NaN;const n=Date.parse(s+'T00:00:00Z');return Number.isFinite(n)&&new Date(n).toISOString().slice(0,10)===s?n:NaN}
function dedupSource(o){ // publisher plus original report URL, never number of syndicated stories
 const publisher=String(o.publisher||'').trim().toLowerCase();
 const original=String(o.original_source||publisher).trim().toLowerCase();
 return original || publisher;
}
export function validateHorizonObservation(o,{crop,now=Date.now()}={}){
 const base=classifyObservation(o,{crop,now});const reasons=[...base.reasons];
 if(!VALID_HORIZONS.has(o?.horizon))reasons.push('Невідомий часовий горизонт');
 if(!VALID_IMPACTS.has(o?.impact))reasons.push('Немає визначеного впливу');
 if(o?.direction_basis!=='measured' && o?.direction_basis!=='reasoned_forecast')reasons.push('Немає методики визначення впливу');
 if(typeof o?.metric!=='string'||!o.metric.trim())reasons.push('Не визначений показник');
 if(o?.horizon==='90d' && o?.evidence_type==='editorial_analysis' && o?.direction_basis==='measured')reasons.push('Тримісячний напрямок не може бути виміряний лише редакційним текстом');
 const asOf=utcDate(o?.event_date);
 if(Number.isFinite(asOf)&&asOf > now+DATE_MS)reasons.push('Майбутня дата події');
 return {valid:reasons.length===0,reasons};
}
export function assessHorizon(crop,horizon,observations,{now=Date.now()}={}){
 if(!VALID_HORIZONS.has(horizon))throw new RangeError('Невідомий горизонт');
 const accepted=[],rejected=[];
 for(const item of (Array.isArray(observations)?observations:[])){
  if(item?.horizon!==horizon)continue; // no cross-horizon leakage
  const v=validateHorizonObservation(item,{crop,now});
  if(v.valid)accepted.push(item);else rejected.push({item,reasons:v.reasons});
 }
 // Independent origins and distinct factor classes: same publisher across multiple articles counts once per factor.
 const groups=new Map();for(const o of accepted){if(!CURRENT_FACTORS.includes(o.factor))continue;const a=groups.get(o.factor)||[];a.push(o);groups.set(o.factor,a)}
 const corroborated=[],conflicts=[];
 for(const [factor,group] of groups){
  const sources=new Map();for(const o of group){const key=dedupSource(o);if(!sources.has(key))sources.set(key,new Set());sources.get(key).add(o.impact)}
  const allImpacts=new Set([...sources.values()].flatMap(v=>[...v].filter(i=>i!=='neutral')));
  if(allImpacts.size>1){conflicts.push(factor);continue}
  if(sources.size>=2 && allImpacts.size===1)corroborated.push({factor,impact:[...allImpacts][0],source_count:sources.size});
 }
 const factors=new Set(corroborated.map(o=>o.factor));
 const ready=corroborated.length>=3 && factors.has('local_price') && factors.has('logistics') && conflicts.length===0;
 const up=corroborated.filter(o=>o.impact==='up').length;
 const down=corroborated.filter(o=>o.impact==='down').length;
 let status='Недостатньо даних',direction=null;
 if(ready){ status=(up&&down)?'Суперечливі фактори':'Ринкова оцінка потребує інтерпретації';
  // Even fully corroborated directional observations need calibrated backtesting before publication.
  direction=up>down?'підтримка ціни':down>up?'тиск на ціну':null;
 }
 return {crop,horizon,status,direction,score:null,can_publish_buy_sell:false,
  eligible_evidence:accepted.length,rejected_evidence:rejected.length,
  corroborated_factors:corroborated,conflicts,
  readiness:ready?'Покриття фактів достатнє для якісного огляду, але сигнал ще не відкалібровано.':'Не вистачає незалежно підтверджених актуальних показників, включно з місцевою ціною та логістикою.',
  sources:[...new Set(accepted.map(x=>x.url))].slice(0,12)};
}
export function assessThreeHorizons(crop,observations,opts={}){
 return {crop,historical_charts_are_decision_inputs:false,indicators_0_to_100_unchanged:true,
  horizons:HORIZONS.map(h=>({...h,...assessHorizon(crop,h.id,observations,opts)}))};
}
