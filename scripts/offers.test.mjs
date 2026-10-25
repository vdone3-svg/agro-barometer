import test from 'node:test';
import assert from 'node:assert/strict';
import {extractOfferCandidates} from '../netlify/functions/_offers.mjs';
const sample=`<h1>Ціни на зерно</h1><h2>Платинові партнери</h2><div>KERNEL Ціни на 20.10.2026 Соняшник15&nbsp;500 Кіровоградська обл.Олександрія</div><div>ТОВ ДРУГЕ Ціни на вчора Кукурудза 8 500 Полтавська обл.Кременчук</div>`;
test('only absolutely dated offers',()=>{let r=extractOfferCandidates(sample,'grain','https://e-zerno.com/trader-prices');assert.equal(r.length,1);assert.equal(r[0].price,15500);assert.equal(r[0].quote_date,'2026-10-20');assert.equal(r[0].verification,'unverified')});
test('reject unexpected page',()=>assert.throws(()=>extractOfferCandidates('error','grain','x')));
