// Explicitly documented RSS locations only; candidates are NOT automatically scraped.
export const ACTIVE_FEEDS = Object.freeze([
 {id:'lat-grain',name:'Latifundist · Зерно',publisher:'Latifundist',country:'UA',tier:'sector_media',url:'https://latifundist.com/rss/novosti/zerno',host:'latifundist.com'},
 {id:'lat-process',name:'Latifundist · Переробка',publisher:'Latifundist',country:'UA',tier:'sector_media',url:'https://latifundist.com/rss/novosti/pererabotka',host:'latifundist.com'},
 {id:'lat-elev',name:'Latifundist · Елеватори',publisher:'Latifundist',country:'UA',tier:'sector_media',url:'https://latifundist.com/rss/novosti/elevatory',host:'latifundist.com'},
 {id:'agroportal-news',name:'AgroPortal · Новини',publisher:'AgroPortal',country:'UA',tier:'sector_media',url:'https://agroportal.ua/en/rss/type_news',host:'agroportal.ua'}
]);
// Research queue: confirmed relevant publishers/reports, but RSS/API or reuse terms must be checked.
export const SOURCE_CATALOG = Object.freeze([
 ...ACTIVE_FEEDS.map(x=>({id:x.id,publisher:x.publisher,category:x.tier,mode:'rss_configured_not_live_verified',url:x.url,country:x.country})),
 {id:'agrotimes',publisher:'AgroTimes',category:'sector_media',mode:'integration_pending',url:'https://agrotimes.ua/',country:'UA'},
 {id:'agravery',publisher:'Agravery',category:'sector_media',mode:'integration_pending',url:'https://agravery.com/',country:'UA'},
 {id:'elevatorist',publisher:'Elevatorist',category:'logistics',mode:'integration_pending',url:'https://elevatorist.com/',country:'UA'},
 {id:'kurkul',publisher:'Kurkul',category:'sector_media',mode:'integration_pending',url:'https://kurkul.com/',country:'UA'},
 {id:'apk-inform',publisher:'APK-Inform',category:'market_analysis',mode:'integration_pending',url:'https://www.apk-inform.com/',country:'UA'},
 {id:'graintrade',publisher:'GrainTrade',category:'market_analysis',mode:'integration_pending',url:'https://graintrade.com.ua/',country:'UA'},
 {id:'agroreview',publisher:'AgroReview',category:'sector_media',mode:'integration_pending',url:'https://agroreview.com/',country:'UA'},
 {id:'superagronom',publisher:'SuperAgronom',category:'agronomy',mode:'integration_pending',url:'https://superagronom.com/',country:'UA'},
 {id:'agropolit',publisher:'AgroPolit',category:'policy',mode:'integration_pending',url:'https://agropolit.com/',country:'UA'},
 {id:'uga',publisher:'Українська зернова асоціація',category:'industry_body',mode:'integration_pending',url:'https://uga.ua/',country:'UA'},
 {id:'minagro',publisher:'Мінагрополітики України',category:'official',mode:'integration_pending',url:'https://minagro.gov.ua/',country:'UA'},
 {id:'ukrstat',publisher:'Держстат України',category:'official',mode:'integration_pending',url:'https://ukrstat.gov.ua/',country:'UA'},
 {id:'ukrzaliznytsia',publisher:'Укрзалізниця',category:'logistics',mode:'integration_pending',url:'https://www.uz.gov.ua/',country:'UA'},
 {id:'usda-fas',publisher:'USDA Foreign Agricultural Service',category:'official',mode:'integration_pending',url:'https://fas.usda.gov/data',country:'US'},
 {id:'usda-wasde',publisher:'USDA WASDE',category:'official',mode:'integration_pending',url:'https://www.usda.gov/oce/commodity/wasde',country:'US'},
 {id:'usda-nass',publisher:'USDA NASS',category:'official',mode:'integration_pending',url:'https://www.nass.usda.gov/Help/RSS/index.php',country:'US'},
 {id:'eu-commission',publisher:'Європейська Комісія · Аграрні ринки',category:'official',mode:'integration_pending',url:'https://agriculture.ec.europa.eu/data-and-analysis/markets_en',country:'EU'},
 {id:'eu-agri-data',publisher:'EU Agri-food Data Portal',category:'official',mode:'integration_pending',url:'https://agridata.ec.europa.eu/',country:'EU'},
 {id:'fao',publisher:'FAO',category:'official',mode:'integration_pending',url:'https://www.fao.org/worldfoodsituation/en/',country:'INT'},
 {id:'igc',publisher:'International Grains Council',category:'market_analysis',mode:'integration_pending',url:'https://www.igc.int/',country:'INT'},
 {id:'ahdb',publisher:'AHDB Cereals & Oilseeds',category:'market_analysis',mode:'integration_pending',url:'https://ahdb.org.uk/',country:'GB'},
 {id:'reuters',publisher:'Reuters Commodities',category:'global_media',mode:'licence_or_feed_required',url:'https://www.reuters.com/markets/commodities/',country:'INT'},
 {id:'s-p-global',publisher:'S&P Global Commodity Insights',category:'market_analysis',mode:'licence_or_feed_required',url:'https://www.spglobal.com/commodity-insights/',country:'INT'}
]);
