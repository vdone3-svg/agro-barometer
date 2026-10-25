import test from 'node:test';
import assert from 'node:assert/strict';
import {extractOfferCandidates} from '../netlify/functions/_offers.mjs';
const sample=`<h1>Ціни на зерно</h1><h2>Платинові партнери</h2><div>KERNEL Ціни на 20.10.2026 Соняшник15&nbsp;500 Кіровоградська обл.Олександрія</div><div>ТОВ ДРУГЕ Ціни на вчора Кукурудза 8 500 Полтавська обл.Кременчук</div>`;
test('only absolutely dated offers',()=>{let r=extractOfferCandidates(sample,'grain','https://e-zerno.com/trader-prices');assert.equal(r.length,1);assert.equal(r[0].price,15500);assert.equal(r[0].quote_date,'2026-10-20');assert.equal(r[0].verification,'unverified')});
test('reject unexpected page',()=>assert.throws(()=>extractOfferCandidates('error','grain','x')));

test('reject location blended with next partner',()=>{
 const html='<h1>Ціни на зерно</h1><h2>Платинові партнери</h2><div>РАМБУРС Ціни на 20.10.2026 Пшениця 3 клас 8 200 Одеська обл. Ізмаїл Пшениця 2 клас 8 300 Одеська обл. Ізмаїл КОРОЛІВСЬКИЙ СМАК Золотий партнер</div>';
 const r=extractOfferCandidates(html,'grain','https://e-zerno.com/trader-prices');
 assert(r.every(o=>!o.point.includes('КОРОЛІВСЬКИЙ СМАК')));
});
test('decode hexadecimal apostrophe entity',()=>{
 const html='<h1>Ціни на добрива</h1><h2>Платинові партнери</h2><div>АГРОВЕЙ ДОБРИВА Ціни на 22.10.2026 КАС ( N:32 ) 25 500 Дніпропетровська обл. м. Кам&#x27;янське</div>';
 const r=extractOfferCandidates(html,'fertilizer','https://e-zerno.com/fertilizer-prices');
 assert.equal(r[0]?.point,"м. Кам'янське");
});

test('captures all five planned crops with absolute dates',()=>{
 const records=[
 ['KERNEL','20.10.2026','Соняшник 15 500 Кіровоградська обл. Олександрія'],
 ['AGROPROSPERIS','28.07.2026','Кукурудза 7 000 Хмельницька обл. Поділля елеватор'],
 ['РАМБУРС','20.10.2026','Пшениця 3 клас 8 200 Одеська обл. Ізмаїл'],
 ['АТК','18.07.2026','Ячмінь 8 000 Житомирська обл. Печанівка'],
 ['ExpoGrain','20.10.2026','Ріпак не ГМО 20 200 Одеська обл. Одеса']
 ];
 const html='<h1>Ціни на зерно</h1><h2>Платинові партнери</h2>'+records.map(([c,d,v])=>`<div>${c} Ціни на ${d} ${v}</div>`).join('');
 const out=extractOfferCandidates(html,'grain','https://e-zerno.com/trader-prices');
 assert.deepEqual(new Set(out.map(x=>x.product)),new Set(['Соняшник','Кукурудза','Пшениця 3 клас','Ячмінь','Ріпак не ГМО']));
 assert(out.every(o=>o.verification==='unverified'&&o.vat==='unknown'));
});

test('relative-date cards are not converted to dated quotes',()=>{
 const html='<h1>Ціни на зерно</h1><h2>Платинові партнери</h2>KERNEL Ціни на сьогодні Соняшник 15 500 Кіровоградська обл. Олександрія AGROPROSPERIS Ціни на 28.07.2026 Кукурудза 7 000 Хмельницька обл. Поділля елеватор';
 const out=extractOfferCandidates(html,'grain','x');
 assert(out.every(o=>o.product!=='Соняшник'));
 assert.equal(out.length,1);
});
