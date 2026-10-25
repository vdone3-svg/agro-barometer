import test from 'node:test';import assert from 'node:assert/strict';
import {groupOffers,seriesFor,priceDelta} from '../public/js/offer-trends-core.mjs';
const base={identity:'id1',company:'РАМБУРС',product:'Пшениця',point:'Ізмаїл',kind:'grain',currency:'UAH'};
test('one quote is a baseline, not a price change',()=>{const a={...base,price:8200,quote_date:'2026-10-20'};assert.equal(seriesFor([a],'id1').length,1);assert.equal(priceDelta(null,a),null)});
test('repeated identical quote date does not generate a second plotted point',()=>{const a={...base,price:8200,quote_date:'2026-10-20',first_seen_at:'2026-10-25T10:00:00Z'};assert.equal(seriesFor([a,{...a,first_seen_at:'2026-10-26T10:00:00Z'}],'id1').length,1)});
test('new dated price produces change in original currency',()=>{const a={...base,price:8200,quote_date:'2026-10-20'},b={...a,price:8400,quote_date:'2026-10-26'};assert.equal(priceDelta(a,b),200)});
test('different currency or identity cannot be compared',()=>{const a={...base,price:8200,quote_date:'2026-10-20'};assert.equal(priceDelta(a,{...a,currency:'USD',quote_date:'2026-10-26'}),null);assert.equal(priceDelta(a,{...a,identity:'other',quote_date:'2026-10-26'}),null)});
test('groups distinct identities',()=>{assert.equal(groupOffers([{...base,price:100},{...base,price:110}]).length,1)});
