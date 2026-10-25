import { getStore } from '@netlify/blobs';

const URL = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json';
const allowed = ['USD', 'EUR'];

export async function collect(label = 'scheduled') {
  const now = new Date().toISOString();
  const store = getStore({ name: 'agro-public-market', consistency: 'strong' });
  const previous = await store.get('latest', { type: 'json' }).catch(() => null);
  const errors = [];
  let fx = {};
  let status = 'failed';
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let response;
    try { response = await fetch(URL, {signal:controller.signal,headers: {'Accept':'application/json','User-Agent':'AGRO-BAROMETER/1.0'}}); }
    finally {clearTimeout(timeout);}
    if(!response.ok) throw new Error('NBU HTTP '+response.status);
    const rows = await response.json();
    if(!Array.isArray(rows)) throw new Error('Unexpected NBU response shape');
    for(const code of allowed) {
      const row = rows.find(x=>x.cc===code && Number.isFinite(Number(x.rate)) && Number(x.rate)>0 && /^\d{2}\.\d{2}\.\d{4}$/.test(x.exchangedate || ''));
      if(row) fx[code] = {rate:Number(row.rate),effective_date:row.exchangedate,source_url:URL};
      else errors.push('Missing '+code+' in NBU response');
    }
    status = Object.keys(fx).length===allowed.length?'ok':'partial';
    if(!Object.keys(fx).length)throw new Error('No valid currency quotes');
  } catch(err) {errors.push(String(err?.message || err).slice(0,250));}
  // A failed job NEVER stamps historical data as current or overwrites the last successful quote.
  const out = {
    schema_version: 1,
    last_attempt: now,
    last_success: Object.keys(fx).length?now:(previous?.last_success||null),
    status,
    fx: Object.keys(fx).length?fx:(previous?.fx||{}),
    last_errors: errors,
    run: label,
    scheduled_timezone: 'Europe/Kyiv',
    note:'NBU exchange rates only. No automatic crop, fertilizer or fuel quotes yet.'
  };
  await store.setJSON('latest', out);
  return out;
}
