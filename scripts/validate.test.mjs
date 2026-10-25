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
test('additional public indicators API and collect integration exist',()=>{
 const root=new URL('../',import.meta.url);
 const fsContent=path=>fs.readFileSync(new URL(path,root),'utf8');
 assert.ok(fsContent('netlify/functions/public-indicators.mjs').includes('public-indicators-latest'));
 assert.ok(fsContent('netlify/functions/collect-morning.mjs').includes('collectPublicSources'));
 assert.ok(fsContent('netlify/functions/collect-daytime.mjs').includes('collectPublicSources'));
 assert.ok(fsContent('public/index.html').includes('market-auto-indicators'));
 assert.ok(fsContent('netlify/functions/_public_sources.mjs').includes('unverified_candidates'));
});
