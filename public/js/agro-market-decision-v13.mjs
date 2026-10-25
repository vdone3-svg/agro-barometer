// Decision signal is a *separate interpretation* of the pre-existing 12-month percentile.
// It never rewrites the 11 historical barometers and never converts headlines into numeric evidence.
export const FOCUS_CROPS = Object.freeze([
  ['wheat','Пшениця'],['corn','Кукурудза'],['sunflower','Соняшник'],
  ['barley','Ячмінь'],['soybeans','Соя'],['rapeseed','Ріпак']
]);

export function interpretPriceBarometer({score,kind='crop',months,reason,sourceDate}={}) {
  if(kind!=='crop' && kind!=='fuel' && kind!=='fert') return {score:null,signal:'Недостатньо даних',certainty:'none',reason:'Невідомий тип товару'};
  if(!Number.isInteger(score)||score<0||score>100||!Number.isInteger(months)||months<8) {
    return {score:null,signal:'Недостатньо даних',certainty:'none',reason:reason||'Немає достатньої історії зіставних локальних цін'};
  }
  const higher = score>=65, lower=score<=35;
  const signal = kind==='crop' ? (higher?'Розглянути продаж':lower?'Не поспішати з продажем':'Спостерігати за ринком')
    : (higher?'Розглянути закупівлю':lower?'Не поспішати із закупівлею':'Спостерігати за ринком');
  return {score,signal,certainty:'historical_only',reason:'Оцінка лише історичної привабливості ціни. Новини, витрати на доставку та доступність пропозицій не підтверджують рішення.',sourceDate:sourceDate||null};
}

// The editorial layer only explains dated, source-linked events; it cannot fabricate a price score.
export function interpretWithNews(priceSignal,newsCrop){
  const count=Array.isArray(newsCrop?.articles)?newsCrop.articles.length:0;
  const publishers=Number.isInteger(newsCrop?.independent_publishers)?newsCrop.independent_publishers:0;
  return {...priceSignal,newsContext:count===0?'Свіжих тематичних новин у підключених джерелах немає.':
    `Знайдено ${count} тематичних публікацій із ${publishers} незалежних видань. Це інформаційний контекст, не доказ напрямку місцевої ціни.`,
    newsUrls: (newsCrop?.articles||[]).filter(a=>{try{return new URL(a.url).protocol==='https:'}catch{return false}}).slice(0,3).map(a=>a.url)};
}
