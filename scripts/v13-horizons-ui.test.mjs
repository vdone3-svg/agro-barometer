import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8');
const ui=readFileSync(new URL('../public/js/agro-v13-horizons-ui.mjs',import.meta.url),'utf8');
test('three horizon dashboard component present',()=>{assert.match(html,/id="agro-v13-horizons"/);assert.match(html,/7–14 днів, 30 днів та 3 місяці/);assert.match(html,/agro-v13-horizons-ui\.mjs/)});
test('all six crops present on dashboard',()=>{for(const crop of ['wheat','corn','sunflower','barley','soy','rapeseed'])assert.ok(ui.includes(`'${crop}'`))});
test('no invented observations injected by UI',()=>{assert.match(ui,/Array\.isArray\(source\)\?source:\[\]/);assert.match(ui,/assessThreeHorizons/)});
