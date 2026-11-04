import json, os, re
from datetime import datetime, timezone
from pathlib import Path

USD_UAH   = float(os.environ.get("USD_UAH", "41.5"))
TEMPLATE  = Path(os.environ.get("TEMPLATE_PATH", "barometer_template.html"))
CULTURES  = ["ріпак", "соняшник", "соя", "кукурудза", "ячмінь", "пшениця"]
CULTURE_EMOJI = {"ріпак":"💛","соняшник":"🌻","соя":"🫘","кукурудза":"🌽","ячмінь":"🌾","пшениця":"🌱"}
FREIGHT = {
    "Долинське":{"Одеська":1500,"Черкаська":525,"Миколаївська":1050,"Кіровоградська":275,"Вінницька":700,"Хмельницька":900,"Полтавська":600,"невідомо":800},
    "Копані":{"Одеська":1400,"Черкаська":375,"Миколаївська":975,"Кіровоградська":105,"Вінницька":600,"Хмельницька":750,"Полтавська":450,"невідомо":700},
}
SELL_THRESHOLD = {"ріпак":18000,"соняшник":14000,"соя":16000,"кукурудза":6500,"ячмінь":6000,"пшениця":7000}
REGION_MAP = {"одес":"Одеська","черкас":"Черкаська","миколаїв":"Миколаївська","кіровоград":"Кіровоградська","вінниц":"Вінницька","хмельниц":"Хмельницька","полтав":"Полтавська"}

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except: return default

def normalize_region(raw):
    if not raw: return "невідомо"
    r = raw.lower()
    for kw, name in REGION_MAP.items():
        if kw in r: return name
    return "невідомо"

def enrich_records(records):
    for r in records:
        region = normalize_region(r.get("region",""))
        r["region_norm"] = region
        r["net_dolynske"] = r["price_uah"] - FREIGHT["Долинське"].get(region,800)
        r["net_kopani"]   = r["price_uah"] - FREIGHT["Копані"].get(region,700)
    return records

def best_prices(all_records):
    result = {}
    for culture in CULTURES:
        recs = [r for r in all_records if r.get("culture")==culture]
        if not recs: result[culture]=None; continue
        recs = enrich_records(recs)
        best_net   = max(recs, key=lambda x: x.get("net_kopani",0))
        best_price = max(recs, key=lambda x: x.get("price_uah",0))
        all_uah    = sorted(set(r["price_uah"] for r in recs), reverse=True)
        result[culture] = {
            "emoji": CULTURE_EMOJI.get(culture,"🌾"),
            "best_price_uah": best_price["price_uah"],
            "best_price_loc": best_price.get("location","?"),
            "best_price_src": best_price.get("source","?"),
            "best_net_kopani": best_net["net_kopani"],
            "best_net_dolynske": best_net["net_dolynske"],
            "best_net_loc": best_net.get("location","?"),
            "best_net_region": best_net.get("region_norm","?"),
            "best_net_src": best_net.get("source","?"),
            "best_net_basis": best_net.get("basis","EXW"),
            "best_net_date": best_net.get("date","?"),
            "price_max": all_uah[0], "price_min": all_uah[-1],
            "records_count": len(recs),
            "sources": sorted(set(r.get("source","?") for r in recs)),
            "top_records": sorted(recs, key=lambda x: x.get("price_uah",0), reverse=True)[:10],
            "sell_threshold": SELL_THRESHOLD.get(culture,10000),
        }
    return result

def prepare_land(land_data):
    recs = land_data.get("records",[])
    if not recs: return {"records":[],"stats":{}}
    sales = [r for r in recs if r.get("type")=="продаж"]
    rents_list = [r for r in recs if r.get("type")=="оренда"]
    prices_ha = [r["price_per_ha"] for r in sales if r.get("price_per_ha")]
    rent_vals  = [r["rent_per_lot"] for r in sales if r.get("rent_per_lot")]
    yields     = [r["yield_pct"] for r in sales if r.get("yield_pct")]
    stats = {
        "total_lots":len(recs),"sale_lots":len(sales),"rent_lots":len(rents_list),
        "avg_price_ha":round(sum(prices_ha)/len(prices_ha)) if prices_ha else 0,
        "min_price_ha":min(prices_ha) if prices_ha else 0,
        "max_price_ha":max(prices_ha) if prices_ha else 0,
        "avg_rent_lot":round(sum(rent_vals)/len(rent_vals)) if rent_vals else 0,
        "avg_yield":round(sum(yields)/len(yields),1) if yields else 0,
        "max_yield":max(yields) if yields else 0,
    }
    return {"records":recs,"stats":stats}

def build_injection(agro_data):
    data_json = json.dumps(agro_data, ensure_ascii=False)
    now = agro_data['generated_at']
    return f"""
<script>
window.__AGRO_DATA__ = {data_json};
(function(){{
  const D=window.__AGRO_DATA__;
  const USD_UAH=D.usd_uah;
  function fmt(n,d=0){{if(n==null||isNaN(n))return'—';return new Intl.NumberFormat('uk-UA',{{minimumFractionDigits:d,maximumFractionDigits:d}}).format(n);}}
  function fmtTrip(net,t=25){{if(!net||isNaN(net))return'—';return fmt(Math.round(net*t/1000))+' тис.₴';}}

  const cropsGrid=document.getElementById('cropsGrid');
  if(cropsGrid){{
    cropsGrid.innerHTML='';
    D.cultures.forEach((culture,idx)=>{{
      const d=D.prices[culture];
      const emoji=d?d.emoji:'🌾';
      const rank=idx+1;
      if(!d){{cropsGrid.innerHTML+=`<div class="crop-card"><div class="crop-header"><div class="crop-icon-name"><span class="crop-emoji">${{emoji}}</span><span class="crop-name">${{culture}}</span></div><span class="crop-rank">#${{rank}}</span></div><div class="crop-body" style="color:var(--fg3);padding:12px;font-size:12px">Немає даних</div></div>`;return;}}
      const netK=d.best_net_kopani;const netD=d.best_net_dolynske;
      const thresh=d.sell_threshold||10000;
      const above=netK>=thresh;
      const sigLabel=above?'🟢 Продавати':(netK>=thresh*0.9?'🟡 Частково':'⚪ Чекати');
      const top3=(d.top_records||[]).slice(0,3);
      const rows=top3.map(r=>`<tr><td>${{(r.location||'?').substring(0,22)}}</td><td class="num">${{fmt(r.price_uah)}} ₴</td><td class="num" style="color:var(--green)">${{fmt(r.net_kopani)}} ₴</td><td style="color:var(--fg3);font-size:10px">${{r.source||''}}</td></tr>`).join('');
      cropsGrid.innerHTML+=`<div class="crop-card"><div class="crop-header"><div class="crop-icon-name"><span class="crop-emoji">${{emoji}}</span><span class="crop-name">${{culture.charAt(0).toUpperCase()+culture.slice(1)}}</span></div><span class="crop-rank ${{rank<=2?'top':''}}">#${{rank}}</span></div><div class="crop-body"><div class="price-row"><span class="price-label">Найкраща ціна</span><span class="price-val best">${{fmt(d.best_price_uah)}} ₴/т</span></div><div class="price-row"><span class="price-label">${{(d.best_price_loc||'').substring(0,28)}}</span><span class="price-label" style="font-size:10px;color:var(--fg3)">${{d.best_price_src||''}}</span></div><div class="divider"></div><div class="net-block"><div class="net-label">Чиста виручка (рейс 25 т)</div><div class="net-row"><span class="net-farm">📍 Копані</span><div><span class="net-val">${{fmt(netK)}} ₴/т</span><span class="net-trip"> → ${{fmtTrip(netK)}}</span></div></div><div class="net-divider"></div><div class="net-row"><span class="net-farm">📍 Долинське</span><div><span class="net-val" style="color:var(--accent2)">${{fmt(netD)}} ₴/т</span><span class="net-trip"> → ${{fmtTrip(netD)}}</span></div></div><div class="net-threshold ${{above?'above':'below'}}">Поріг: ${{fmt(thresh)}} ₴/т | ${{sigLabel}}</div></div>${{rows?`<div style="margin-top:8px;overflow-x:auto"><table class="tg-table" style="font-size:11px"><thead><tr><th>Пункт</th><th>Ціна</th><th>Net Копані</th><th>Джерело</th></tr></thead><tbody>${{rows}}</tbody></table></div>`:''}} <div style="font-size:10px;color:var(--fg3);margin-top:6px;text-align:right">${{d.records_count}} записів · ${{fmt(d.price_min)}}–${{fmt(d.price_max)}} ₴/т</div></div></div>`;
    }});
  }}

  const tgBody=document.getElementById('tgBody');
  const tgFilters=document.getElementById('tgFilters');
  const tgInsights=document.getElementById('tgInsights');
  const tgSub=document.querySelector('#tgSection .sec-sub');
  if(tgBody&&D.tg_records&&D.tg_records.length>0){{
    if(tgSub)tgSub.textContent='Автооновлення щодня о 07:00 · '+D.generated_at;
    const culturesInData=[...new Set(D.tg_records.map(r=>r.culture).filter(Boolean))];
    if(tgFilters)tgFilters.innerHTML='<button class="tg-chip active" onclick="tgFilter(null,this)">Всі</button>'+culturesInData.map(c=>`<button class="tg-chip" onclick="tgFilter('${{c}}',this)">${{c}}</button>`).join('');
    window.renderTgRows=function(fc){{
      const rows=fc?D.tg_records.filter(r=>r.culture===fc):D.tg_records;
      tgBody.innerHTML=rows.map(r=>`<tr><td style="color:var(--accent);white-space:nowrap">${{r.source||'?'}}</td><td>${{r.culture||'?'}}</td><td class="num">${{r.price_uah?fmt(r.price_uah)+' ₴':r.price_usd?r.price_usd+'$':'—'}}</td><td style="font-size:11px">✅ з ПДВ</td><td>${{(r.location||'?').substring(0,30)}}</td><td style="color:var(--fg3)">${{(r.date||'?').substring(0,10)}}</td><td style="font-size:11px;color:var(--fg3)">${{r.basis||''}} ${{r.region_norm&&r.region_norm!=='невідомо'?'· '+r.region_norm:''}}</td></tr>`).join('');
    }}
    window.renderTgRows(null);
    window.tgFilter=function(c,btn){{document.querySelectorAll('.tg-chip').forEach(b=>b.classList.remove('active'));btn.classList.add('active');window.renderTgRows(c);}};
    if(tgInsights)tgInsights.innerHTML=D.cultures.map(c=>{{const d=D.prices[c];if(!d)return'';return`<div class="tg-insight"><strong>${{d.emoji}} ${{c.charAt(0).toUpperCase()+c.slice(1)}}:</strong> ${{fmt(d.best_price_uah)}} ₴/т · net Копані <strong>${{fmt(d.best_net_kopani)}} ₴/т</strong> (${{fmtTrip(d.best_net_kopani)}} за рейс)</div>`;}} ).filter(Boolean).join('');
  }}else if(tgBody){{tgBody.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--fg3);padding:20px">Запусти telegram_parser.py для завантаження цін</td></tr>';}}

  const land=D.land;
  if(land&&land.records&&land.records.length>0){{
    const stats=land.stats;
    const rows=land.records.slice(0,10).map(r=>`<tr><td>${{r.type==='продаж'?'💰':'📋'}} ${{r.district||'?'}}</td><td>${{r.size_ha?r.size_ha.toFixed(2)+' га':'?'}}</td><td class="num">${{r.price_per_ha?fmt(r.price_per_ha)+' ₴/га':'—'}}</td><td class="num">${{r.rent_per_lot?fmt(r.rent_per_lot)+' ₴':'—'}}</td><td class="num">${{r.yield_pct?r.yield_pct.toFixed(1)+'%':'—'}}</td><td style="color:var(--fg3);font-size:10px">${{r.source||'?'}}</td></tr>`).join('');
    const sec=document.createElement('div');sec.className='tg-section';
    sec.innerHTML=`<div class="sec-head"><div class="sec-title">🏡 Земельний ринок — Кіровоградська обл.</div><div class="sec-sub">Моніторинг паїв · ${{D.generated_at}}</div></div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px"><div class="signal-card"><div class="signal-name">Лотів</div><div class="signal-val">${{stats.total_lots}}</div><div class="signal-sub">${{stats.sale_lots}} продаж · ${{stats.rent_lots}} оренда</div></div><div class="signal-card"><div class="signal-name">Ціна паю</div><div class="signal-val">${{fmt(stats.avg_price_ha)}} ₴/га</div><div class="signal-sub">≈ ${{fmt(Math.round(stats.avg_price_ha/USD_UAH))}} $/га</div></div><div class="signal-card"><div class="signal-name">Дохідність</div><div class="signal-val" style="color:var(--green)">${{stats.max_yield?stats.max_yield.toFixed(1)+'%':'—'}}</div><div class="signal-sub">макс.</div></div></div><div class="tg-table-wrap"><table class="tg-table" style="min-width:500px"><thead><tr><th>Тип/Район</th><th>Площа</th><th>Ціна/га</th><th>Оренда/пай</th><th>Дохідність</th><th>Джерело</th></tr></thead><tbody>${{rows}}</tbody></table></div>`;
    const calc=document.getElementById('calcSection');
    if(calc)calc.parentNode.insertBefore(sec,calc);else{{const m=document.querySelector('.main');if(m)m.appendChild(sec);}}
  }}

  window.__PRICES__=D.prices;window.__FREIGHT__=D.freight;window.__USD_UAH__=D.usd_uah;
  window.runCalc=function(){{
    const crop=document.getElementById('calcCrop')?.value;
    const farm=document.getElementById('calcFarm')?.value;
    const dir=document.getElementById('calcDir')?.value;
    const tons=parseFloat(document.getElementById('calcTons')?.value||25);
    let price=parseFloat(document.getElementById('calcPrice')?.value);
    const dirMap={{kernel:'Кіровоградська',cherkasy:'Черкаська',mykolaiv:'Миколаївська',odesa:'Одеська'}};
    const cropMap={{rapeseed:'ріпак',sunflower:'соняшник',soy:'соя',corn:'кукурудза',barley:'ячмінь',wheat:'пшениця'}};
    const cn=cropMap[crop]||crop;const rn=dirMap[dir]||'невідомо';const fn=farm==='dolynske'?'Долинське':'Копані';
    if(isNaN(price)){{const pd=D.prices[cn];price=pd?pd.best_price_uah:0;}}
    const freight=(D.freight[fn]||{{}})[rn]||800;
    const net_t=price-freight;const net_tot=net_t*tons;
    const el=document.getElementById('calcResult');if(!el)return;
    el.style.display='block';
    el.innerHTML=`<div class="calc-res-grid"><div class="calc-res-item"><div class="calc-res-label">Ціна закупки</div><div class="calc-res-val">${{fmt(price)}} ₴/т</div><div class="calc-res-sub">${{cn}}</div></div><div class="calc-res-item"><div class="calc-res-label">Фрахт (${{fn}} → ${{rn}})</div><div class="calc-res-val" style="color:var(--red)">− ${{fmt(freight)}} ₴/т</div><div class="calc-res-sub">${{tons}} т</div></div><div class="calc-res-item"><div class="calc-res-label">Net за тонну</div><div class="calc-res-val" style="color:var(--green)">${{fmt(net_t)}} ₴/т</div></div><div class="calc-res-item"><div class="calc-res-label">Рейс ${{tons}} т</div><div class="calc-res-val">${{fmt(net_tot)}} ₴</div></div></div><div class="calc-warn">⚠️ Орієнтовний розрахунок — перевір ціну напряму з покупцем.</div>`;
  }};
}})();
</script>"""

def main():
    print("=== AGRO BAROMETER — Build HTML (template injection) ===")
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    if not TEMPLATE.exists():
        print(f"❌ Шаблон не знайдено: {TEMPLATE}")
        return 1

    template_html = TEMPLATE.read_text(encoding="utf-8")
    print(f"✅ Шаблон: {TEMPLATE} ({len(template_html):,} символів)")

    tg_data  = load_json("telegram_prices.json", {"records":[],"by_culture":{}})
    web_data = load_json("web_prices.json", {"records":[]})
    land_raw = load_json("land_data.json", {"records":[]})

    tg_records = tg_data.get("records",[])
    if not tg_records:
        for v in tg_data.get("by_culture",{}).values(): tg_records.extend(v)

    all_records = tg_records + web_data.get("records",[])
    print(f"   Telegram: {len(tg_records)} | Web: {len(web_data.get('records',[]))} | Земля: {len(land_raw.get('records',[]))}")

    prices   = best_prices(all_records)
    land_out = prepare_land(land_raw)

    agro_data = {
        "generated_at": now_utc,
        "usd_uah": USD_UAH,
        "cultures": CULTURES,
        "prices": prices,
        "freight": FREIGHT,
        "sell_threshold": SELL_THRESHOLD,
        "land": land_out,
        "tg_records": sorted(
            [r for r in all_records if r.get("source","").startswith("@")],
            key=lambda x: x.get("date",""), reverse=True
        )[:50],
    }

    patched = re.sub(
        r'(<span class="meta-dot live"></span>\s*)[\d.]+',
        lambda m: m.group(1) + now_str.split()[0], template_html
    )
    patched = re.sub(
        r'(НБУ:.*?<strong>)[\d,]+(\s*₴/\$)',
        lambda m: m.group(1) + f"{USD_UAH:,.2f}".replace(".",",") + m.group(2), patched
    )

    injection = build_injection(agro_data)
    patched = patched.replace("</body>", injection + "\n</body>") if "</body>" in patched else patched + injection

    with open("index.html","w",encoding="utf-8") as f: f.write(patched)
    kb = len(patched)/1024
    print(f"\n✅ index.html збудовано ({kb:.0f} КБ)")
    for c in CULTURES:
        d=prices.get(c)
        if d: print(f"   {d['emoji']} {c}: {d['best_price_uah']:,.0f} ₴ | net Копані {d['best_net_kopani']:,.0f} ₴ ({d['records_count']} записів)")
        else: print(f"   ⚪ {c}: немає даних")
    return 0

if __name__=="__main__": exit(main())
