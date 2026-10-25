import {FOCUS_CROPS,interpretPriceBarometer} from './agro-market-decision-v13.mjs';
const root=document.getElementById('agro-v13-decision-items'),status=document.getElementById('agro-v13-decision-status');
// Cross-version aliases are explicit: never silently replace one crop with another.
const ALIASES={wheat:['wheat'],corn:['corn','maize'],sunflower:['sunflower'],barley:['barley'],soybeans:['soybeans','soy'],rapeseed:['rapeseed','canola']};
function show(){
 const snapshot=window.AGRO_V13_HISTORICAL_SNAPSHOT;if(!snapshot){status.textContent='Історичні дані поки не завантажені.';return;}
 root.replaceChildren();let valid=0;
 for(const [key,label] of FOCUS_CROPS){
  const item=snapshot.items?.find(it=>ALIASES[key].includes(it.id)&&it.kind==='crop');
  const decision=interpretPriceBarometer(item||{});if(decision.score!==null)valid++;
  const article=document.createElement('article');article.style.cssText='border:1px solid #d5e5d9;border-radius:10px;padding:12px';
  const title=document.createElement('strong');title.textContent=label;article.append(title);
  const score=document.createElement('p');score.style.cssText='font-size:20px;font-weight:700;margin:8px 0';score.textContent=decision.score===null?'— / 100':`${decision.score} / 100`;article.append(score);
  const signal=document.createElement('p');signal.style.margin='6px 0';signal.textContent=decision.signal;article.append(signal);
  const reason=document.createElement('small');reason.textContent=decision.reason;article.append(reason);root.append(article);
 }
 status.textContent=`Історичних цінових оцінок для 6 культур достатньо: ${valid} із 6. Висновки за новинами не підміняють цінові шкали.`;
}
document.addEventListener('agro-v13-historical-updated',show);show();
