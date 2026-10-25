// Pure functions shared with automated tests.
export function groupOffers(rows){
 const m=new Map();for(const r of rows||[]){if(!r?.identity||!Number.isFinite(r.price))continue;
 if(!m.has(r.identity))m.set(r.identity,{identity:r.identity,company:r.company,product:r.product,point:r.point,kind:r.kind,currency:r.currency});}
 return [...m.values()].sort((a,b)=>(a.company+' '+a.product).localeCompare(b.company+' '+b.product,'uk'));
}
export function seriesFor(rows,identity){
 const relevant=(rows||[]).filter(r=>r.identity===identity&&Number.isFinite(r.price)&&/^20\d\d-\d\d-\d\d$/.test(r.quote_date||''));
 // One value per quote date; if source publishes multiple prices on one day prefer the latest observation.
 const dates=new Map();for(const r of relevant.sort((a,b)=>(a.first_seen_at||'').localeCompare(b.first_seen_at||'')))dates.set(r.quote_date,r);
 return [...dates.values()].sort((a,b)=>a.quote_date.localeCompare(b.quote_date));
}
export function priceDelta(a,b){
 if(!a||!b||a.identity!==b.identity||a.currency!==b.currency||a.quote_date===b.quote_date)return null;
 return Number.isFinite(a.price)&&Number.isFinite(b.price)?b.price-a.price:null;
}
