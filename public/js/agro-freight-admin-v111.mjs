const $=(id)=>document.getElementById(id);
const form=$('freight-form'),message=$('feedback'),save=$('submit-button');
const api='/.netlify/functions/freight-rates';
const today=new Date().toLocaleDateString('en-CA');
$('observed_date').max=today;
$('observed_date').value=today;
function feedback(text,error=false){message.textContent=text;message.className='feedback '+(error?'error':'success');}
async function refresh(){try{const r=await fetch(api,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const j=await r.json();$('record-count').textContent=String(j.records_total??'—');$('approved-count').textContent=String(j.approved_for_automatic_pricing??'—');}catch{$('record-count').textContent='Недоступно';$('approved-count').textContent='—';}}
$('refresh-button').addEventListener('click',refresh);
form.addEventListener('submit',async(event)=>{
 event.preventDefault();if(!form.reportValidity())return;
 const token=$('admin_token').value;
 const d=Object.fromEntries(new FormData(form).entries());
 const price=Number(d.amount),distance=Number(d.distance_km),tonnes=Number(d.load_tonnes);
 if(!Number.isFinite(price)||price<=0||!Number.isFinite(distance)||distance<=0||!Number.isFinite(tonnes)||tonnes<=0){feedback('Перевір числові поля.',true);$('admin_token').value='';return;}
 const record={source_name:d.source_name,source_url:d.source_url,observed_date:d.observed_date,origin_city:d.origin_city,destination_city:d.destination_city,distance_km:distance,load_tonnes:tonnes,vehicle_type:d.vehicle_type,cargo_type:d.cargo_type,payment_type:d.payment_type,vat_status:d.vat_status,evidence_status:d.evidence_status,notes:d.notes};
 record[d.price_basis==='trip'?'trip_price_uah':'price_per_tonne_uah']=price;
 // Never log/store/display the token or include it in JSON body or URL.
 $('admin_token').value='';save.disabled=true;feedback('Збереження…');
 try{
  const response=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({records:[record]}),cache:'no-store',credentials:'same-origin',referrerPolicy:'no-referrer'});
  const result=await response.json().catch(()=>({}));
  if(!response.ok){const hints={401:'Невірний токен.',503:'Функція запису недоступна або токен не налаштований.',409:'Такий ID уже існує з іншим вмістом.',400:'Помилка перевірки полів.',413:'Завеликий запит.'};throw Error((hints[response.status]||'Помилка збереження')+(result.detail?' '+result.detail:''));}
  feedback('Запис збережено. Кількість у базі: '+result.records_total+'. Це ще не підтверджений тариф для автоматичного рейтингу.');
  await refresh();
 }catch(err){feedback(err.message||'Не вдалося зберегти.',true)}finally{save.disabled=false;}
});
refresh();
