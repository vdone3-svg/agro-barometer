// Only describe evidence availability; never generate a trading score from counts.
export const CULTURES=['wheat','corn','sunflower','barley','soy','rapeseed'];
const validDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s+'T00:00:00Z'))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
function daysAgo(iso,now){
 const value=typeof iso==='string'?Date.parse(iso):NaN;
 if(!Number.isFinite(value))return null;
 const day=Math.floor((now.getTime()-value)/86400000);
 return day>=0?day:null;
}
const uniq=values=>[...new Set(values.filter(Boolean))];
export function summarizeCoverage({usda=null,eu=null,usdaHealth=null,euHealth=null,now=new Date()}={}){
 const usdaRows=Array.isArray(usda?.records)?usda.records:[];
 const euRows=Array.isArray(eu?.rows)?eu.rows:[];
 return {
  schema_version:1,
  generated_at:now.toISOString(),
  ready_for_trade_decision:false,
  sources:{
   usda_psd:{status:usdaHealth?.status||'unknown',last_success:usdaHealth?.last_success||null,records:usdaRows.length,kind:'world_and_ukraine_supply_demand'},
   eu_dg_agri:{status:euHealth?.status||'unknown',last_success:euHealth?.last_success||null,records:euRows.length,kind:'european_wholesale_cereal_prices'}
  },
  crops:CULTURES.map(crop=>{
   const balances=usdaRows.filter(r=>r?.crop===crop&&Number.isFinite(Number(r.value))&&Number(r.value)>=0&&Number.isInteger(Number(r.market_year))&&r?.scope&&r?.attribute&&r?.unit);
   const prices=euRows.filter(r=>r?.crop===crop&&validDay(r.period_start)&&Number.isFinite(Number(r.price_eur_per_tonne))&&Number(r.price_eur_per_tonne)>0);
   const dates=prices.map(r=>r.period_start).sort();
   const latest=dates.at(-1)||null;
   const years=uniq(balances.map(r=>String(r.market_year))).sort();
   const coverage={crop,usda:{records:balances.length,market_years:years,scopes:uniq(balances.map(r=>r.scope)),attributes:uniq(balances.map(r=>r.attribute)).length},eu_prices:{records:prices.length,latest_period_start:latest,latest_age_days:latest?daysAgo(latest,now):null,countries:uniq(prices.map(r=>r.member_state)).length},ukrainian_buyer_quotes: 'not_covered_by_these_sources',freight_oleksandriia:'not_covered_by_these_sources',analysis_status:'context_only'};
   return coverage;
  }),
  limitations:['Official data series are context, not actual offers to buy from Oleksandriia.','Data counts are not independent confirmations or a recommendation score.','A successful prior collection does not guarantee current API availability.']
 };
}
