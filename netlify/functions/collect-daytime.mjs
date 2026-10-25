import { collect } from './_collector.mjs';
import { collectPublicSources } from './_public_sources.mjs';
export default async () => {const result = await collect('daytime');
try{const sources=await collectPublicSources('daytime');console.log('indicators',sources.sources.map(s=>s.id+':'+s.status).join(','));}catch(err){console.error('noncritical indicators collection error',String(err));}console.log('daytime status',result.status,result.last_success,result.last_errors);};
// 10:00 / 14:00 UTC; no crop/fuel alerts until specific adapters are added.
export const config = { schedule: '0 10,14 * * *' };
