import test from 'node:test';
import assert from 'node:assert/strict';
import {ACTIVE_FEEDS,SOURCE_CATALOG} from '../netlify/functions/_news_sources_v13.mjs';
import {parseRss,summarizeNews} from '../netlify/functions/_news_digest_v13.mjs';
const now=Date.parse('2026-10-25T12:00:00Z');
function item(host,headline){return {title:headline,url:`https://${host}/story/1`,date:'2026-10-24T12:00:00.000Z',source:host,excerpt:headline}}
test('registry contains more than one independent news publisher',()=>assert.ok(new Set(ACTIVE_FEEDS.map(x=>x.publisher)).size>=2));
test('more than twenty candidate channels are catalogued',()=>assert.ok(SOURCE_CATALOG.length>=20));
test('sources awaiting review cannot be fetched by feed list',()=>assert.ok(ACTIVE_FEEDS.every(x=>SOURCE_CATALOG.find(c=>c.id===x.id)?.mode==='rss_configured_not_live_verified')));
test('feed URLs use https and have allowed hostname',()=>{for(const f of ACTIVE_FEEDS){assert.equal(new URL(f.url).protocol,'https:');assert.equal(new URL(f.url).hostname,f.host)}});
test('cross-source identical headlines are deduplicated',()=>{const title='Кукурудза рекордний збір зерна в Україні сьогодні';const d=summarizeNews([item('agroportal.ua',title),item('latifundist.com',title)],{now});assert.equal(d.articles_total,1)});
test('different articles from two publishers count independently',()=>{const d=summarizeNews([item('agroportal.ua','Кукурудза та експорт до Європи протягом тижня'),item('latifundist.com','Кукурудза та нові показники врожайності в Україні')],{now});assert.equal(d.crops['кукурудза'].independent_publishers,2)});
test('AgroPortal RSS item accepts only its publisher URLs',()=>{const xml=`<rss><channel><item><title>Кукурудза прогноз врожаю в Україні</title><link>https://agroportal.ua/news/1</link><pubDate>Sat, 24 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>`;assert.equal(parseRss(xml,'AgroPortal','agroportal.ua',now).length,1)});
