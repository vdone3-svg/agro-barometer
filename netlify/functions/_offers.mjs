// Conservative E-ZERNO listing parser. Extract only individually attributable, absolutely dated offers.
// Intentionally no currency/VAT/basis inference, and no extraction from relative "сьогодні/вчора" dates.
const escEntities = str => String(str).replace(/&nbsp;|&#160;|&#xA0;/gi,' ').replace(/&amp;/gi,'&').replace(/&quot;/gi,'"').replace(/&#39;|&#x27;|&apos;/gi,"'").replace(/&lt;/gi,'<').replace(/&gt;/gi,'>');
const textify = h => escEntities(String(h).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,' ').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,' ').replace(/<[^>]*>/g,' ').replace(/[\u00a0\u202f]/g,' ')).replace(/\s+/g,' ').trim();
const iso = s => {const a=s.match(/^(\d{2})\.(\d{2})\.(20\d{2})$/);if(!a)return null;const v=`${a[3]}-${a[2]}-${a[1]}`;return new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v?v:null;};
const today = () => new Date().toISOString().slice(0,10);
const regionPattern=/(Кіровоградська|Полтавська|Дніпропетровська|Черкаська|Одеська|Миколаївська|Київська|Хмельницька|Вінницька|Житомирська|Львівська|Чернівецька|Закарпатська|Харківська|Рівненська|Волинська|Тернопільська|Сумська|Чернігівська|Запорізька|Івано-Франківська|Херсонська|Донецька|Луганська)\s+обл\./;
const grainTypes=['Соняшник високоолеїновий','Ріпак не ГМО','Пшениця 2 клас','Пшениця 3 клас','Пшениця 4 клас','Пшениця 2кл.','Пшениця 3кл.','Пшениця 4кл.','Соняшник','Кукурудза','Ячмінь','Ріпак'];
const fertilizerTypes=['Аміачна селітра','Нітроамофоска','Карбамід','КАС'];
const safeN=(s)=>{const n=Number(s.replace(/[\s\u00a0\u202f]/g,'').replace(',','.'));return Number.isFinite(n)?n:null};

// Do not publish an offer if its location appears to include another listing.
// Fail closed: a missing location is preferable to a misattributed commercial quote.
const spilloverPattern = /(?:Платиновий партнер|Золотий партнер|Срібний партнер|Ціни на|\bТОВ\b|\bAGROP\b|\bLuv\b|\bN:|\bP:|\bK:|(?:Амофос|Суперфосфат|Карбамід|Селітра|Пшениця|Соняшник|Кукурудза|Ріпак|Нітроамофоска|КАС)\s*(?:\(|[0-9]|$))/i;
const invalidLocation = point => !point || point.length > 65 || spilloverPattern.test(point) || /[<>]|&(?:#|[a-z]+;)/i.test(point) || /\b(?:Черкас|Ізмаїл|Мостиська)\s+[А-ЯA-Z][^,]*$/.test(point);

function findOffers(chunk,kind,company,date,sourceUrl){
 const types=kind==='grain'?grainTypes:fertilizerTypes;
 const escaped=types.map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
 const re=new RegExp('('+escaped.join('|')+')\\s*(?:\\(\\s*([^)]{1,65})\\s*\\))?\\s*(\\$|€)?\\s*([0-9][0-9\\s\\u00a0\\u202f]{1,10}(?:[.,]\\d{1,2})?)\\s+','gi');
 const out=[];let m;
 while((m=re.exec(chunk))){
  const product=m[1].replace(/\s+/g,' ').trim();
  const val=safeN(m[4]);const currency=m[3]==='$'?'USD':m[3]==='€'?'EUR':'UAH';
  if(val===null || (currency==='UAH'?(val<100||val>200000):(val<30||val>5000)))continue;
  const tail=chunk.slice(re.lastIndex,re.lastIndex+190);
  const rm=tail.match(regionPattern);
  if(!rm || rm.index>110)continue;
  const after=tail.slice(rm.index+rm[0].length).trim();
  const next=after.search(new RegExp('(?:'+escaped.join('|')+')\\s*(?:\\(|\\$|€|[0-9])','i'));
  const point=(next>=0?after.slice(0,next):after).replace(/^(?:Україна\s*\/\s*[^ ]+\s*)/,'').trim().slice(0,100);
  if(invalidLocation(point))continue;
  const rec={kind,company,product,formula:m[2]?.trim()||null,price:val,currency,region:rm[1]+' обл.',point:point||null,quote_date:date,source_url:sourceUrl,vat:'unknown',basis:'unknown',verification:'unverified',quality:'partial',collected_at:null};
  out.push(rec);
 }
 return out;
}
const knownCompanies=[
'НІБУЛОН','RISOIL','ГЛЕНПОРТ ОДЕСА','OKKO','АГРОХІМТЕХНОЛОДЖІ','АСТАРТА-КИЇВ','В АГРО','РАМБУРС','КОРОЛІВСЬКИЙ СМАК','AVALON GP TRAIDING','KERNEL','AGROPROSPERIS','Контінентал Фармерз Груп','МХП','КИЇВСЬКИЙ МЛИН','БІСКВІТНИЙ КОМПЛЕКС РОШЕН','Алмейда Груп','AGROMINO','AGROVISTA','FENIX AGRO','VVT Group','YUROL TRADING','АТК','GROSSDORF Агрохімічна Компанія','ExpoGrain','МКО ТРАНС-СЕРВІС','DACSA BUNGE UKRAINE','Region Grain Company','Ділекс Трейд','ТОВ Гудгрейноіл','ОДЕСЗЕРНОТРЕЙД','РОМА','Васильківхлібпродукт','Павлоградзернопродукт','GRANOLA','ТОВ Коудайс Україна','РО АГРО ТРЕЙД','YEDNIST\' GROUP','ФАЗОР','АГРОПАРТНЕР','Українська Агропромислова Група','ХІМАГРО','ІНАГРОТЕХ','MAKOSH','САНАГРО УКРАЇНА','ПромНафтоХімКомплект','Агрономічна компанія','УКРФЕРТІНВЕСТ','МИНЕРАЛ-ТРЕЙД','ВА АГРО ЮКРЕЙН','AGROTOK','НВП Фервіта','АГРОВЕЙ ДОБРИВА','КЕАРФІЛД'];
function knownCompany(prefix){const p=prefix.toLocaleUpperCase('uk');const found=knownCompanies.filter(n=>p.endsWith(n.toLocaleUpperCase('uk'))).sort((a,b)=>b.length-a.length);return found[0]||null;}
export function extractOfferCandidates(html,kind,sourceUrl){
 const text=textify(html);
 if(!text.includes(kind==='grain'?'Ціни на зерно':'Ціни на добрива'))throw Error('Unexpected E-ZERNO page type');
 const start=text.indexOf('Платинові партнери');
 const content=start>=0?text.slice(start):text;
 // Each card is delimited by its own price-date header, including relative-date cards.
 // Never allow the next company card to become a previous offer's location.
 const dateHeader=/Ціни на\s+(сьогодні|вчора|\d{2}\.\d{2}\.20\d{2})/gi;
 const matches=[...content.matchAll(dateHeader)];
 const offers=[];
 for(let i=0;i<matches.length;i++){
  const m=matches[i];
  const date=iso(m[1]);
  if(!date||date>today())continue; // no inferred date for "today" or "yesterday"
  const preceding=content.slice(Math.max(0,m.index-240),m.index).replace(/(?:Платиновий партнер|Золотий партнер|Срібний партнер|Трейдери|Дистриб'ютори|Партнери)\s*$/gi,' ').trim();
  const company=knownCompany(preceding);
  if(!company)continue;
  const end=i+1<matches.length?matches[i+1].index:content.length;
  let chunk=content.slice(m.index+m[0].length,end).slice(0,900);
  // Trim next card's name/partner label, before matching any candidate offer.
  const nextCompany=knownCompanies
    .map(name=>({name,index:chunk.toLocaleUpperCase('uk').indexOf(name.toLocaleUpperCase('uk'))}))
    .filter(x=>x.index>=0)
    .sort((a,b)=>a.index-b.index)[0];
  if(nextCompany)chunk=chunk.slice(0,nextCompany.index);
  const unknownNextCompany=chunk.search(/\bТОВ\s+[А-ЯA-ZІЇЄҐ]/);
  if(unknownNextCompany>=0)chunk=chunk.slice(0,unknownNextCompany);
  offers.push(...findOffers(chunk,kind,company,date,sourceUrl));
 }
 const unique=new Map();
 for(const x of offers){const key=[x.kind,x.company,x.product,x.formula,x.price,x.currency,x.region,x.point,x.quote_date].join('|');unique.set(key,x);}
 return [...unique.values()].slice(0,120);
}
