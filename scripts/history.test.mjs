import test from 'node:test';
import assert from 'node:assert/strict';
import { updateHistory, offerIdentity } from '../netlify/functions/_offer_history.mjs';
const example={kind:'grain',company:'RISOIL',product:'Пшениця 3 клас',formula:null,price:158,currency:'USD',region:'Львівська обл.',point:'Мостиська',quote_date:'2026-10-19',source_url:'https://e-zerno.com/trader-prices',verification:'unverified',quality:'partial'};
const src=o=>[{id:'grain',status:'ok',data:{offers:o}}];
test('new observation and unchanged rerun are idempotent',()=>{const a=updateHistory(null,src([example]),'2026-10-25T10:00:00.000Z');assert.equal(a.total_observations,1);const b=updateHistory(a,src([example]),'2026-10-25T12:00:00.000Z');assert.equal(b.total_observations,1);assert.equal(b.added_this_run,0);assert.equal(b.changes.length,0)});
test('different price creates change without changing identity',()=>{const a=updateHistory(null,src([example]),'2026-10-25T10:00:00.000Z');const changed={...example,price:159,quote_date:'2026-10-20'};assert.equal(offerIdentity(example),offerIdentity(changed));const b=updateHistory(a,src([changed]),'2026-10-26T10:00:00.000Z');assert.equal(b.total_observations,2);assert.equal(b.changes[0].previous_price,158);assert.equal(b.changes[0].new_price,159)});
test('failed source is not added; invalid quote skipped',()=>{assert.equal(updateHistory(null,[{...src([example])[0],status:'error'}],'2026-10-25T10:00:00.000Z').total_observations,0);assert.equal(updateHistory(null,src([{...example,price:NaN}]),'2026-10-25T10:00:00.000Z').total_observations,0)});
