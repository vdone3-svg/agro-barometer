import test from 'node:test';
import assert from 'node:assert/strict';
import {filterSourceOffers,offerProblem} from '../netlify/functions/_offer_quality.mjs';
const base={kind:'grain',company:'X',product:'Пшениця 3 клас',price:8000,currency:'UAH',point:'Ізмаїл',quote_date:'2026-10-20',verification:'unverified'};
test('rejected spillover in historical snapshots',()=>{
 const source={id:'grain',data:{offers:[base,{...base,point:'Одеса Горох жовтий 11 000 Одеська обл. Одеса'},{...base,point:'Мостиська ТОВ "'},{...base,point:'с. Кожанка ПРОДІНВЕСТ СЕРВІС'}]}};
 const out=filterSourceOffers(source);
 assert.equal(out.data.offers.length,1);assert.equal(out.data.quality_control.hidden_malformed,3);assert.equal(out.data.crop_coverage['Пшениця'],1);
});
test('clean known facility retained',()=>assert.equal(offerProblem({...base,point:'Бориспіль Елеватор БК Рошен'}),null));
