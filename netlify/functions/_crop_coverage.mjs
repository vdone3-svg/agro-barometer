export const FIVE_CROPS = Object.freeze(['Соняшник','Кукурудза','Пшениця','Ячмінь','Ріпак']);
export function cropFamily(product=''){
 const p=String(product).toLocaleLowerCase('uk');
 if(p.startsWith('соняшник'))return 'Соняшник';
 if(p.startsWith('кукурудза'))return 'Кукурудза';
 if(p.startsWith('пшениця'))return 'Пшениця';
 if(p.startsWith('ячмінь'))return 'Ячмінь';
 if(p.startsWith('ріпак'))return 'Ріпак';
 return null;
}
export function cropCoverage(offers){
 return Object.fromEntries(FIVE_CROPS.map(name=>[name,offers.filter(o=>cropFamily(o.product)===name).length]));
}
