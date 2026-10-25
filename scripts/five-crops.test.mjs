import test from 'node:test';
import assert from 'node:assert/strict';
import {cropFamily,cropCoverage} from '../netlify/functions/_crop_coverage.mjs';
test('five target families and variants mapped without mixing categories',()=>{
 assert.deepEqual(['Соняшник високоолеїновий','Кукурудза кремниста','Пшениця 3 клас','Ячмінь','Ріпак не ГМО'].map(cropFamily),['Соняшник','Кукурудза','Пшениця','Ячмінь','Ріпак']);
 assert.equal(cropFamily('Соя'),null);
});
test('coverage tracks missing crops as zero',()=>{
 assert.deepEqual(cropCoverage([{product:'Пшениця 4 клас'},{product:'Ріпак не ГМО'}]),{Соняшник:0,Кукурудза:0,Пшениця:1,Ячмінь:0,Ріпак:1});
});
