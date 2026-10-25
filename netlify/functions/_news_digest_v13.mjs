// Source-linked headlines only; never infer price direction from an article title.
export const CROP_RULES=Object.freeze({
 'пшениця':/пшениц|wheat/i, 'кукурудза':/кукурудз|маїс|corn|maize/i,
 'соняшник':/соняшник|соняшников|sunflower/i,'ячмінь':/ячмен|ячмін|barley/i,
 'соя':/\bсо[яєїю]\b|соєв|сої|soybean|\bsoy\b/i,
 'ріпак':/ріпак|ріпаков|rapeseed|canola/i
});
const strip = s=>String(s??'').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g,'$1').replace(/<[^>]*>/g,' ').replace(/&(?:amp|lt|gt|quot|apos|nbsp|#39);/g, m=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'",'&nbsp;':' ','&#39;':"'"})[m]||m).replace(/\s+/g,' ').trim();
function element(block,tag){const m=block.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`,'i'));return m?strip(m[1]):'';}
export function parseRss(xml,source,allowedHost,now=Date.now()){
 if(typeof xml!=='string'||xml.length>1_500_000)throw Error('Invalid RSS payload');
 const result=[];
 for(const m of xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)){
  const title=element(m[1],'title'),link=element(m[1],'link'),description=element(m[1],'description'),dateRaw=element(m[1],'pubDate');
  const date=new Date(dateRaw),ms=date.getTime();let url;
  try{url=new URL(link)}catch{continue}
  if(!title||title.length<12||!Number.isFinite(ms)||url.protocol!=='https:'||!(url.hostname===allowedHost||url.hostname.endsWith('.'+allowedHost)))continue;
  if(ms>now+60*60*1000||now-ms>14*24*60*60*1000)continue;
  result.push({title:title.slice(0,240),url:url.toString(),source,date:date.toISOString(),excerpt:description.slice(0,320)});
  if(result.length>=80)break;
 }
 return result;
}
export function summarizeNews(items,{now=Date.now()}={}){
 const unique=new Map(),seenTitles=new Set();for(const i of items||[]){if(!i||!i.url)continue;const key=String(i.title||'').toLocaleLowerCase('uk-UA').replace(/[^\p{L}\p{N}]+/gu,' ').trim();if(unique.has(i.url)||(key.length>20&&seenTitles.has(key)))continue;unique.set(i.url,i);if(key.length>20)seenTitles.add(key)}
 const recent=Array.from(unique.values()).filter(i=>Number.isFinite(new Date(i.date).getTime())&&now-new Date(i.date).getTime()<=14*86400000&&new Date(i.date).getTime()<=now+3600000).sort((a,b)=>Date.parse(b.date)-Date.parse(a.date));
 const crops=Object.fromEntries(Object.keys(CROP_RULES).map(crop=>{
  const related=recent.filter(i=>CROP_RULES[crop].test(`${i.title} ${i.excerpt}`)).slice(0,3);
  return [crop,{count:related.length,independent_publishers:new Set(related.map(i=>{try{return new URL(i.url).hostname.replace(/^www\./,'')}catch{return i.source}})).size,articles:related.map(({title,url,date,source})=>({title,url,date,source})),summary:related.length?`За останні 14 днів у новинах про цю культуру: ${related.slice(0,2).map(x=>x.title.replace(/[.!?]+$/,'')).join('; ')}. Це важливо враховувати під час оцінки ринку, але самі новини не доводять, що ціна в Олександрії зросла чи впала.`:'За останні 14 днів у підключених джерелах не знайдено достатньо новин саме про цю культуру. Зміни ринку за цим сигналом визначити не можна.'}];
 }));
 return {crops,articles_total:recent.length,latest_at:recent[0]?.date||null};
}
