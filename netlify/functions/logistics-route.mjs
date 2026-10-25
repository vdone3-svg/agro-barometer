import {chooseHit,validCity,distanceKm} from './_route_v121.mjs';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'};
const send=(value,status=200)=>new Response(JSON.stringify(value),{status,headers});
const base='https://graphhopper.com/api/1';
async function jsonAt(url){const ctl=new AbortController();const timeout=setTimeout(()=>ctl.abort(),8000);try{const response=await fetch(url,{signal:ctl.signal});if(!response.ok)throw Error('provider_http_'+response.status);return await response.json();}finally{clearTimeout(timeout);}}
async function geo(q,key){const url=new URL(base+'/geocode');url.searchParams.set('q',q);url.searchParams.set('limit','6');url.searchParams.set('locale','uk');url.searchParams.set('key',key);return (await jsonAt(url)).hits||[];}
export default async request=>{
 if(request.method!=='GET')return send({error:'method_not_allowed'},405);
 const q=new URL(request.url),city=q.searchParams.get('city'),region=q.searchParams.get('region')||'';
 if(!validCity(city)||region.length>85||(!region.match(/^[\p{L} .’'\-]*$/u)))return send({error:'invalid_or_ambiguous_city'},400);
 const key=process.env.GRAPHHOPPER_API_KEY;
 if(!key)return send({status:'not_configured',source:'GraphHopper Directions API',message:'Додайте GRAPHHOPPER_API_KEY у Netlify. Відстань не вигадується.'});
 try{
  const origin=chooseHit(await geo('Олександрія, Кіровоградська область, Україна',key),{city:'Олександрія',region:'Кіровоградська'});
  const dest=chooseHit(await geo([city,region,'Україна'].filter(Boolean).join(', '),key),{city,region});
  if(!origin||!dest)return send({status:'ambiguous_location',city,region,message:'Постачальник геокодування не підтвердив однозначний населений пункт. Не використовувати для розрахунку.'});
  const url=new URL(base+'/route');for(const p of [origin.point,dest.point])url.searchParams.append('point',`${p.lat},${p.lng}`);
  url.searchParams.set('profile','car');url.searchParams.set('calc_points','false');url.searchParams.set('instructions','false');url.searchParams.set('key',key);
  const data=await jsonAt(url),km=distanceKm(data);
  if(!km)return send({status:'route_unavailable',city,region});
  return send({status:'route_estimate',origin:'Олександрія, Кіровоградська область',city,region,km,provider:'GraphHopper',profile:'car',verified_for_grain_truck:false,notes:'Відстань між центрами міст за автомобільним профілем car. Не перевірено обмеження для вантажних авто, фактичний пункт доставки й актуальні перекриття.'});
 }catch(e){return send({status:'provider_unavailable',message:'Джерело маршруту тимчасово недоступне; кілометраж не підставляється.'},502)}
};
