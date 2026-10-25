const $ = id => document.getElementById(id);
const status=$('v7-status'),product=$('v7-product'),offer=$('v7-offer'),km=$('v7-km'),rate=$('v7-rate'),result=$('v7-result');
let rows=[];
const fmt=n=>new Intl.NumberFormat('uk-UA',{maximumFractionDigits:2}).format(n);
function fill(node, values, label){node.replaceChildren();for(const [value,text] of values){const op=document.createElement('option');op.value=value;op.textContent=text;node.append(op)}if(!values.length){const op=document.createElement('option');op.value='';op.textContent=label;node.append(op)}}
function refreshOffers(){const selected=product.value;const matches=rows.filter(r=>r.product===selected);fill(offer,matches.map((r,i)=>[String(i),`${r.company} · ${r.point} · ${fmt(r.price)} грн · ${r.quote_date}`]),'Немає доступних пропозицій');compute()}
function compute(){const matches=rows.filter(r=>r.product===product.value);const r=matches[Number(offer.value)];result.replaceChildren();if(!r){result.textContent='Оберіть культуру та пропозицію.';return}
const header=document.createElement('div');header.textContent=`${r.company} · ${r.product} · ${r.point} (${r.region}); ${r.quote_date} · НЕ ПІДТВЕРДЖЕНО`;
result.append(header);
const valueKm=km.value.trim(),valueRate=rate.value.trim();if(valueKm===''||valueRate===''){const p=document.createElement('p');p.textContent='Вкажи перевірену відстань і тариф, щоб побачити умовний сценарій.';result.append(p);return}
const k=Number(valueKm),t=Number(valueRate);if(!Number.isFinite(k)||!Number.isFinite(t)||k<0||t<0||k>3000||t>100){const p=document.createElement('p');p.textContent='Перевір відстань і тариф: вони не можуть бути від’ємними.';result.append(p);return}
const cost=k*t;const p=document.createElement('p');p.style.fontWeight='700';p.textContent=`Умовні витрати: ${fmt(cost)} грн/т · умовний залишок: ${fmt(r.price-cost)} грн (за припущення грн/т)`;result.append(p);
const warn=document.createElement('p');warn.style.color='#835a12';warn.textContent='Порівняння орієнтовне: одиниця ціни, ПДВ і базис невідомі. Це не визначення найвигіднішого покупця.';result.append(warn)}
product.addEventListener('change',refreshOffers);offer.addEventListener('change',compute);km.addEventListener('input',compute);rate.addEventListener('input',compute);
try{const response=await fetch('/.netlify/functions/public-indicators?v7='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);const body=await response.json();const grain=(body.sources||[]).find(s=>s.id==='grain');rows=(grain?.data?.offers||[]).filter(r=>r.kind==='grain'&&r.currency==='UAH'&&r.verification==='unverified'&&typeof r.price==='number'&&r.price>0&&r.company&&r.point&&r.product&&r.quote_date&&r.freshness!=='archival_unverified');
const products=[...new Set(rows.map(r=>r.product))].sort((a,b)=>a.localeCompare(b,'uk'));fill(product,products.map(x=>[x,x]),'Немає доступних гривневих пропозицій');status.textContent=`Завантажено ${rows.length} непідтверджених гривневих оголошень із читального API. Архівні старші 30 днів не включено до вибору. За базисом і ПДВ вони непорівнянні.`;refreshOffers()
}catch(err){status.textContent='Не вдалося прочитати API: '+err.message;fill(product,[],'Немає даних');fill(offer,[],'Немає даних');result.textContent='Перевір API public-indicators та інтернет-з’єднання.'}
