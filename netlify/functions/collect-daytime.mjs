import { collect } from './_collector.mjs';
export default async () => {const result = await collect('daytime');console.log('daytime status',result.status,result.last_success,result.last_errors);};
// 10:00 / 14:00 UTC; no crop/fuel alerts until specific adapters are added.
export const config = { schedule: '0 10,14 * * *' };
