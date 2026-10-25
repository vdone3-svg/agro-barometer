import {getStore} from '@netlify/blobs';
import {fetchMarketFeeds,mergeArchive} from './_market_archive_v13.mjs';
// Netlify Scheduled Function; no public write API or admin token involved.
export default async ()=>{
 const now=new Date().toISOString();
 const observations=await fetchMarketFeeds();
 const store=getStore({name:'agro-market-evidence-v13',consistency:'strong'});
 const previous=await store.get('news-archive',{type:'json'}).catch(()=>null);
 const next=mergeArchive(previous,observations,now);
 await store.setJSON('news-archive',next);
 console.log('market archive',JSON.stringify({added:next.added_this_run,total:next.articles_total,feeds_ok:observations.filter(x=>x.ok).length}));
};
export const config={schedule:'20 5 * * *'};
