// Defensive API adapter. No coordinates are inferred or hardcoded; return unavailable rather than misleading km.
export const normalize = s => String(s||'').normalize('NFC').trim().toLocaleLowerCase('uk-UA').replace(/[’`]/g,"'").replace(/\s+/g,' ');
export function validCity(city){return typeof city==='string' && /^[\p{L}][\p{L} .’'\-]{1,69}$/u.test(city.trim());}
export function chooseHit(hits=[], {city,region=''}={}) {
  const target=normalize(city), reg=normalize(region).replace(/\s*обл\.?$/u,'');
  const matched=hits.filter(h=>{
    const c=normalize(h?.name);const country=String(h?.countrycode||h?.country_code||'').toLowerCase();
    const state=normalize(h?.state||'');
    return c===target && country==='ua' && (!reg || state.includes(reg));
  });
  return matched.length===1&&Number.isFinite(matched[0].point?.lat)&&Number.isFinite(matched[0].point?.lng)?matched[0]:null;
}
export function distanceKm(route){const metres=route?.paths?.[0]?.distance;return Number.isFinite(metres)&&metres>0&&metres<3000000?Math.round(metres/100)/10:null;}
