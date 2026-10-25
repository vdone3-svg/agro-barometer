// USD/metric tonne price series: never infer missing historical prices.
export const CROPS = Object.freeze({wheat:'Пшениця',corn:'Кукурудза',sunflower:'Соняшник',barley:'Ячмінь',soy:'Соя',rapeseed:'Ріпак'});
export const YEARS=[2022,2023,2024,2025,2026]; // rolling 5 calendar years incl current year
export function validObservation(row){
 if(!row||typeof row!=='object')return false;
 const date=String(row.month||''); if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(date))return false;
 const [y,m]=date.split('-').map(Number); if(y<2022||y>2026 || (y===2026&&m>10))return false;
 return Object.hasOwn(CROPS,row.crop)&&Number.isFinite(row.usd_per_tonne)&&row.usd_per_tonne>0&&row.currency==='USD'&&row.unit==='metric_tonne'&&['ukraine_local','world_benchmark'].includes(row.market)
 &&typeof row.source_url==='string'&&/^https:\/\//.test(row.source_url)
 &&typeof row.series_id==='string'&&row.series_id.trim().length>2
 &&typeof row.basis==='string'&&row.basis.trim().length>0
 &&typeof row.source_name==='string'&&row.source_name.trim().length>1;
}
export function selectSeries(rows,crop,market,seriesId,years){
 const included=new Set(years.map(Number));return (rows||[]).filter(validObservation).filter(r=>r.crop===crop&&r.market===market&&r.series_id===seriesId&&included.has(Number(r.month.slice(0,4)))).sort((a,b)=>a.month.localeCompare(b.month));
}
export function splitByYear(rows){const result={}; for(const r of rows){const year=Number(r.month.slice(0,4));result[year]??=[];result[year].push(r);}return result;}
export function coverage(rows,year){return new Set(rows.filter(r=>Number(r.month.slice(0,4))===year).map(r=>r.month)).size;}
export function rejectMixedSeries(rows){return new Set(rows.map(r=>r.series_id+'|'+r.basis+'|'+r.market)).size<=1;}
export function parseMonthlyCsv(text){const lines=String(text).replace(/^\uFEFF/,'').trim().split(/\r?\n/);const expected=['month','crop','market','series_id','basis','usd_per_tonne','currency','unit','source_name','source_url']; if(lines[0]!==expected.join(','))throw Error('Невірні колонки CSV'); const rows=[];for(let i=1;i<lines.length;i++){if(!lines[i].trim())continue;const parts=lines[i].split(',');if(parts.length!==expected.length)throw Error('CSV рядок '+(i+1)+': очікується 10 полів без ком');const row=Object.fromEntries(expected.map((k,j)=>[k,parts[j].trim()]));row.usd_per_tonne=Number(row.usd_per_tonne);if(!validObservation(row))throw Error('CSV рядок '+(i+1)+': невалідне спостереження');rows.push(row)}const keys=new Set();for(const r of rows){const k=[r.month,r.crop,r.market,r.series_id,r.basis].join('|');if(keys.has(k))throw Error('Повторення спостереження: '+k);keys.add(k)}return rows;}
