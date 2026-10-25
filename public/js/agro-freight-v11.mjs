const host=document.querySelector('#agro-freight-v11');
const status=host?.querySelector('#agro-freight-v11-status');
const tbody=host?.querySelector('tbody');
const cell=(tr,value)=>{const td=document.createElement('td');td.textContent=String(value??'—');td.style.padding='7px';td.style.borderBottom='1px solid #ddd';tr.appendChild(td);};
if(host&&status&&tbody){
 fetch('/.netlify/functions/freight-rates',{cache:'no-store'})
  .then(async r=>{if(!r.ok)throw Error(`API ${r.status}`);return r.json()})
  .then(data=>{
   const rows=Array.isArray(data.records)?data.records:[];
   status.textContent=rows.length?`У базі ${rows.length} спостережень. Перевірених для автоматичної моделі: ${data.approved_for_automatic_pricing||0}.`:'Реєстр створено. Поки немає підтверджених транспортних ставок. Вигадані значення не додаємо.';
   for(const r of rows.slice(0,20)){
    const tr=document.createElement('tr');cell(tr,r.observed_date);cell(tr,`${r.origin_city} → ${r.destination_city}`);cell(tr,r.distance_km);cell(tr,r.price_per_tonne_uah);cell(tr,r.vat_status);
    const td=document.createElement('td'),a=document.createElement('a');a.href=r.source_url;a.textContent=r.source_name;a.target='_blank';a.rel='noopener noreferrer';td.appendChild(a);tr.appendChild(td);tbody.appendChild(tr);
   }
  }).catch(()=>{status.textContent='Реєстр тимчасово недоступний. Перевір Netlify Functions → freight-rates.'});
}
