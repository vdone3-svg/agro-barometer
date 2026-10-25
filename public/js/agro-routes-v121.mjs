import {destination} from './agro-decision-core-v9.mjs';
const $=id=>document.getElementById(id), city=$('v121-city'),region=$('v121-region'),out=$('v121-status'),btn=$('v121-check'),tariff=$('v121-freight');
const fmt=n=>new Intl.NumberFormat('uk-UA',{maximumFractionDigits:1}).format(n);
try{
 const [market,freight]=await Promise.all([fetch('/.netlify/functions/public-indicators').then(r=>r.json()),fetch('/.netlify/functions/freight-rates').then(r=>r.json())]);
 const offers=market.sources?.find(x=>x.id==='grain')?.data?.offers||[];
 const seen=new Set();for(const o of offers){const value=destination(o);if(!value)continue;const key=value+'|'+o.region;if(seen.has(key))continue;seen.add(key);const option=document.createElement('option');option.value=key;option.textContent=value+' · '+o.region;city.append(option)}
 tariff.textContent=`Тарифна база: ${freight.records_total||0} спостережень, ${freight.approved_for_automatic_pricing||0} схвалено для моделі. Автоматична середня ставка не публікується без порівнюваних даних.`;
}catch{tariff.textContent='Неможливо завантажити пропозиції або тарифну базу.'}
city.addEventListener('change',()=>{const [c,r]=city.value.split('|');region.textContent=r||'—';out.textContent='Натисніть «Розрахувати маршрут»; жодна відстань не підставляється без відповіді маршрутизатора.';});
btn.addEventListener('click',async()=>{
 const [c,r]=city.value.split('|');if(!c){out.textContent='Спочатку оберіть населений пункт.';return;}
 btn.disabled=true;out.textContent='Запит до маршрутизатора…';
 try{const url=new URL('/.netlify/functions/logistics-route',location.origin);url.searchParams.set('city',c);url.searchParams.set('region',r||'');const response=await fetch(url);const data=await response.json();
  if(data.status==='route_estimate')out.textContent=`${c}: ${fmt(data.km)} км (GraphHopper, профіль легкового автомобіля). Не підтверджено для 25-тонного зерновоза. Тариф не підставляється; економічна рекомендація не формується.`;
  else if(data.status==='not_configured')out.textContent='GraphHopper ще не підключений. У Netlify потрібна змінна GRAPHHOPPER_API_KEY. Жодних кілометрів не вигадано.';
  else out.textContent='Немає надійної відстані: '+(data.message||data.status||data.error||'невідома помилка');
 }catch{out.textContent='Помилка доступу до сервера маршрутизації. Відстань не визначено.'}finally{btn.disabled=false}
});
