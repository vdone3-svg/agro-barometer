import {interviewOverview} from './agro-v13-policy.mjs';
import {evaluateV13,CROPS_V13} from './agro-economics-core-v13.mjs';
import {adaptPublicOffer,aggregateReasons,freightQualityReport} from './agro-v13-adapter.mjs';
const $=id=>document.getElementById(id);
const status=$('v13-status'),cropSelect=$('v13-crop'),summary=$('v13-summary'),freightStatus=$('v13-freight-status'),review=$('v13-review'),offersTable=$('v13-offers'),ranked=$('v13-ranked');
const fmt=new Intl.NumberFormat('uk-UA');
let adapted=[],rates=[],problems=[];
function addLine(container,text){const li=document.createElement('li');li.textContent=text;container.append(li)}
function td(tr,text){const el=document.createElement('td');el.textContent=String(text);el.style.cssText='padding:9px;border-bottom:1px solid #dce7e0;vertical-align:top';tr.append(el)}
function render(){
 const selected=adapted.filter(o=>o.crop===cropSelect.value);
 const result=evaluateV13(selected,rates,{today:new Date().toISOString().slice(0,10),vat_rate:null});
 summary.textContent=`${cropSelect.value}: ${selected.length} оголошень; підтверджений економічний рейтинг — ${result.summary.comparable}; перевірити — ${result.summary.review}; архів — ${result.summary.archived}. Непідтверджені ціни не відкидаються як невигідні.`;
 const overview=interviewOverview(selected,result);
 const overviewEl=$('v13-overview');
 overviewEl.textContent=`${cropSelect.value}: підтверджених економічних результатів ${overview.counts.verified}; перспективних непідтверджених ${overview.counts.promising}; окремих цінових сигналів для перевірки ${overview.counts.reviewPriority}; архівних ${overview.counts.archived}. Ринок: ${selected.length} записів у поточному виборі. Достовірність: підтверджений рейтинг формується лише після повної перевірки.`;
 const promising=$('v13-promising'),priority=$('v13-priority-review');promising.replaceChildren();priority.replaceChildren();
 for(const entry of overview.items.filter(x=>x.category==='promising_unconfirmed'||x.category==='needs_economic_engine').slice(0,12))addLine(promising,`${entry.offer.company} — ${entry.offer.original_product}; ${entry.offer.destination_city||'напрямок невідомий'}. Потребує перевірки: ${entry.reasons.slice(0,2).join('; ')}.`);
 if(!promising.children.length)addLine(promising,'Немає відкритих кандидатів у цій культурі.');
 for(const entry of overview.items.filter(x=>x.category==='review_priority').slice(0,10))addLine(priority,`${entry.offer.company}: ${entry.reasons.join('; ')}`);
 if(!priority.children.length)addLine(priority,'Порівнювані підтверджені цінові орієнтири поки не надані: система не оголошує ціни аномальними. Неуточнені умови залишаються у списку перевірки.');
 const reasons=aggregateReasons(result.review);review.replaceChildren();for(const [reason,count] of reasons.slice(0,9))addLine(review,`${reason} — ${count}`);
 if(!reasons.length)addLine(review,'Для цієї культури наразі немає активних кандидатів на перевірку.');
 offersTable.replaceChildren();
 for(const o of selected.slice(0,20)){
  const tr=document.createElement('tr');td(tr,o.company);td(tr,o.original_product);td(tr,o.destination_city||'Місто не визначено');td(tr,o.observed_quote_value==null?'—':`${fmt.format(o.observed_quote_value)} ${o.observed_quote_currency||''} (одиниця невідома)`);td(tr,'ПДВ / базис / якість / доставка — не підтверджені');offersTable.append(tr);
 }
 if(!selected.length){const tr=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=5;cell.textContent='Немає актуальних оголошень цієї культури.';cell.style.padding='12px';tr.append(cell);offersTable.append(tr)}
 ranked.replaceChildren();
 if(!result.ranked.length)addLine(ranked,'Жодного підтвердженого висновку. До рейтингу потраплятимуть тільки пропозиції з належними доказами.');
 else for(const row of result.ranked.slice(0,20))addLine(ranked,`${row.offer.company}: ${fmt.format(row.net_revenue_uah_per_tonne)} грн/т без ПДВ; порівнювати лише всередині групи ${row.comparison_group}`);
}
for(const c of CROPS_V13){const option=document.createElement('option');option.value=c;option.textContent=c[0].toLocaleUpperCase('uk-UA')+c.slice(1);cropSelect.append(option)}
cropSelect.addEventListener('change',render);
try{
 const responses=await Promise.all([fetch('/.netlify/functions/public-indicators',{cache:'no-store'}),fetch('/.netlify/functions/freight-rates',{cache:'no-store'})]);
 if(responses.some(r=>!r.ok))throw Error('Недоступне джерело даних');
 const [market,freight]=await Promise.all(responses.map(r=>r.json()));
 const originals=market.sources?.find(s=>s.id==='grain')?.data?.offers||[];
 adapted=originals.map(adaptPublicOffer).filter(Boolean);rates=Array.isArray(freight.records)?freight.records:[];
 const report=freightQualityReport(rates);
 status.textContent=`Отримано ${adapted.length} зернових оголошень із публічного джерела. Система не приписує їм підтверджені одиниці ціни, ПДВ або умови договору.`;
 freightStatus.textContent=`Транспортна база: ${report.total} спостережень; ${report.approved} позначено як схвалені; точні адреси доставки: ${report.exact_destination}. Жоден запис не отримує схвалення лише від завантаження в базу.`;
 cropSelect.value='кукурудза';render();
}catch(e){status.textContent='Перевірку зупинено: '+e.message;freightStatus.textContent='Тарифні дані недоступні — не формуємо економічний рейтинг.';summary.textContent='Не вдалося виконати оцінку.';addLine(ranked,'Рекомендації вимкнені через помилку завантаження.');}
const placeButton=$('v13-place-check'),placeStatus=$('v13-place-status');
placeButton.addEventListener('click',async()=>{
 const city=$('v13-place-city').value.trim(),region=$('v13-place-region').value.trim(),address=$('v13-place-address').value.trim();
 if(!city||!address){placeStatus.textContent='Потрібні місто та повна адреса термінала.';return}
 placeButton.disabled=true;placeStatus.textContent='Перевірка геокодування та маршруту…';
 try{
  const u=new URL('/.netlify/functions/logistics-place',location.origin);
  for(const [k,v]of Object.entries({city,region,address}))u.searchParams.set(k,v);
  const r=await fetch(u);const d=await r.json();
  if(d.status==='exact_address_car_estimate')placeStatus.textContent=`${d.km} км за профілем car — орієнтир до термінала. НЕ підтверджено для 25-тонного зерновоза і не використовується в рейтингу.`;
  else placeStatus.textContent=d.message||d.status||'Адресу не підтверджено, відстань не визначена.';
 }catch{placeStatus.textContent='Помилка доступу до API. Відстань не визначена.'}finally{placeButton.disabled=false}
});
