import {assessSales} from './agro-economic-core-v12.mjs';
const $=id=>document.getElementById(id);
const status=$('v12-status'),summary=$('v12-summary'),tbody=$('v12-rows'),review=$('v12-review'),select=$('v12-crop');
let offers=[],routes=[],freight=[];
const fmt=n=>new Intl.NumberFormat('uk-UA',{maximumFractionDigits:2}).format(n);
function cell(tr,str){const td=document.createElement('td');td.textContent=str;td.style.cssText='padding:8px;border-bottom:1px solid #e1ece4';tr.append(td)}
function render(){
 const filtered=offers.filter(x=>x.product===select.value);
 const result=assessSales(filtered,routes,freight);
 tbody.replaceChildren();
 for(const x of result.ranked){const tr=document.createElement('tr');cell(tr,x.offer.company+' · '+x.city);cell(tr,fmt(x.offer.price)+' грн/т');cell(tr,fmt(x.freight)+' грн/т');cell(tr,fmt(x.net)+' грн/т');tbody.append(tr)}
 if(!result.ranked.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=4;td.style.padding='12px';td.textContent='Зараз немає підтверджених даних для економічного рейтингу — пропозиції не приховуються як невигідні.';tr.append(td);tbody.append(tr)}
 summary.textContent=`Допущено до розрахунку: ${result.summary.eligible}. На перевірку: ${result.summary.needs_review}. Архівних оголошень: ${result.summary.archival}.`;
 const reasons=new Map();for(const x of result.review)for(const why of x.reasons)reasons.set(why,(reasons.get(why)||0)+1);
 review.replaceChildren();for(const [why,count] of reasons){const li=document.createElement('li');li.textContent=`${why}: ${count}`;review.append(li)}
}
select.addEventListener('change',render);
try{
 const resp=await Promise.all([fetch('/.netlify/functions/public-indicators',{cache:'no-store'}),fetch('/data/logistics-city-routes-v8.json',{cache:'no-store'}),fetch('/.netlify/functions/freight-rates',{cache:'no-store'})]);
 if(resp.some(r=>!r.ok))throw Error('Один із трьох API недоступний');
 const [market,map,freightData]=await Promise.all(resp.map(r=>r.json()));
 const grain=market.sources?.find(s=>s.id==='grain');
 offers=(grain?.data?.offers||[]).filter(o=>o.kind==='grain'&&o.currency==='UAH'&&o.price>0);
 routes=map.routes||[];freight=freightData.records||[];
 const names=[...new Set(offers.map(o=>o.product))].sort((a,b)=>a.localeCompare(b,'uk'));select.replaceChildren();for(const name of names){const op=document.createElement('option');op.value=name;op.textContent=name;select.append(op)}
 status.textContent=`Завантажено ${offers.length} гривневих кандидатів та ${freight.length} записів транспортних ставок. Схвалених для розрахунку: ${freightData.approved_for_automatic_pricing||0}.`;render();
}catch(err){status.textContent='Не вдалося отримати дані: '+err.message;summary.textContent='Висновки не формуються при помилці завантаження.'}
