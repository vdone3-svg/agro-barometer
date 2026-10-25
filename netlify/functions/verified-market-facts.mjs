import {queryFacts} from './_verified_facts_v13.mjs';
export default async (request)=>{
 const url=new URL(request.url);
 const commodity=url.searchParams.get('commodity')||'';
 const sourceKind=url.searchParams.get('source_kind')||'';
 const records=queryFacts({commodity,sourceKind});
 return Response.json({schema_version:1,database:'verified_reference_facts_v13',snapshot_date:'2026-10-25',records_total:records.length,records,note:'Dated reference snapshots compiled from attributed publications. Not live USDA/EU API observations, not transaction prices, not authorized to drive buy/sell barometers.'},{headers:{'cache-control':'public,max-age=3600'}});
};
