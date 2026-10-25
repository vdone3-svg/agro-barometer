import test from 'node:test';
import assert from 'node:assert/strict';
import {pointProblem,offerProblem,quoteFreshness} from '../netlify/functions/_offer_quality.mjs';
const bad=[
 'Мостиська ТОВ "','Ізмаїл Золоті партнери','Одеса Новотех Соя 20 100 Одеська обл. Ізмаїл',
 'Миронівка Соя 16 800 Черкаська обл. Єрки', 'Черкаси ТОВ «','м.Васильків Жито 6 000 Київська обл. м.Васильків'
];
test('known V6 listing spillovers are withheld',()=>{for(const p of bad)assert.ok(pointProblem(p),p);});
test('simple locations remain readable',()=>{for(const p of ['Ізмаїл','ст. Глибока','м. Кам\'янське','Придніпровський ОЕЗ','Одеса, Чорноморськ, Південний'])assert.equal(pointProblem(p),null,p);});
test('archival dates get an archival status without rewriting source date',()=>{
 const at=new Date('2026-10-25T10:00:00Z');
 assert.equal(quoteFreshness({quote_date:'2026-03-24'},at),'archival_unverified');
 assert.equal(quoteFreshness({quote_date:'2026-10-23'},at),'recent_unverified');
 assert.equal(quoteFreshness({quote_date:'2026-10-10'},at),'older_unverified');
});
test('offer checks include obvious location contamination',()=>{
 assert.equal(offerProblem({kind:'grain',company:'RISOIL',product:'Пшениця 4 клас',price:150,point:'Мостиська ТОВ "'}),'markup_or_company_quote');
});
