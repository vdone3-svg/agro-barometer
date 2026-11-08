"""
AGRO BAROMETER — збірка index.html
Шаблон barometer_template.html + ін'єкція живих даних (window.__AGRO_DATA__).

Принципи:
  • «Найкраща ціна» — лише з порівнюваних закупівельних оферт (не ціни продавців, не олія/шрот,
    не експортні DAP/DAF/FOB на кордоні, не явні викиди).
  • Net рахується лише коли відомий регіон покупця і для нього є ставка фрахту — ставку не вигадуємо.
  • Статичні дати шаблону НЕ переписуються на сьогоднішню (раніше старий контент видавався за свіжий).
  • Увесь текст із зовнішніх джерел екранується перед вставкою в HTML.
  • prices_history.json — персистентний архів знімків «найкращої ціни» по 6 культурах,
    зберігається в git main, забезпечує дельту тиждень/місяць без зовнішнього сховища.
"""
import json, os, re
import crop_summaries
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
NBU_RATE = os.environ.get("NBU_USD_UAH")
USD_UAH  = float(NBU_RATE or os.environ.get("USD_UAH_RATE") or os.environ.get("USD_UAH") or "45.47")
RATE_SRC = f"НБУ {os.environ.get('NBU_DATE','')}".strip() if NBU_RATE else "з налаштувань (не НБУ)"
TEMPLATE = Path(os.environ.get("TEMPLATE_PATH", "barometer_template.html"))

CULTURES = ["ріпак", "соняшник", "соя", "кукурудза", "ячмінь", "пшениця"]
CULTURE_EMOJI = {"ріпак":"💛","соняшник":"🌻","соя":"🫘","кукурудза":"🌽","ячмінь":"🌾","пшениця":"🌱"}

# Ставки найманого зерновоза 25 т, грн/т з ПДВ — ОЦІНКА, НЕ ОФЕРТА ПЕРЕВІЗНИКА.
# База: Укрвантаж АГРО (Latifundist, квіт.–трав. 2026) + ~8% на паливо. Дизель із квітня зріс ~16%
# (90,3 → 104,5 ₴/л на 30.10.2026), а ставки на 500+ км у жовтні сягали 3 000–3 700 ₴/т, тож
# далекі маршрути, ймовірно, занижені. Замінити на підтверджені ставки перевізників (FREIGHT_CONFIRMED).
# Ізмаїл/Рені (~600 км) винесені в «Дунай» без ставки: net для них не рахується, доки немає реальної ціни.
FREIGHT = {
    "Долинське":{"Одеська":1620,"Черкаська":570,"Миколаївська":1130,"Кіровоградська":300,"Вінницька":755,"Хмельницька":970,"Полтавська":650},
    "Копані":   {"Одеська":1510,"Черкаська":405,"Миколаївська":1055,"Кіровоградська":115,"Вінницька":650,"Хмельницька":810,"Полтавська":490},
}
FREIGHT_STATUS = "оцінка"   # "оцінка" | "підтверджено ДД.ММ.РРРР"
REGION_MAP = {"ізмаїл":"Дунай","измаил":"Дунай","рені":"Дунай","рени":"Дунай","орлівк":"Дунай","кілія":"Дунай","бессараб":"Дунай",
              "одес":"Одеська","тіс ":"Одеська","тис вуг":"Одеська","південн":"Одеська","чорноморськ":"Одеська","черкас":"Черкаська","миколаїв":"Миколаївська","кіровоград":"Кіровоградська","кропивниц":"Кіровоградська","олександрі":"Кіровоградська","знам.янк":"Кіровоградська",
              "вінниц":"Вінницька","хмельниц":"Хмельницька","полтав":"Полтавська","дніпро":"Дніпропетровська",
              "київськ":"Київська","житомир":"Житомирська","запоріз":"Запорізька","харків":"Харківська"}

# Санітарні межі ₴/т — лише щоб відсіяти помилки парсингу (олія, тонни, номери лотів), не «очікувані ціни»
SANITY = {"ріпак":(12000,32000),"соняшник":(9000,30000),"соя":(10000,30000),
          "кукурудза":(3500,13000),"ячмінь":(3500,13000),"пшениця":(3500,14000)}
EXPORT_BASIS = re.compile(r"\b(DAP|DAF|FOB|CIF|CFR|DDP)\b", re.I)
SELLER_HINT  = re.compile(r"\bпродам\b", re.I)
NON_CROP     = re.compile(r"олі[яїює]|шрот|макуха|жмих|насінн|тверд", re.I)


HISTORY_FILE = Path("prices_history.json")
HISTORY_KEEP_DAYS = 35  # зберігаємо ~35 днів знімків


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── Дельта-трекер ────────────────────────────────────────────────────────────

def _snapshot_from_prices(prices: dict, date_str: str) -> dict:
    """Формує компактний знімок best_price по кожній культурі."""
    snap = {"date": date_str, "prices": {}}
    for c, d in prices.items():
        if d and d.get("best_price"):
            snap["prices"][c] = {
                "uah": d["best_price"]["price_uah"],
                "src": d["best_price"].get("source", ""),
            }
    return snap


def load_history() -> list:
    """Завантажує список знімків із prices_history.json (або порожній список)."""
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data.get("snapshots", [])
        except Exception as e:
            print(f"  ⚠️ prices_history.json пошкоджено: {e} — починаємо заново")
    return []


def _snap_date(s):
    try:
        return datetime.strptime(s.get("date", ""), "%d.%m.%Y").date()
    except ValueError:
        return None


def save_history(snapshots: list) -> None:
    """Зберігає знімки у prices_history.json, видаляє старіші за HISTORY_KEEP_DAYS."""
    cutoff = (datetime.now(KYIV) - timedelta(days=HISTORY_KEEP_DAYS)).date()
    fresh = [s for s in snapshots if (_d := _snap_date(s)) and _d >= cutoff]
    fresh.sort(key=_snap_date)
    HISTORY_FILE.write_text(
        json.dumps({"snapshots": fresh}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  📦 prices_history.json: {len(fresh)} знімків збережено")


def compute_deltas(prices: dict, snapshots: list, today_str: str) -> dict:
    """
    Повертає dict {культура: {delta_7: int|None, delta_30: int|None}}
    delta > 0 → ціна зросла, < 0 → впала, None → нема даних для порівняння.
    """
    def find_snap(days_ago: int) -> dict | None:
        # найсвіжіший знімок, якому щонайменше days_ago днів, але не старший за days_ago+3
        today = datetime.now(KYIV).date()
        cands = [s for s in snapshots if (d := _snap_date(s)) and days_ago <= (today - d).days <= days_ago + 3]
        return max(cands, key=_snap_date) if cands else None

    snap7  = find_snap(7)
    snap30 = find_snap(30)

    deltas = {}
    for c, d in prices.items():
        if not d or not d.get("best_price"):
            deltas[c] = {"delta_7": None, "delta_30": None}
            continue
        cur = d["best_price"]["price_uah"]
        d7  = cur - snap7["prices"][c]["uah"]  if snap7  and c in snap7.get("prices", {})  else None
        d30 = cur - snap30["prices"][c]["uah"] if snap30 and c in snap30.get("prices", {}) else None
        deltas[c] = {"delta_7": round(d7) if d7 is not None else None,
                     "delta_30": round(d30) if d30 is not None else None}
    return deltas


def normalize_region(raw):
    r = (raw or "").lower()
    for kw, name in REGION_MAP.items():
        if kw in r:
            return name
    return "невідомо"


def parse_date(s):
    """'05.11.2026 13:52' | '05.11.2026' → datetime (Kyiv) або None."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?", s or "")
    if not m:
        return None
    d, mo, y, hh, mm = m.groups()
    try:
        return datetime(int(y), int(mo), int(d), int(hh or 12), int(mm or 0), tzinfo=KYIV)
    except ValueError:
        return None


MAX_OFFER_AGE_DAYS = 7


def classify(r):
    """Повертає (eligible: bool, reason: str|None) для участі у «найкращій ціні»."""
    dt = parse_date(r.get("date"))
    if dt and (datetime.now(KYIV) - dt).days > MAX_OFFER_AGE_DAYS:
        return False, f"застаріла ({dt.strftime('%d.%m')})"
    if r.get("ref_kind") == "national_avg":
        return False, "середня по Україні — орієнтир, не оферта"
    c = r.get("culture")
    p = r.get("price_uah")
    if c not in SANITY or not isinstance(p, (int, float)):
        return False, "без культури/ціни"
    lo, hi = SANITY[c]
    if not (lo <= p <= hi):
        return False, f"поза межами {lo}–{hi}"
    basis = str(r.get("basis") or "")
    if EXPORT_BASIS.search(basis):
        return False, f"експортний базис {basis}"
    q = str(r.get("quality") or "")
    if NON_CROP.search(q) or SELLER_HINT.search(q):
        return False, "не насіння культури / ціна продавця"
    if c == "соняшник" and re.search(r"високоолеїн|вис\.?\s*ол", q, re.I):
        return False, "високоолеїновий — окремий продукт"
    return True, None


def enrich(records):
    """Нормалізує регіон, рахує net (лише з відомим фрахтом), дедуплікує повтори постів."""
    out, seen = [], {}
    for r in records:
        r = dict(r)
        region = normalize_region(f'{r.get("location") or ""} {r.get("region") or ""}')
        r["region_norm"] = region
        fk, fd = FREIGHT["Копані"].get(region), FREIGHT["Долинське"].get(region)
        r["freight_kopani"], r["freight_dolynske"] = fk, fd
        r["net_kopani"]   = r["price_uah"] - fk if fk is not None and r.get("price_uah") else None
        r["net_dolynske"] = r["price_uah"] - fd if fd is not None and r.get("price_uah") else None
        ok, why = classify(r)
        r["eligible"], r["excluded_reason"] = ok, why
        dt = parse_date(r.get("date"))
        r["ts"] = dt.isoformat() if dt else ""
        # той самий пост з тією самою ціною в різні дні → лишаємо найсвіжіший
        key = (r.get("source"), r.get("culture"), (r.get("location") or "")[:25].lower(), r.get("price_uah"), r.get("quality"))
        if key in seen:
            if r["ts"] > out[seen[key]]["ts"]:
                out[seen[key]] = r
            continue
        seen[key] = len(out)
        out.append(r)
    return out


def _slim(r):
    keys = ("source","culture","quality","price_raw","price_uah","currency","basis","vat","location",
            "region_norm","date","ts","url","buyer","volume_t","net_kopani","net_dolynske",
            "freight_kopani","freight_dolynske","eligible","excluded_reason","ref_kind")
    return {k: r.get(k) for k in keys}


def reference_prices(recs):
    """Середні по Україні (GrainTrade) — окремо від оферт; лише продукт культури, не «вис.ол.» тощо."""
    refs = [r for r in recs if r.get("ref_kind") == "national_avg"
            and SANITY[r["culture"]][0] <= r["price_uah"] <= SANITY[r["culture"]][1]
            and not (r["culture"] == "соняшник" and re.search(r"високоолеїн|вис\.?\s*ол", str(r.get("quality") or ""), re.I))]
    refs.sort(key=lambda x: -x["price_uah"])
    return [_slim(r) for r in refs[:6]]


def best_prices(records):
    result = {}
    for c in CULTURES:
        recs = [r for r in records if r.get("culture") == c]
        elig = [r for r in recs if r["eligible"]]
        refs = reference_prices(recs)
        if not elig:
            result[c] = {"emoji": CULTURE_EMOJI[c], "records_count": len(recs), "eligible_count": 0,
                         "excluded": len(recs), "top": [], "best_price": None, "reference": refs,
                         "best_net": {"Копані": None, "Долинське": None}} if recs else None
            continue
        by_price = sorted(elig, key=lambda x: x["ts"], reverse=True)      # за рівної ціни — свіжіша
        by_price = sorted(by_price, key=lambda x: -x["price_uah"])
        best_net = {}
        for farm, key in (("Копані","net_kopani"), ("Долинське","net_dolynske")):
            with_net = [r for r in elig if r.get(key) is not None]
            best_net[farm] = _slim(max(with_net, key=lambda x: x[key])) if with_net else None
        prices = [r["price_uah"] for r in elig]
        result[c] = {
            "emoji": CULTURE_EMOJI[c],
            "best_price": _slim(by_price[0]),
            "best_net": best_net,
            "price_min": min(prices), "price_max": max(prices),
            "records_count": len(recs), "eligible_count": len(elig), "excluded": len(recs) - len(elig),
            "sources": sorted({r.get("source","?") for r in elig}),
            "top": [_slim(r) for r in by_price[:6]],
            "reference": refs,
        }
    return result


def prepare_land(land):
    recs = land.get("records", [])
    if not recs:
        return {"records": [], "stats": {}, "generated_at": land.get("generated_at","")}
    sales = [r for r in recs if r.get("type") == "продаж"]
    # ціна/га, явно нижча за 20 тис. ₴, — це орендна плата, розпізнана як ціна; у статистику не беремо
    prices_ha = [r["price_per_ha"] for r in sales if r.get("price_per_ha") and r["price_per_ha"] >= 20000]
    yields    = [r["yield_pct"] for r in sales if r.get("yield_pct")]
    stats = {
        "total_lots": len(recs), "sale_lots": len(sales), "rent_lots": len(recs) - len(sales),
        "avg_price_ha": round(sum(prices_ha)/len(prices_ha)) if prices_ha else None,
        "n_price": len(prices_ha),
        "min_price_ha": min(prices_ha) if prices_ha else None,
        "max_price_ha": max(prices_ha) if prices_ha else None,
        "max_yield": max(yields) if yields else None,
    }
    return {"records": recs, "stats": stats, "generated_at": land.get("generated_at","")}


INJECTION_JS = r"""
(function(){
  const D=window.__AGRO_DATA__;
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl=u=>/^https?:\/\//i.test(u||'')?esc(u):'';
  const fmt=(n,d=0)=>(n==null||isNaN(n))?'—':new Intl.NumberFormat('uk-UA',{minimumFractionDigits:d,maximumFractionDigits:d}).format(n);
  const trip=(net,t=25)=>(net==null||isNaN(net))?'':' → '+fmt(Math.round(net*t/1000))+' тис.₴';
  const ageDays=ts=>{if(!ts)return null;return Math.floor((Date.now()-new Date(ts).getTime())/864e5);};
  const ageFlag=ts=>{const a=ageDays(ts);if(a==null)return'<span class="flag flag-warn">дата?</span>';if(a>=2)return`<span class="flag flag-warn">${a} дн. тому</span>`;return'';};
  const ra=u=>{const s=safeUrl(u);return s?` class="row-link" data-url="${s}" title="Відкрити пропозицію"`:'';};
  const go=u=>{const s=safeUrl(u);return s?`<a class="go" href="${s}" target="_blank" rel="noopener" title="Відкрити">↗</a>`:'';};
  const srcLabel=u=>/t\.me\//.test(u||'')?'пост у Telegram':/graintrade\.com\.ua\/birzha/.test(u||'')?'лот на біржі GrainTrade':/nibulon/.test(u||'')?'прайс Нібулону':/e-zerno/.test(u||'')?'сторінка цін e-zerno':'джерело';
  const openBtn=(u,label)=>{const s=safeUrl(u);return s?`<a class="open-btn" href="${s}" target="_blank" rel="noopener">${label||'Відкрити'}: ${srcLabel(u)} ↗</a>`:'<span class="open-btn off">посилання на джерело відсутнє</span>';};
  // рядок-посилання: клік по всьому рядку відкриває пропозицію
  document.addEventListener('click',e=>{const tr=e.target.closest('tr.row-link');if(!tr||e.target.closest('a'))return;window.open(tr.dataset.url,'_blank','noopener');});
  if(!document.getElementById('rowLinkCss')){const st=document.createElement('style');st.id='rowLinkCss';st.textContent=`
    tr.row-link{cursor:pointer}
    tr.row-link:hover td{background:var(--surface2)}
    .go{display:inline-block;color:var(--accent)!important;font-weight:700;margin-right:5px;text-decoration:none;padding:0 2px}
    .open-btn{display:block;margin:6px 0 2px;padding:7px 10px;border-radius:8px;background:var(--accent);color:#fff!important;font-size:12px;font-weight:600;text-align:center;text-decoration:none}
    .open-btn:hover{filter:brightness(1.1)}
    .open-btn.off{background:var(--surface2);color:var(--fg3)!important;font-weight:400}`;document.head.appendChild(st);}
  const link=(u,txt)=>{const s=safeUrl(u);return s?`<a href="${s}" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline dotted">${txt}</a>`:txt;};
  let farm='Долинське';const cropFarm={};
  try{Object.assign(cropFarm,JSON.parse(localStorage.getItem('agroCropFarm')||'{}'));}catch(e){}

  // ── Шапка: дата збірки + курс ──
  const banner=document.getElementById('statusBanner');
  if(banner)banner.insertAdjacentHTML('beforeend',` <br><span style="opacity:.85">Дані зібрано: <strong>${esc(D.generated_at_kyiv)}</strong> · записів цін: ${D.counts.prices} (порівнюваних ${D.counts.eligible}) · новин: ${D.counts.news} · курс $: ${fmt(D.usd_uah,2)} (${esc(D.rate_src)})</span>`);

  // ── Культури ──
  function renderCrops(){
    const g=document.getElementById('cropsGrid');if(!g)return;
    g.innerHTML=D.cultures.map((c,idx)=>{
      const farm=cropFarm[c]||'Долинське';
      const d=D.prices[c];const title=c.charAt(0).toUpperCase()+c.slice(1);
      const tg=`<div class="farm-toggle crop-farm">${['Долинське','Копані'].map(f=>`<button class="farm-btn${f===farm?' active':''}" data-crop="${esc(c)}" data-farm="${f}">${f}</button>`).join('')}</div>`;
      const head=`<div class="crop-header"><div class="crop-icon-name"><span class="crop-emoji">${d?d.emoji:'🌾'}</span><span class="crop-name">${esc(title)}</span></div>${tg}</div>`;
      const refBlock=(d&&d.reference&&d.reference.length)?`<div class="crop-ref" style="margin-top:8px;padding:6px 8px;border:1px dashed var(--fg3);border-radius:6px;font-size:11px">
          <div style="color:var(--fg3);margin-bottom:3px" title="Середні закупівельні ціни по Україні за базисом. Не пропозиція конкретного покупця; пункт і фрахт невідомі — net не рахується.">Орієнтир: середні по Україні (GrainTrade, ${esc((d.reference[0].date||'').substring(0,5))}) — не оферта, net не рахується</div>
          ${d.reference.map(r=>`<div style="display:flex;justify-content:space-between;gap:8px"><span>${link(r.url,esc(r.basis||'')+(r.quality?' · '+esc(String(r.quality).substring(0,22)):''))}</span><span class="num">${fmt(r.price_uah)} ₴/т</span></div>`).join('')}
        </div>`:'';
      if(!d||!d.best_price){
        const why=d?(d.reference&&d.reference.length&&d.reference.length===d.records_count?'Є лише середні ціни по Україні, пропозицій конкретних покупців немає':`${d.records_count} знайдених записів, але жоден не пройшов перевірку порівнюваності`):'За 3 дні жодної закупівельної ціни не знайдено';
        return `<div class="crop-card">${head}<div class="crop-body" style="color:var(--fg3);font-size:12px;padding:6px 0">Немає порівнюваних пропозицій покупців.<br>${esc(why)}.</div>${refBlock}</div>`;
      }
      const b=d.best_price;
      const netRow=(f)=>{const r=d.best_net[f];
        if(!r)return `<div class="net-row"><span class="net-farm">📍 ${f}</span><span class="net-farm" style="color:var(--fg3)">фрахт до покупців невідомий</span></div>`;
        const fr=f==='Копані'?r.freight_kopani:r.freight_dolynske;const net=f==='Копані'?r.net_kopani:r.net_dolynske;
        return `<div class="net-row"><span class="net-farm" style="font-weight:700">📍 ${f}</span><div><span class="net-val">${fmt(net)} ₴/т</span><span class="net-trip">${trip(net)}</span></div></div>
          <div style="font-size:10px;color:var(--fg3);text-align:right;margin-top:-2px">${link(r.url,esc(r.location)+(safeUrl(r.url)?' ↗':''))} (${esc(r.region_norm)}) ${fmt(r.price_uah)} − фрахт ${fmt(fr)}${D.freight_status==='оцінка'?' <span title="орієнтовна ставка, не оферта перевізника">(оцінка)</span>':''} · ${esc(r.source)}</div>`;};
      const nk=farm==='Копані'?'net_kopani':'net_dolynske';
      const place=r=>{const l=r.location&&r.location!=='невідомо'?r.location:'';const bu=r.buyer&&r.buyer!==l?r.buyer:'';return (bu&&l?bu+' · '+l:(bu||l||'пункт не вказано'));};
      const rows=d.top.map(r=>`<tr${ra(r.url)}><td>${go(r.url)}${esc(place(r).substring(0,40))}<div style="font-size:10px;color:var(--fg3)">${esc(r.source)} · ${esc((r.date||'').substring(0,5))}${r.quality?' · '+esc(String(r.quality).substring(0,18)):''}</div></td><td class="num">${link(r.url,fmt(r.price_uah))}${r.currency!=='UAH'?`<div style="font-size:10px;color:var(--fg3);font-weight:400">${fmt(r.price_raw)} ${esc(r.currency)}</div>`:''}</td><td class="num" style="color:var(--green)">${r[nk]!=null?fmt(r[nk]):'<span style="color:var(--fg3);font-weight:400">—</span>'}</td></tr>`).join('');
      const dl=D.deltas&&D.deltas[c]?D.deltas[c]:{};
      const fmtDelta=(v,label)=>{if(v==null)return'';const cls=v>0?'delta-up':v<0?'delta-down':'delta-flat';const ar=v>0?'▲':v<0?'▼':'—';return `<span class="price-delta ${cls}" title="${label}">${ar} ${fmt(Math.abs(v))} ₴/т</span>`;};
      const deltaRow=(dl.delta_7!=null||dl.delta_30!=null)?`<div class="price-row" style="gap:6px;flex-wrap:wrap"><span class="price-label" style="font-size:10px">Зміна:</span>${fmtDelta(dl.delta_7,'За тиждень')}${dl.delta_30!=null?`<span style="font-size:9px;color:var(--fg3)">місяць: ${fmtDelta(dl.delta_30,'За місяць')}</span>`:''}</div>`:'';
      return `<div class="crop-card">${head}<div class="crop-body">
        <div class="price-row"><span class="price-label">Найвища закупівельна</span><span class="price-val best">${link(b.url,fmt(b.price_uah)+' ₴/т')}</span></div>
        ${deltaRow}
        <div class="price-row"><span class="price-label">${esc(place(b).substring(0,40))}</span><span class="price-label" style="font-size:10px;color:var(--fg3)">${esc(b.source)} · ${esc(b.basis||'базис?')} ${ageFlag(b.ts)}</span></div>
        ${openBtn(b.url,'Відкрити найвищу пропозицію')}
        <div class="divider"></div>
        <div class="net-block"><div class="net-label">Найкраща чиста виручка з ${farm==='Копані'?'Копанів':'Долинського'} (рейс 25 т)</div>${netRow(farm)}</div>
        <div style="margin-top:8px"><table class="tg-table crop-table" style="font-size:11px"><colgroup><col style="width:56%"><col style="width:22%"><col style="width:22%"></colgroup><thead><tr><th>Пункт / покупець</th><th style="text-align:right">Ціна ₴/т</th><th style="text-align:right">Net ${farm==='Копані'?'Коп.':'Дол.'}</th></tr></thead><tbody>${rows}</tbody></table></div>
        <div style="font-size:10px;color:var(--fg3);margin-top:6px;text-align:right">${d.eligible_count} порівнюваних із ${d.records_count} · ${fmt(d.price_min)}–${fmt(d.price_max)} ₴/т${d.excluded?` · відсіяно ${d.excluded}`:''}</div>
        ${refBlock}
      </div></div>`;
    }).join('');
  }
  renderCrops();
  document.addEventListener('click',e=>{const b=e.target.closest('.crop-farm .farm-btn');if(!b)return;
    cropFarm[b.dataset.crop]=b.dataset.farm;try{localStorage.setItem('agroCropFarm',JSON.stringify(cropFarm));}catch(_){}
    const y=b.getBoundingClientRect().top;renderCrops();
    const nb=document.querySelector(`.crop-farm .farm-btn[data-crop="${CSS.escape(b.dataset.crop)}"][data-farm="${CSS.escape(b.dataset.farm)}"]`);
    if(nb)window.scrollBy(0,nb.getBoundingClientRect().top-y);});
  if(!document.getElementById('cropFarmCss')){const st=document.createElement('style');st.id='cropFarmCss';st.textContent=`
    .crop-header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
    .crop-farm{display:inline-flex}.crop-farm .farm-btn{padding:7px 11px;font-size:12px;min-height:34px}
    @media(max-width:480px){.sum-grid{grid-template-columns:1fr}.sum-card p{font-size:14px}.crops-grid{grid-template-columns:1fr!important}}`;document.head.appendChild(st);}
  // ── Висновки барометра по культурах (щоденні) ──
  (function(){
    const S=D.summaries;const grid=document.getElementById('cropsGrid');if(!S||!grid)return;
    const md=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
    const cls={sell:'v-sell',split:'v-split',hold:'v-hold',none:'v-split'};
    const auto=D.cultures.some(c=>S[c]&&S[c].auto);
    const cards=D.cultures.map(c=>{const s=S[c];if(!s)return'';const d=D.prices[c];const title=c.charAt(0).toUpperCase()+c.slice(1);
      return `<div class="sum-card"><div class="sum-top"><span class="sum-name">${d?d.emoji:'🌾'} ${esc(title)}</span><span class="sum-verdict ${cls[s.verdict]||'v-split'}">${esc(s.label)}</span></div>
        ${(s.paragraphs||[]).map(p=>`<p>${md(p)}</p>`).join('')}
        ${s.todo?`<div class="sum-do">${md(s.todo)}</div>`:''}</div>`;}).join('');
    const sec=document.createElement('div');sec.className='sum-section';sec.id='summaryLive';
    sec.innerHTML=`<div class="sec-head"><div class="sec-title">🧑‍🌾 Висновок барометра по культурах — на ${esc(D.generated_at_kyiv)}</div>
      <div class="sec-sub">${auto?'Пишеться щоранку автоматично з сьогоднішніх цін і новин; цифри звірені з даними барометра.':'Сьогодні автоматичний висновок не сформувався — показано лише факти.'} Ціни — опубліковані пропозиції, не угоди${D.freight_status==='оцінка'?'; фрахт — орієнтовна оцінка':''}. Це аналітична думка, остаточне рішення — за вами.</div></div>
      <div class="sum-grid">${cards}</div>`;
    const main=document.querySelector('.main');if(main)main.insertBefore(sec,main.firstChild);else{const host=grid.parentNode;host.parentNode.insertBefore(sec,host);}
  })();


  // ── Telegram-оферти ──
  const tgBody=document.getElementById('tgBody'),tgFilters=document.getElementById('tgFilters'),tgInsights=document.getElementById('tgInsights');
  const live=(D.tg_records||[]);
  if(tgBody&&live.length){
    const sub=document.querySelector('#tgSection .sec-sub');if(sub)sub.textContent='Живі пости каналів за 3 дні · зібрано '+D.generated_at_kyiv+' · сірим — не порівнюються (експорт, викид тощо)';
    const cs=[...new Set(live.map(r=>r.culture))].filter(Boolean);
    if(tgFilters)tgFilters.innerHTML='<button class="tg-chip active" data-c="">Всі</button>'+cs.map(c=>`<button class="tg-chip" data-c="${esc(c)}">${esc(c)}</button>`).join('');
    const render=fc=>{tgBody.innerHTML=live.filter(r=>!fc||r.culture===fc).map(r=>`<tr${ra(r.url)} style="${r.eligible?'':'opacity:.5'}" title="${esc(r.excluded_reason||'')}"><td style="color:var(--accent);white-space:nowrap">${link(r.url,esc(r.source))}</td><td>${esc(r.culture)}${r.quality?`<div style="font-size:10px;color:var(--fg3)">${esc(String(r.quality).substring(0,22))}</div>`:''}</td><td class="num">${fmt(r.price_uah)} ₴${r.currency!=='UAH'?`<div style="font-size:10px;color:var(--fg3)">${fmt(r.price_raw)} ${esc(r.currency)}</div>`:''}</td><td style="font-size:11px">${esc(r.vat&&r.vat!=='невідомо'?r.vat:(/ПДВ/.test(r.basis||'')?'з ПДВ':'невідомо'))}</td><td>${esc((r.location&&r.location!=='невідомо'?r.location:(r.buyer||'?')).substring(0,30))}</td><td style="color:var(--fg3);white-space:nowrap">${esc(r.date||'?')}</td><td style="font-size:11px;color:var(--fg3)">${esc(r.basis||'')}${r.region_norm&&r.region_norm!=='невідомо'?' · '+esc(r.region_norm):''}${r.excluded_reason?' · '+esc(r.excluded_reason):''}</td></tr>`).join('');};
    render('');
    if(tgFilters)tgFilters.onclick=e=>{const b=e.target.closest('.tg-chip');if(!b)return;tgFilters.querySelectorAll('.tg-chip').forEach(x=>x.classList.remove('active'));b.classList.add('active');render(b.dataset.c);};
  }
  if(tgInsights)tgInsights.innerHTML=D.cultures.map(c=>{const d=D.prices[c];if(!d||!d.best_price)return'';const n=d.best_net[farm]||d.best_net['Долинське']||d.best_net['Копані'];
    return `<div class="tg-insight"><strong>${d.emoji} ${esc(c)}:</strong> найвища ${fmt(d.best_price.price_uah)} ₴/т (${esc(d.best_price.source)})${n?` · найкраща net ${fmt(n.net_dolynske??n.net_kopani)} ₴/т з Долинського — ${esc(n.location)}`:' · net: фрахт невідомий'}</div>`;}).join('');

  // ── Земля ──
  const land=D.land;
  if(land&&land.records&&land.records.length){
    const st=land.stats;
    const rows=land.records.slice(0,12).map(r=>`<tr${ra(r.url)}><td>${go(r.url)}${r.type==='продаж'?'💰':'📋'} ${esc(r.district||'?')}</td><td>${r.size_ha?Number(r.size_ha).toFixed(2)+' га':'?'}</td><td class="num">${r.price_per_ha?fmt(r.price_per_ha)+' ₴/га':'—'}</td><td class="num">${r.rent_per_lot?fmt(r.rent_per_lot)+' ₴':'—'}</td><td class="num">${r.yield_pct?Number(r.yield_pct).toFixed(1)+'%':'—'}</td><td style="color:var(--fg3);font-size:10px">${esc(r.source||'?')}</td></tr>`).join('');
    const sec=document.createElement('div');sec.className='tg-section';
    sec.innerHTML=`<div class="sec-head"><div class="sec-title">🏡 Земельний ринок — Кіровоградська обл.</div><div class="sec-sub">Telegram-лоти за 3 дні · оголошення, не угоди · натисніть рядок, щоб відкрити лот</div></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px">
      <div class="signal-card"><div class="signal-name">Лотів</div><div class="signal-val">${st.total_lots}</div><div class="signal-sub">${st.sale_lots} продаж · ${st.rent_lots} оренда</div></div>
      <div class="signal-card"><div class="signal-name">Ціна паю (сер.)</div><div class="signal-val">${st.avg_price_ha?fmt(st.avg_price_ha)+' ₴/га':'—'}</div><div class="signal-sub">${st.avg_price_ha?'≈ '+fmt(Math.round(st.avg_price_ha/D.usd_uah))+' $/га · n='+st.n_price:'недостатньо даних'}</div></div>
      <div class="signal-card"><div class="signal-name">Дохідність (макс.)</div><div class="signal-val" style="color:var(--green)">${st.max_yield?Number(st.max_yield).toFixed(1)+'%':'—'}</div><div class="signal-sub">заявлена в лоті</div></div></div>
      <div class="tg-table-wrap"><table class="tg-table" style="min-width:500px"><thead><tr><th>Тип/Район</th><th>Площа</th><th>Ціна/га</th><th>Оренда/пай</th><th>Дохідність</th><th>Джерело</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    const anchor=document.querySelector('.panels-row');if(anchor)anchor.parentNode.insertBefore(sec,anchor);
  }

  // ── Новини ──
  const ng=document.getElementById('newsGrid'),nst=document.getElementById('newsListStatic');
  const nsub=document.querySelector('#newsSection .sec-sub');
  if(ng&&D.news&&D.news.length){
    if(nst)nst.style.display='none';
    if(nsub)nsub.textContent=`Оновлено: ${D.news_generated_kyiv||D.generated_at_kyiv} · ${D.news.length} матеріалів за добу · тільки 6 культур і зерновий ринок`;
    ng.innerHTML=D.news.map(n=>{const u=safeUrl(n.url);const tag=u?'a':'div';
      return `<${tag} class="news-card" ${u?`href="${u}" target="_blank" rel="noopener"`:''}><div class="news-src" style="color:${String(n.source).startsWith('@')?'var(--accent)':'var(--green)'}">${esc(n.source)}</div><div class="news-title">${esc(n.title)}</div>${n.summary?`<div class="news-summary">${esc(n.summary)}</div>`:''}<div class="news-date">${esc(n.date||'')}</div></${tag}>`;}).join('');
  }else if(nsub){nsub.textContent='Свіжих новин за добу не знайдено — нижче статичний список джерел';}
})();
"""


def main():
    print("=== AGRO BAROMETER — Build HTML ===")
    now_utc = datetime.now(timezone.utc)
    now_kyiv = now_utc.astimezone(KYIV)
    if not TEMPLATE.exists():
        print(f"❌ Шаблон не знайдено: {TEMPLATE}")
        return 1
    html = TEMPLATE.read_text(encoding="utf-8")

    tg   = load_json("telegram_prices.json", {"records": []})
    web  = load_json("web_prices.json", {"records": []})
    land = load_json("land_data.json", {"records": []})
    news = load_json("news_data.json", {"items": []})

    records = enrich([r for r in tg.get("records", []) + web.get("records", []) if r.get("price_uah")])
    prices = best_prices(records)
    excluded = [r for r in records if not r["eligible"]]
    print(f"   Цін: {len(records)} (після дедупу) · порівнюваних {len(records)-len(excluded)} · відсіяно {len(excluded)}")

    # ── Дельта-трекер ────────────────────────────────────────────────────────
    today_str = now_kyiv.strftime("%d.%m.%Y")
    snapshots = load_history()
    deltas = compute_deltas(prices, snapshots, today_str)

    # Додаємо/замінюємо знімок поточного дня
    new_snap = _snapshot_from_prices(prices, today_str)
    snapshots = [s for s in snapshots if s.get("date") != today_str]
    snapshots.append(new_snap)
    save_history(snapshots)

    # Лог дельт
    for c in CULTURES:
        d7  = deltas.get(c, {}).get("delta_7")
        d30 = deltas.get(c, {}).get("delta_30")
        s7  = (f"{'▲' if d7>0 else '▼'}{abs(d7):,} ₴/т" if d7 else "—") if d7 is not None else "н/д"
        s30 = (f"{'▲' if d30>0 else '▼'}{abs(d30):,} ₴/т" if d30 else "—") if d30 is not None else "н/д"
        if d7 is not None or d30 is not None:
            print(f"   Δ {c}: тиждень {s7} · місяць {s30}")
    for r in sorted(excluded, key=lambda x: -x["price_uah"])[:12]:
        print(f"     ✂ {r['culture']} {r['price_uah']:,.0f} {r.get('source')} — {r['excluded_reason']}")

    news_items = news.get("items", [])[:50]
    ngen = news.get("generated_at", "")
    try:
        ngen_k = datetime.fromisoformat(ngen).astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
    except Exception:
        ngen_k = ""

    print("\n=== Висновки по культурах ===")
    summaries = crop_summaries.generate(CULTURES, prices, deltas, news_items, USD_UAH, today_str)

    tg_rows = sorted([_slim(r) for r in records if str(r.get("source","")).startswith("@")],
                     key=lambda x: x.get("ts",""), reverse=True)[:80]
    data = {
        "generated_at_kyiv": now_kyiv.strftime("%d.%m.%Y %H:%M") + " (Київ)",
        "usd_uah": USD_UAH, "rate_src": RATE_SRC,
        "cultures": CULTURES, "prices": prices, "freight": FREIGHT,
        "land": prepare_land(land), "tg_records": tg_rows,
        "news": news_items, "news_generated_kyiv": ngen_k,
        "counts": {"prices": len(records), "eligible": len(records)-len(excluded), "news": len(news_items)},
        "deltas": deltas,
        "summaries": summaries, "freight_status": FREIGHT_STATUS,
        "history_days": len(snapshots),
    }

    # Шапка: дата збірки і курс — це чесно поточні значення
    today = now_kyiv.strftime("%d.%m.%Y")
    html = re.sub(r'(<span class="meta-dot live"></span>\s*)[\d.]+', lambda m: m.group(1) + today, html, count=1)
    rate_txt = f"{USD_UAH:,.2f}".replace(",", " ").replace(".", ",")
    html = re.sub(r'(НБУ:\s*<strong>)[\d,\s]+(₴/\$)', lambda m: m.group(1) + rate_txt + " " + m.group(2), html, count=1)
    if not NBU_RATE:
        html = html.replace('<span class="meta-item">НБУ:', '<span class="meta-item" title="курс із налаштувань, не з НБУ">$:', 1)
    html = re.sub(r'Курс НБУ [\d.]+:</span>\s*<span class="rate-val">1 USD = [\d,]+ ₴',
                  f'Курс ({RATE_SRC}):</span>\n    <span class="rate-val">1 USD = {rate_txt} ₴', html, count=1)

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # не дати даним закрити <script>
    injection = f"\n<script>\nwindow.__AGRO_DATA__ = {payload};\n{INJECTION_JS}\n</script>\n"
    html = html.replace("</body>", injection + "</body>") if "</body>" in html else html + injection

    Path("index.html").write_text(html, encoding="utf-8")
    print(f"\n✅ index.html ({len(html)/1024:.0f} КБ) · курс {USD_UAH} ({RATE_SRC})")
    for c in CULTURES:
        d = prices.get(c)
        if d and d["best_price"]:
            bn = d["best_net"]["Долинське"]
            net_s = f"{bn['net_dolynske']:,.0f}" if bn else "—"
            print(f"   {d['emoji']} {c}: {d['best_price']['price_uah']:,.0f} ₴ ({d['best_price']['source']}) | "
                  f"net Долинське {net_s} | {d['eligible_count']}/{d['records_count']}")
        else:
            print(f"   ⚪ {c}: немає порівнюваних даних")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
