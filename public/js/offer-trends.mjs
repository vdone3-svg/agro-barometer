// Read-only visualization. Never modifies the 0–100 historical barometers.
import { groupOffers, seriesFor, priceDelta } from './offer-trends-core.mjs';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>Number(n).toLocaleString('uk-UA',{maximumFractionDigits:2});
const local=t=>t?new Date(t).toLocaleString('uk-UA',{timeZone:'Europe/Kyiv'}):'—';
let rows=[], groups=[];
function render(){
 const kind=$('v5-kind').value, select=$('v5-offer');const prev=select.value;
 const filtered=groups.filter(g=>kind==='all'||g.kind===kind);
 select.innerHTML=filtered.map(g=>`<option value="${esc(g.identity)}">${esc(g.company)} · ${esc(g.product)} · ${esc(g.point)} · ${esc(g.currency)}</option>`).join('');
 if(filtered.some(g=>g.identity===prev))select.value=prev;
 draw();
}
function draw(){
 const identity=$('v5-offer').value; const g=groups.find(g=>g.identity===identity);
 if(!g){$('v5-selected').textContent='Немає доступних спостережень';$('v5-chart').textContent='Історія порожня';$('v5-caveat').textContent='';$('v5-observations').innerHTML='';return;}
 const series=seriesFor(rows,identity),curr=series.at(-1),old=series.length>1?series.at(-2):null;
 const delta=old?priceDelta(old,curr):null;
 $('v5-selected').textContent=g.company+' · '+g.product+' · '+g.point+' · '+g.currency+' (одиниця не перевірена)';
 $('v5-caveat').textContent=series.length<2?'Є тільки одне спостереження. Зміну ціни поки неможливо визначити.':delta===null?'Для цієї пропозиції немає зіставної пари для зміни ціни.':'Зміна між двома останніми датованими оголошеннями: '+(delta>0?'+':'')+fmt(delta)+' '+g.currency+' (одиниця не перевірена). ПДВ і базис невідомі; це не підтверджена ринкова динаміка.';
 if(series.length<2){$('v5-chart').innerHTML='<div style="padding:32px 10px;text-align:center"><div style="font-size:26px;font-weight:800">'+fmt(curr.price)+' '+esc(curr.currency)+'</div><div style="font-size:12px;color:#65756a">Початкове спостереження · '+esc(curr.quote_date)+'</div><div style="font-size:12px">Для лінійного графіка потрібно щонайменше дві різні дати оголошень.</div></div>';}
 else {
  const prices=series.map(o=>o.price),lo=Math.min(...prices),hi=Math.max(...prices),w=800,h=190,pad=38;
  const xs=series.map((o,i)=>pad+(w-2*pad)*i/Math.max(1,series.length-1));
  const ys=series.map(o=>hi===lo?h/2:h-pad-(o.price-lo)*(h-2*pad)/(hi-lo));
  const line=xs.map((x,i)=>x.toFixed(1)+','+ys[i].toFixed(1)).join(' ');
  const dots=series.map((o,i)=>`<circle cx="${xs[i]}" cy="${ys[i]}" r="5" fill="#326d4d"><title>${esc(o.quote_date)} · ${fmt(o.price)} ${esc(o.currency)}</title></circle>`).join('');
  $('v5-chart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Історія датованих оголошень ${esc(g.product)} у ${esc(g.currency)}" style="display:block;width:100%;height:auto;max-height:220px"><line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#b9cabd"/><polyline points="${line}" fill="none" stroke="#326d4d" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${dots}<text x="${pad}" y="${h-9}" font-size="12" fill="#53685b">${esc(series[0].quote_date)}</text><text x="${w-pad}" y="${h-9}" text-anchor="end" font-size="12" fill="#53685b">${esc(curr.quote_date)}</text><text x="${pad}" y="18" font-size="12" fill="#53685b">${fmt(hi)} ${esc(g.currency)}</text><text x="${pad}" y="${h-pad-8}" font-size="12" fill="#53685b">${fmt(lo)}</text></svg>`;
 }
 $('v5-observations').innerHTML=series.slice().reverse().map(o=>`<tr style="border-bottom:1px solid #e3ebe5"><td style="padding:8px">${esc(o.quote_date)}</td><td>${esc(local(o.first_seen_at))}</td><td>${fmt(o.price)} ${esc(o.currency)}<div style="font-size:11px;color:#65756a">од. не перевірена</div></td><td style="color:#9b651c">Не підтверджено</td><td><a href="${esc(o.source_url)}" rel="noopener noreferrer" target="_blank">E-ZERNO</a></td></tr>`).join('');
}
async function refresh(){try{
 const res=await fetch('/.netlify/functions/offer-history?v='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);
 const data=await res.json();if(data.status==='error')throw Error('сховище недоступне');
 rows=Array.isArray(data.observations)?data.observations:[]; groups=groupOffers(rows);
 $('offer-history-summary').textContent=data.status==='not_started'?'Історія ще не почалася.':`Усього у сховищі: ${Number(data.total_observations||0)} · різних пропозицій: ${Number(data.total_distinct_offers||0)} · додано останнім збором: ${Number(data.added_this_run||0)} · остання перевірка журналу: ${local(data.updated_at)}`;
 render();
}catch(err){$('offer-history-summary').textContent='Не вдалося завантажити історію: '+err.message;}}
$('v5-kind').addEventListener('change',render);$('v5-offer').addEventListener('change',draw);
refresh();setInterval(()=>{if(!document.hidden)refresh()},300000);
