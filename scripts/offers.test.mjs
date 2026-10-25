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
