import {assessThreeHorizons} from './agro-horizons-v13.mjs';
const choices=[['wheat','Пшениця'],['corn','Кукурудза'],['sunflower','Соняшник'],['barley','Ячмінь'],['soy','Соя'],['rapeseed','Ріпак']];
const select=document.getElementById('v13-horizon-crop');
const root=document.getElementById('v13-horizon-cards');
const status=document.getElementById('v13-horizon-status');
for(const [id,name] of choices){const opt=document.createElement('option');opt.value=id;opt.textContent=name;select.append(opt)}
function observations(){
 // Later: load a documented, verified, normalized evidence API. Never infer direction from headlines.
 const source=window.AGRO_V13_VERIFIED_HORIZON_OBSERVATIONS;
 return Array.isArray(source)?source:[];
}
function render(){
 const result=assessThreeHorizons(select.value,observations());root.replaceChildren();
 for(const h of result.horizons){
  const card=document.createElement('article');card.style.cssText='border:1px solid #d5e5d9;border-radius:10px;padding:12px';
  const title=document.createElement('strong');title.textContent=h.label;
  const line=document.createElement('p');line.textContent=h.status;line.style.cssText='font-weight:600;margin:8px 0';
  const description=document.createElement('small');description.textContent=h.readiness;
  const details=document.createElement('p');details.style.margin='8px 0 0';details.textContent=`Підтверджені повідомлення: ${h.eligible_evidence}. Узгоджені фактори: ${h.corroborated_factors.length}.`;
  card.append(title,line,description,details);root.append(card);
 }
 status.textContent='Три горизонти аналізуються окремо. Немає каліброваного сигналу купівлі чи продажу.';
}
select.addEventListener('change',render);render();
