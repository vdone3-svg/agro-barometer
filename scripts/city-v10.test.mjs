import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compareScenario} from '../public/js/agro-decision-core-v9.mjs';
const x=JSON.parse(readFileSync(new URL('../public/data/logistics-city-routes-v8.json',import.meta.url)));
test('V10 5 unique verified sourced city routes',()=>{assert.equal(x.version,'city_v10');assert.equal(x.routes.length,5);assert.equal(new Set(x.routes.map(r=>r.city)).size,5);assert(x.routes.every(r=>r.km>0&&r.source.startsWith('https://flagma.ua/')&&r.status==='planning_city_to_city'))});
test('Odessa versus Izmail: higher gross quote does not necessarily win',()=>{const offers=[{company:'Одеса',product:'Пшениця 3 клас',point:'Одеса',region:'Одеська обл.',price:7900},{company:'Ізмаїл',product:'Пшениця 3 клас',point:'Ізмаїл',region:'Одеська обл.',price:8300}];const r=compareScenario(offers,x.routes,3);assert.equal(r.ranked.length,2);assert.equal(r.ranked[0].company,'Одеса');assert.equal(r.ranked[0].remainder,6670);assert.equal(r.ranked[1].remainder,6356)});
test('unknown destinations not magically estimated',()=>{const r=compareScenario([{company:'Z',point:'Рені',region:'Одеська обл.',price:9000}],x.routes,3);assert.equal(r.ranked.length,0);assert.equal(r.missing.length,1)});
