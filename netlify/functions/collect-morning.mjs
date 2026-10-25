import { collect } from './_collector.mjs';
export default async () => {const result = await collect('morning');console.log('morning status',result.status,result.last_success,result.last_errors);};
// 04:35 UTC = 06:35 Kyiv winter / 07:35 Kyiv summer — both before 08:00.
export const config = { schedule: '35 4 * * *' };
