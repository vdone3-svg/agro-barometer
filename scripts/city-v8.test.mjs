import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const routes=JSON.parse(readFileSync('public/data/logistics-city-routes-v8.json','utf8'));const source=readFileSync('public/js/agro-logistics-v7.mjs','utf8');
test('city route catalog includes verified city distance',()=>{assert(routes.routes.length>=1);assert.equal(routes.routes[0].city,'Ізмаїл');assert.equal(routes.routes[0].km,648);assert.equal(routes.default_freight_rate,null)});
test('never invent unknown city distances',()=>{assert.match(source,/km.value=''/);assert.match(source,/rate.value=''/)});
test('display city from conservative point names',()=>{assert.match(source,/function destination/);assert.match(source,/function updateCity/)});
test('preserve V7 conditional math and unverified disclosure',()=>{assert.match(source,/const cost=k\*t/);assert.match(source,/ПДВ і базис невідомі/)});
