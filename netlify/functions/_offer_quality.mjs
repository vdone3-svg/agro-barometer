// Shared fail-closed checks for newly scraped offers AND legacy archived observations.
// This detects obvious contamination, not commercial validity or actual delivery terms.
export function pointProblem(point) {
 const s=String(point??'').trim();
 if(!s || s.length>80) return 'missing_or_long_point';
 if(/[<>]|&(?:#|[a-z]+;)/i.test(s) || /[«»“”"]/.test(s)) return 'markup_or_company_quote';
 if(/(?:платиновий|золотий|срібний)\s+партнер|золоті\s+партнери|\bТОВ\b|\bФОП\b|\bAGROP\b|\bЦіни на\b/i.test(s)) return 'next_company_spillover';
 if(/(?:Соя|Горох|Жито|Амофос|Суперфосфат|Карбамід|Селітра|Нітроамофоска|Пшениця|Соняшник|Кукурудза|Ріпак|Ячмінь|КАС)\s+(?:(?:\d[\d\s]{2,})|\(|\bN:|\bP:)/i.test(s)) return 'next_product_spillover';
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
