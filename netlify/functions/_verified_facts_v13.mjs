// Source-bound public reference snapshots. Never label as live API results.
export const FACTS = Object.freeze([
 {id:'ua-harvest-grain-2026-10-01',source_name:'Держстат України',source_kind:'official_primary',source_url:'https://stat.gov.ua/uk/news/nove-na-sayti-ploshchi-valovi-zbory-ta-urozhaynist-silskohospodarskykh-kultur-1',publication_date:'2026-10-20',observation_date:'2026-10-01',geography:'UA',commodity:'grain_and_pulses_total',metric:'harvested_volume',value:36.3,unit:'million_metric_tonnes',period:'2026-10-01',basis:'harvest_to_date',status:'source_documented',usable_for_price_ranking:false},
 {id:'ua-harvest-wheat-2026-10-01',source_name:'Держстат України',source_kind:'official_primary',source_url:'https://stat.gov.ua/uk/news/nove-na-sayti-ploshchi-valovi-zbory-ta-urozhaynist-silskohospodarskykh-kultur-1',publication_date:'2026-10-20',observation_date:'2026-10-01',geography:'UA',commodity:'wheat',metric:'harvested_volume',value:26.1,unit:'million_metric_tonnes',period:'2026-10-01',basis:'harvest_to_date',status:'source_documented',usable_for_price_ranking:false},
 {id:'ua-harvest-grain-yoy-2026-10-01',source_name:'Держстат України',source_kind:'official_primary',source_url:'https://stat.gov.ua/uk/news/nove-na-sayti-ploshchi-valovi-zbory-ta-urozhaynist-silskohospodarskykh-kultur-1',publication_date:'2026-10-20',observation_date:'2026-10-01',geography:'UA',commodity:'grain_and_pulses_total',metric:'change_vs_same_date_previous_year',value:9.7,unit:'percent',period:'2026-10-01',basis:'yoy_same_date',status:'source_documented',usable_for_price_ranking:false},
 {id:'ua-harvest-wheat-yoy-2026-10-01',source_name:'Держстат України',source_kind:'official_primary',source_url:'https://stat.gov.ua/uk/news/nove-na-sayti-ploshchi-valovi-zbory-ta-urozhaynist-silskohospodarskykh-kultur-1',publication_date:'2026-10-20',observation_date:'2026-10-01',geography:'UA',commodity:'wheat',metric:'change_vs_same_date_previous_year',value:11.8,unit:'percent',period:'2026-10-01',basis:'yoy_same_date',status:'source_documented',usable_for_price_ranking:false},
 {id:'world-corn-ending-stocks-2026-27-oct',source_name:'GrainsPrices (переказ оцінок USDA)',source_kind:'secondary_report',source_url:'https://grainsprices.com/usda',publication_date:'2026-10-09',observation_date:'2026-10-09',geography:'WORLD',commodity:'corn',metric:'ending_stocks_forecast',value:280.440,unit:'million_metric_tonnes',period:'2026/27',basis:'usda_october_2026_report_as_republished',status:'secondary_needs_official_crosscheck',usable_for_price_ranking:false},
 {id:'world-wheat-ending-stocks-2026-27-oct',source_name:'GrainsPrices (переказ оцінок USDA)',source_kind:'secondary_report',source_url:'https://grainsprices.com/usda',publication_date:'2026-10-09',observation_date:'2026-10-09',geography:'WORLD',commodity:'wheat',metric:'ending_stocks_forecast',value:276.038,unit:'million_metric_tonnes',period:'2026/27',basis:'usda_october_2026_report_as_republished',status:'secondary_needs_official_crosscheck',usable_for_price_ranking:false},
 {id:'world-soy-ending-stocks-2026-27-oct',source_name:'GrainsPrices (переказ оцінок USDA)',source_kind:'secondary_report',source_url:'https://grainsprices.com/usda',publication_date:'2026-10-09',observation_date:'2026-10-09',geography:'WORLD',commodity:'soybeans',metric:'ending_stocks_forecast',value:124.278,unit:'million_metric_tonnes',period:'2026/27',basis:'usda_october_2026_report_as_republished',status:'secondary_needs_official_crosscheck',usable_for_price_ranking:false}
]);
export function validateFacts(facts=FACTS){
 const ids=new Set();
 for(const f of facts){
  if(!f.id||ids.has(f.id))throw Error('duplicate_or_missing_id');ids.add(f.id);
  if(!Number.isFinite(f.value)||f.value<0)throw Error('invalid_value');
  if(!/^https:\/\//.test(f.source_url))throw Error('missing_provenance');
  for(const d of [f.publication_date,f.observation_date]){if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||new Date(d+'T00:00:00Z').toISOString().slice(0,10)!==d)throw Error('invalid_date');}
  if(f.usable_for_price_ranking!==false)throw Error('reference_facts_not_trade_quotes');
  if(!['official_primary','secondary_report'].includes(f.source_kind))throw Error('invalid_source_kind');
 }
 return true;
}
export function queryFacts({commodity='',sourceKind=''}={}){return FACTS.filter(f=>(!commodity||f.commodity===commodity)&&(!sourceKind||f.source_kind===sourceKind));}
