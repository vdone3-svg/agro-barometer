import {createHash} from 'node:crypto';
import {parseRss} from './_news_digest_v13.mjs';
import {ACTIVE_FEEDS} from './_news_sources_v13.mjs';

const keepDays=120, maxRecords=3500;
const msDay=86400000;
export function itemKey(item){
  return createHash('sha256').update(String(item.url)).digest('hex').slice(0,32);
}
export function mergeArchive(previous,feedResults,checkedAt=new Date().toISOString()){
  const now=Date.parse(checkedAt);
  if(!Number.isFinite(now))throw Error('Invalid checkedAt');
  const old=Array.isArray(previous?.articles)?previous.articles:[];
  const records=new Map();
  for(const i of old){
    const t=Date.parse(i.date);
    if(i.id&&Number.isFinite(t)&&t<=now+3600000&&now-t<=keepDays*msDay)records.set(i.id,i);
  }
  let added=0;
  const sourceChecks=[];
  for(const r of feedResults){
    sourceChecks.push({id:r.id,publisher:r.publisher,url:r.url,ok:!!r.ok,items:(r.items||[]).length,checked_at:checkedAt,error:r.ok?null:String(r.error||'unavailable').slice(0,120)});
    if(!r.ok)continue;
    for(const item of r.items||[]){
      if(!item?.url||!item?.title||!Number.isFinite(Date.parse(item.date)))continue;
      const t=Date.parse(item.date);
      if(t>now+3600000||now-t>keepDays*msDay)continue;
      const id=itemKey(item);
      if(!records.has(id)){added++;records.set(id,{id,title:item.title,url:item.url,source:r.publisher,date:item.date,first_seen_at:checkedAt});}
    }
  }
  const articles=[...records.values()].sort((a,b)=>Date.parse(b.date)-Date.parse(a.date)).slice(0,maxRecords);
  const checks=[...(Array.isArray(previous?.checks)?previous.checks:[]),...sourceChecks].slice(-300);
  const publishers=new Set(articles.map(a=>a.source));
  return {schema_version:1,kind:'news_archive_v13',updated_at:checkedAt,articles_total:articles.length,added_this_run:added,publishers_in_archive:publishers.size,latest_article_at:articles[0]?.date??null,articles,checks,last_checks:sourceChecks,note:'Headlines with dates and source links only. Not verified market prices or factual claims. No automatic effect on historical barometers or decision scores.'};
}
export async function fetchMarketFeeds(fetchImpl=fetch,now=Date.now()){
  return Promise.all(ACTIVE_FEEDS.map(async feed=>{
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),7000);
    try{
      const r=await fetchImpl(feed.url,{signal:controller.signal,headers:{accept:'application/rss+xml,application/xml,text/xml'}});
      if(!r.ok)throw Error('HTTP '+r.status);
      const body=await r.text();
      return {id:feed.id,publisher:feed.publisher,url:feed.url,ok:true,items:parseRss(body,feed.name,feed.host,now)};
    }catch(err){return {id:feed.id,publisher:feed.publisher,url:feed.url,ok:false,items:[],error:String(err?.message||err)};}
    finally{clearTimeout(timer);}
  }));
}
export function coverageReport(archive,now=new Date().toISOString()){
  const nowMs=Date.parse(now),recent=(archive?.articles||[]).filter(a=>nowMs-Date.parse(a.date)<=14*msDay&&nowMs>=Date.parse(a.date));
  const checks=archive?.last_checks||[];
  return {articles_14d:recent.length,independent_publishers_14d:new Set(recent.map(a=>a.source)).size,feeds_configured:ACTIVE_FEEDS.length,feeds_ok_last_run:checks.filter(x=>x.ok).length,failed_feeds:checks.filter(x=>!x.ok).map(x=>({id:x.id,error:x.error})),last_update:archive?.updated_at??null,warning:'Article counts measure media coverage, not data quality. Official numerical market data and live freight quotes are tracked separately.'};
}
