/** V13 interview decisions: visibility is not an economic claim. */
export const INTERVIEW_POLICY_V13=Object.freeze({
 unknown_freight:'separate_promising_unconfirmed',
 mixed_delivery:'single_verified_economic_comparison',
 unusual_quote:'review_without_ranking',
 homepage:'verified_offers_market_state_evidence',
});
const positive=v=>typeof v==='number'&&Number.isFinite(v)&&v>0;
/** Evaluate an observed listing WITHOUT assuming the unit, VAT, terms or a freight rate. */
export function publicOpportunity(offer,{confirmedReference=null}={}){
 if(offer?.freshness==='archival_unverified')return {category:'archive',reasons:['Архівне спостереження']};
 const reasons=[];
 if(!positive(offer?.price_uah_per_tonne))reasons.push('Ціна у грн/т не підтверджена');
 if(offer?.vat_status==='unknown'||!['included','excluded'].includes(offer?.vat_status))reasons.push('ПДВ невідомий');
 if(offer?.delivery_mode!=='pickup'&&offer?.delivery_mode!=='seller_delivery')reasons.push('Базис і спосіб доставки невідомі');
 if(offer?.quality_conditions_verified!==true)reasons.push('Умови якості потребують перевірки');
 if(!offer?.destination_city)reasons.push('Напрямок не встановлено');
 if(offer?.delivery_mode==='seller_delivery'&&offer?.freight_confirmed!==true)reasons.push('Немає підтвердженого фрахту');
 const ref=confirmedReference;
 // Outlier alert only when both numbers have verified matching unit/tax/quality and reference is documented.
 const comparableReference=ref?.documented===true&&ref?.same_crop_and_grade===true&&ref?.same_vat_basis===true&&ref?.same_delivery_basis===true&&positive(ref?.price_uah_per_tonne)&&positive(offer?.price_uah_per_tonne);
 const unusual=comparableReference&&offer.price_uah_per_tonne>ref.price_uah_per_tonne*1.3;
 if(unusual)reasons.push('Нетипова ціна відносно підтвердженого порівнюваного орієнтира');
 if(unusual)return {category:'review_priority',reasons};
 if(reasons.length)return {category:'promising_unconfirmed',reasons};
 // Listing completeness is not enough for certification: actual engine must still validate every criterion.
 return {category:'needs_economic_engine',reasons:['Потрібна остаточна економічна перевірка']};
}
export function interviewOverview(offers=[],result={ranked:[],review:[],archived:[]}){
 const counts={verified:result.ranked?.length||0,promising:0,reviewPriority:0,archived:0};
 const items=[];
 const verifiedOffers=new Set((result.ranked||[]).map(row=>row.offer));
 for(const offer of offers){if(verifiedOffers.has(offer))continue;const d=publicOpportunity(offer);items.push({offer,...d});if(d.category==='archive')counts.archived++;else if(d.category==='review_priority')counts.reviewPriority++;else if(d.category==='promising_unconfirmed'||d.category==='needs_economic_engine')counts.promising++;}
 // A result reviewed by the economic engine is not moved into the verified column automatically.
 return {counts,items};
}
