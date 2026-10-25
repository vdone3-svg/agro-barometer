import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const root=new URL('../',import.meta.url);
test('static source still has data file',()=>{
 const market=JSON.parse(fs.readFileSync(new URL('public/data/market.json',root),'utf8'));
 for(const field of ['quotes','news','items','sources']) assert.ok(Array.isArray(market[field]),field);
});
test('display has live status panel and no invented crop values',()=>{
 const html=fs.readFileSync(new URL('public/index.html',root),'utf8');
 assert.ok(html.includes('auto-fx-status'));
 assert.ok(html.includes('market-status'));
 assert.ok(html.includes('не автоматичні'));
});
