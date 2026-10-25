import { collect } from './_collector.mjs';
import { collectPublicSources } from './_public_sources.mjs';
export default async () => {const result = await collect('morning');
try{const sources=await collectPublicSources('morning');console.log('indicators',sources.sources.map(s=>s.id+':'+s.status).join(','));}catch(err){console.error('noncritical indicators collection error',String(err));}console.log('morning status',result.status,result.last_success,result.last_errors);};
// 04:35 UTC = 06:35 Kyiv winter / 07:35 Kyiv summer — both before 08:00.
export const config = { schedule: '35 4 * * *' };
