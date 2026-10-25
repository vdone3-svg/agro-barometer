import {parseRss,summarizeNews} from './_news_digest_v13.mjs';
import {ACTIVE_FEEDS,SOURCE_CATALOG} from './_news_sources_v13.mjs';
const FEEDS=ACTIVE_FEEDS.map(f=>({source:f.name,publisher:f.publisher,url:f.url,host:f.host}));
const headers={'content-type':'application/json; charset=utf-8','cache-control':'public, max-age=0, s-maxage=1800'};
export default async ()=>{
 const results=await Promise.all(FEEDS.map(async f=>{
  const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),6500);
  try{const res=await fetch(f.url,{signal:ctrl.signal,headers:{'Accept':'application/rss+xml, application/xml, text/xml'}});
   if(!res.ok)throw Error('HTTP '+res.status);const xml=await res.text();return {source:f.source,publisher:f.publisher,ok:true,items:parseRss(xml,f.source,f.host)};
  }catch{return {source:f.source,publisher:f.publisher,ok:false,items:[]}}finally{clearTimeout(timer)}
 }));
 const digest=summarizeNews(results.flatMap(r=>r.items));
 const live=results.some(r=>r.ok)&&digest.articles_total>0;
 const payload={schema_version:1,status:live?'news_context_available':'news_unavailable',generated_at:new Date().toISOString(),window_days:14,sources:results.map(({source,publisher,ok,items})=>({source,publisher,ok,count:items.length})),source_catalog:{publishers_total:new Set(SOURCE_CATALOG.map(x=>x.publisher)).size,configured_rss:ACTIVE_FEEDS.length,awaiting_integration:SOURCE_CATALOG.filter(x=>x.mode!=='rss_configured_not_live_verified').length},...digest,notice:'Новини — контекст, не котирування. Відсутність новин не означає відсутність змін на ринку. Немає підтвердженої причинності або сигналу купівлі/продажу.'};
 return new Response(JSON.stringify(payload),{status:200,headers});
};
