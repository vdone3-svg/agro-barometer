import {getStore} from '@netlify/blobs';
import {STORE} from './_usda_psd_v13.mjs';
import {MARKET_STORE} from './_eu_cereal_prices_v13.mjs';
import {summarizeCoverage} from './_source_coverage_v13.mjs';
export default async()=>{
 try{
  const usda=getStore({name:STORE,consistency:'strong'});
  const eu=getStore({name:MARKET_STORE,consistency:'strong'});
  const [usdaData,euData,usdaHealth,euHealth]=await Promise.all([
   usda.get('observations',{type:'json'}).catch(()=>null),
   eu.get('observations',{type:'json'}).catch(()=>null),
   usda.get('health',{type:'json'}).catch(()=>null),
   eu.get('health',{type:'json'}).catch(()=>null)
  ]);
  return Response.json(summarizeCoverage({usda:usdaData,eu:euData,usdaHealth,euHealth}),{headers:{'cache-control':'no-store'}});
 }catch(e){return Response.json({status:'unavailable',error:'numeric_coverage_unavailable'},{status:503,headers:{'cache-control':'no-store'}});}
};
