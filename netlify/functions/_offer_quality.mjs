// Shared fail-closed checks for newly scraped offers AND legacy archived observations.
// This detects obvious contamination, not commercial validity or actual delivery terms.
export function pointProblem(point) {
 const s=String(point??'').trim();
 if(!s || s.length>80) return 'missing_or_long_point';
 if(/[<>]|&(?:#|[a-z]+;)/i.test(s) || /[«»“”"]/.test(s)) return 'markup_or_company_quote';
 if(/(?:платиновий|золотий|срібний)\s+партнер|золоті\s+партнери|\bТОВ\b|\bФОП\b|\bAGROP\b|\bЦіни на\b/i.test(s)) return 'next_company_spillover';
 if(/(?:Соя|Горох(?:\s+жовтий)?|Жито|Амофос|Суперфосфат|Карбамід|Селітра|Нітроамофоска|Пшениця|Соняшник|Кукурудза|Ріпак|Ячмінь|КАС)\s+(?:(?:\d[\d\s]{2,})|\(|\bN:|\bP:)/i.test(s)) return 'next_product_spillover';
 if(/(?:ПРОДІНВЕСТ\s+СЕРВІС|Золоті\s+партнери|Елеватор\s+БК\s+Рошен)/i.test(s) && !/^Бориспіль Елеватор БК Рошен$/i.test(s)) return 'possible_next_listing';
 if(/\b(?:N|P|K|S):\s*\d/i.test(s)) return 'fertilizer_formula_spillover';
 return null;
}
export function offerProblem(o){
 if(!o || !['grain','fertilizer'].includes(o.kind))return 'bad_kind';
 if(!o.company || !o.product || !Number.isFinite(o.price) || o.price<=0)return 'incomplete';
 return pointProblem(o.point);
}
export function offerAgeDays(o,at=new Date()){
 const day=String(o?.quote_date??'');
 if(!/^20\d{2}-\d{2}-\d{2}$/.test(day))return null;
 const n=Date.parse(day+'T00:00:00Z');
 const now=Date.UTC(at.getUTCFullYear(),at.getUTCMonth(),at.getUTCDate());
 return Number.isFinite(n)?Math.floor((now-n)/86400000):null;
}
export function quoteFreshness(o,at=new Date()){
 const age=offerAgeDays(o,at);
 return age===null||age<0?'unknown':age<=7?'recent_unverified':age<=30?'older_unverified':'archival_unverified';
}

// Read-time protection is essential: already stored snapshots may have been collected by older parsers.
export function filterSourceOffers(source){
 if(!source || !['grain','fertilizer'].includes(source.id) || !source.data)return source;
 const original=Array.isArray(source.data.offers)?source.data.offers:[];
 const offers=original.filter(o=>!offerProblem({...o,kind:source.id})).map(o=>({...o,kind:source.id, freshness:quoteFreshness(o)}));
 const rejected=original.length-offers.length;
 const counts=source.id==='grain'?Object.fromEntries(['Соняшник','Кукурудза','Пшениця','Ячмінь','Ріпак'].map(name=>[name,offers.filter(o=>String(o.product||'').toLocaleLowerCase('uk').startsWith(name.toLocaleLowerCase('uk'))).length])):null;
 return {...source,data:{...source.data,offers,quality_control:{...source.data.quality_control,source_candidates:original.length,published_candidates:offers.length,hidden_malformed:rejected,filter:'unified_v62',note:'Read-time filter; candidate counts, not verified bids.'},...(counts?{crop_coverage:counts}:{})}};
}
