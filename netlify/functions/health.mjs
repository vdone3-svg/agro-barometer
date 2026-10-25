export default async () => Response.json({service:"AGRO BAROMETER",mode:"published-json",auto_collectors_enabled:false,updated_at:new Date().toISOString()},{headers:{"Cache-Control":"no-store"}});
export const config={path:"/api/health"};
