// Pure functions for testing and browser usage. Nothing here certifies quotes or costs.
export function destination(o){
const p=String(o?.point||'').trim(),r=String(o?.region||'').trim();
const map={'Ізмаїл':'Ізмаїл','м. Ізмаїл':'Ізмаїл','Рені':'Рені','Одеса':'Одеса','м. Київ':'Київ','Ярмолинці':'Ярмолинці','м.Васильків':'Васильків','Орлівка':'Орлівка','Золочів':'Золочів','Хацьки':'Хацьки','Рівне':'Рівне','Черкаси':'Черкаси'};
return r&&Object.hasOwn(map,p)?map[p]:null;
}
export function compareScenario(offers,routes,rate){
const ranked=[],missing=[];const valid=Number.isFinite(rate)&&rate>0&&rate<=100;
for(const o of offers){const city=destination(o);const route=routes.find(x=>x.city===city&&x.region===o.region&&Number.isFinite(x.km)&&x.km>0&&x.status==='planning_city_to_city');
if(!route||!valid){if(!route)missing.push({...o,city});continue}
const freight=route.km*rate;ranked.push({...o,city,km:route.km,freight,remainder:o.price-freight});
}
ranked.sort((a,b)=>b.remainder-a.remainder||a.km-b.km||a.company.localeCompare(b.company,'uk'));return {ranked,missing};
}
export function breakEvenRate(a,b){const deltaKm=a.km-b.km;return deltaKm===0?null:(a.price-b.price)/deltaKm}
