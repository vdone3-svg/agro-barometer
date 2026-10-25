import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compareScenario} from '../public/js/agro-decision-core-v9.mjs';
const x=JSON.parse(readFileSync(new URL('../public/data/logistics-city-routes-v8.json',import.meta.url)));
test('V10.1 8 sourced planning city routes',()=>{assert.equal(x.version,'city_v10_1');assert.equal(x.routes.length,8);assert.equal(new Set(x.routes.map(r=>r.city)).size,8);assert(x.routes.every(r=>r.km>0&&r.source.startsWith('https://')&&r.status==='planning_city_to_city'))});
test('Odessa versus Izmail: higher gross quote does not necessarily win',()=>{const offers=[{company:'Одеса',product:'Пшениця 3 клас',point:'Одеса',region:'Одеська обл.',price:7900},{company:'Ізмаїл',product:'Пшениця 3 клас',point:'Ізмаїл',region:'Одеська обл.',price:8300}];const r=compareScenario(offers,x.routes,3);assert.equal(r.ranked.length,2);assert.equal(r.ranked[0].company,'Одеса');assert.equal(r.ranked[0].remainder,6670);assert.equal(r.ranked[1].remainder,6356)});
test('Reni and Zolochiv routes included; ambiguous Pereiaslavska excluded',()=>{const o=[{company:'ExpoGrain',point:'Рені',region:'Одеська обл.',price:7200},{company:'Koudais',point:'Золочів',region:'Львівська обл.',price:6000},{company:'NIBULON',point:'Переяславська',region:'Київська обл.',price:4200}];const r=compareScenario(o,x.routes,3);assert.equal(r.ranked.length,2);assert.equal(r.missing.length,1);assert.equal(r.missing[0].company,'NIBULON')});
test('Yarmolyntsi approximate waypoint route preserves source',()=>{const r=x.routes.find(x=>x.city==='Ярмолинці');assert.equal(r.km,552);assert.match(r.note,/проміжної точки/)});
