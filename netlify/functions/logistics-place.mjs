// Exact-address route preview only. Not certified for heavy goods vehicles.
import {validCity,chooseHit,distanceKm} from './_route_v121.mjs';
import {chooseExactPlace,validAddressPart} from './_route_place_v13.mjs';
const h={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'};
const send=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:h});
async function requestJSON(u){const controller=new AbortController();const t=setTimeout(()=>controller.abort(),9000);try{const r=await fetch(u,{signal:controller.signal});if(!r.ok)throw Error('provider_http_'+r.status);return r.json()}finally{clearTimeout(t)}}
const api='https://graphhopper.com/api/1';
async function geocode(q,key){const u=new URL(api+'/geocode');u.searchParams.set('q',q);u.searchParams.set('limit','10');u.searchParams.set('locale','uk');u.searchParams.set('key',key);return (await requestJSON(u)).hits||[]}
export default async request=>{
 if(request.method!=='GET')return send({error:'method_not_allowed'},405);
 const q=new URL(request.url),city=q.searchParams.get('city')||'',region=q.searchParams.get('region')||'',address=q.searchParams.get('address')||'';
 if(!validCity(city)||!validAddressPart(address)||region.length>85||!/^[\p{L} .’'\-]*$/u.test(region))return send({status:'invalid_address',message:'Вкажіть населений пункт, область і повну адресу термінала.'},400);
 const key=process.env.GRAPHHOPPER_API_KEY;
 if(!key)return send({status:'not_configured',message:'Потрібна змінна Netlify GRAPHHOPPER_API_KEY; відстань не вигадується.'});
 try{
  const origin=chooseHit(await geocode('Олександрія, Кіровоградська область, Україна',key),{city:'Олександрія',region:'Кіровоградська'});
  const dest=chooseExactPlace(await geocode([address,city,region,'Україна'].filter(Boolean).join(', '),key),{city,region,address});
  if(!origin||!dest)return send({status:'ambiguous_address',message:'Не вдалося однозначно геокодувати адресу термінала. Уточніть адресу або користуйтеся міським орієнтиром.'});
  const u=new URL(api+'/route');for(const p of [origin.point,dest.point])u.searchParams.append('point',`${p.lat},${p.lng}`);
  u.searchParams.set('profile','car');u.searchParams.set('calc_points','false');u.searchParams.set('instructions','false');u.searchParams.set('key',key);
  const km=distanceKm(await requestJSON(u));if(km===null)return send({status:'route_unavailable'});
  return send({status:'exact_address_car_estimate',origin:'Олександрія, Кіровоградська область',city,region,address,km,provider:'GraphHopper',profile:'car',verified_for_grain_truck:false,verified_for_economic_ranking:false,note:'Дорожня оцінка до однозначно знайденої адреси. Профіль car НЕ перевіряє обмеження для 25-тонного зерновоза і не є підтвердженим транспортним тарифом.'});
 }catch{return send({status:'provider_unavailable',message:'Маршрутизатор недоступний. Відстань не підставляється.'},502)}
};
