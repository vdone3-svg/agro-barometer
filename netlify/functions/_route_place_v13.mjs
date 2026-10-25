import {normalize} from './_route_v121.mjs';
export function validAddressPart(value,max=110){return typeof value==='string'&&value.trim().length>=3&&value.trim().length<=max&&!/[<>\x00-\x1f{}\\]/.test(value)}
export function chooseExactPlace(hits=[],{city,region,address}={}){
 const normalizedCity=normalize(city),streetPart=normalize(address).replace(/\b(вул\.?|вулиця|street|st\.)\b/g,'').trim();
 const matching=hits.filter(h=>{
  const country=String(h?.countrycode||h?.country_code||'').toLowerCase();
  const cityMatch=[h.city,h.locality,h.name].some(v=>normalize(v)===normalizedCity);
  const regionMatch=!region||normalize(h.state||'').includes(normalize(region).replace(/\s*обл(?:асть|\.)?$/u,''));
  const street=normalize(h.street||'');
  const hasNumber=/\d/.test(address);
  const number=String(h.housenumber||'');
  const numberMatch=!hasNumber||Boolean(number&&normalize(address).includes(normalize(number)));
  return country==='ua'&&cityMatch&&regionMatch&&street&&streetPart.includes(street)&&numberMatch&&Number.isFinite(h.point?.lat)&&Number.isFinite(h.point?.lng);
 });
 return matching.length===1?matching[0]:null;
}
