// Freight observations are NOT confirmed bookings or grain purchase prices.
const dateRE=/^20\d{2}-\d{2}-\d{2}$/;
const isCalendarDate=(value)=>{
 if(!dateRE.test(value))return false;
 const date=new Date(value+'T00:00:00.000Z');
 return Number.isFinite(date.getTime()) && date.toISOString().slice(0,10)===value;
};
const text=(v,n=160)=>typeof v==='string'&&v.trim()&&v.trim().length<=n;
const clean=(v)=>typeof v==='string'?v.trim():'';
const choices=(v,allowed)=>allowed.includes(v);
export function normalizeFreightRate(input, today=new Date().toISOString().slice(0,10)){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('record must be an object');
 const required=['source_name','source_url','observed_date','origin_city','destination_city','vehicle_type','cargo_type','payment_type','vat_status','evidence_status'];
 for(const k of required)if(!text(input[k],k==='source_url'?700:160))throw Error(`missing or invalid ${k}`);
 let u;
 try{u=new URL(input.source_url);}catch{throw Error('invalid source_url')}
 if(u.protocol!=='https:'&&u.protocol!=='http:')throw Error('invalid URL protocol');
 if(!isCalendarDate(input.observed_date)||input.observed_date>today)throw Error('invalid observed_date');
 const vType=['grain_truck','other'];if(!choices(input.vehicle_type,vType))throw Error('invalid vehicle_type');
 if(!choices(input.evidence_status,['unverified_listing','carrier_quote','verified_document']))throw Error('invalid evidence_status');
 if(!choices(input.vat_status,['included','excluded','unknown']))throw Error('invalid vat_status');
 if(!choices(input.payment_type,['cash','bank','unknown']))throw Error('invalid payment_type');
 const distance=Number(input.distance_km),tonnage=Number(input.load_tonnes);
 if(!Number.isFinite(distance)||distance<1||distance>5000)throw Error('invalid distance_km');
 if(!Number.isFinite(tonnage)||tonnage<1||tonnage>100)throw Error('invalid load_tonnes');
 const hasTrip=input.trip_price_uah!=null && input.trip_price_uah!=='';
 const hasTonne=input.price_per_tonne_uah!=null && input.price_per_tonne_uah!=='';
 if(hasTrip===hasTonne)throw Error('provide exactly one of trip_price_uah and price_per_tonne_uah');
 const price=Number(hasTrip?input.trip_price_uah:input.price_per_tonne_uah);
 if(!Number.isFinite(price)||price<=0||price>1000000)throw Error('invalid price');
 const perTonne=hasTrip?price/tonnage:price;
 const id=clean(input.record_id);
 if(id&&!/^[a-zA-Z0-9_-]{6,90}$/.test(id))throw Error('invalid record_id');
 return {
  record_id:id||`${clean(input.observed_date)}-${clean(input.source_name).replace(/[^a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9]/g,'_').slice(0,28)}-${Math.round(distance)}-${Math.round(price)}-${Math.round(tonnage*10)}`,
  source_name:clean(input.source_name),source_url:u.toString(),observed_date:input.observed_date,
  origin_city:clean(input.origin_city),destination_city:clean(input.destination_city),
  distance_km:distance,vehicle_type:input.vehicle_type,cargo_type:clean(input.cargo_type),
  load_tonnes:tonnage,payment_type:input.payment_type,vat_status:input.vat_status,
  evidence_status:input.evidence_status, price_basis:hasTrip?'trip':'tonne',
  trip_price_uah:hasTrip?price:null,price_per_tonne_uah:Number(perTonne.toFixed(2)),
  price_per_tonne_km_uah:Number((perTonne/distance).toFixed(4)),
  direction_matters:true,notes:clean(input.notes).slice(0,350),
  // A quoted rate cannot become a firm carrier offer just because it was normalized.
  validated_for_market_model:false
 };
}
export function mergeRates(previous,incoming){
 const map=new Map((previous||[]).map(r=>[r.record_id,r]));
 for(const rate of incoming){
  const old=map.get(rate.record_id);
  if(old&&JSON.stringify(old)!==JSON.stringify(rate))throw Error(`record_id conflict: ${rate.record_id}`);
  map.set(rate.record_id,rate);
 }
 if(map.size>2000)throw Error('record limit exceeded');
 return [...map.values()].sort((a,b)=>b.observed_date.localeCompare(a.observed_date));
}
export function publicView(records,today=new Date().toISOString().slice(0,10)){
 const visible=(records||[]).map(({record_id,source_name,source_url,observed_date,origin_city,destination_city,distance_km,vehicle_type,cargo_type,load_tonnes,payment_type,vat_status,evidence_status,price_basis,trip_price_uah,price_per_tonne_uah,price_per_tonne_km_uah,validated_for_market_model})=>({record_id,source_name,source_url,observed_date,origin_city,destination_city,distance_km,vehicle_type,cargo_type,load_tonnes,payment_type,vat_status,evidence_status,price_basis,trip_price_uah,price_per_tonne_uah,price_per_tonne_km_uah,validated_for_market_model}));
 return {schema_version:1,database:'freight_rates_v11',date:today,records_total:visible.length,approved_for_automatic_pricing:visible.filter(r=>r.validated_for_market_model===true).length,records:visible,
  note:'Observations only. No implied market average or freight quote. Sources have not been automatically scraped. Do not rank grain purchase offers using this database until methodology and comparability are established.'};
}
