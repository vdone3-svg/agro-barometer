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

def _snapshot_from_prices(prices: dict, date_str: str, fuel: dict | None = None) -> dict:
    """Знімок дня: найвища пропозиція (uah), медіана порівнюваних (med), к-сть (n) + пальне."""
    snap = {"date": date_str, "prices": {}}
    for c, d in prices.items():
        if d and d.get("best_price"):
            snap["prices"][c] = {
                "uah": d["best_price"]["price_uah"],
                "src": d["best_price"].get("source", ""),
                "med": d.get("price_median"),
                "n": d.get("eligible_count"),
            }
    if fuel and fuel.get("items"):
        snap["fuel"] = {i["key"]: i["price"] for i in fuel["items"]}
        snap["fuel_date"] = fuel.get("date")
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


def _find_snap(snapshots, days_ago: int, slack: int = 3, before_today: bool = True):
    """Найсвіжіший знімок, якому days_ago…days_ago+slack днів (день 0 = сьогодні не береться)."""
    today = datetime.now(KYIV).date()
    cands = [s for s in snapshots if (d := _snap_date(s)) and days_ago <= (today - d).days <= days_ago + slack
             and (not before_today or d < today)]
    return max(cands, key=_snap_date) if cands else None


def compute_deltas(prices: dict, snapshots: list, today_str: str) -> dict:
    """
    {культура: {delta_1, delta_7, delta_30, med_delta_1, med_delta_7, med_delta_30, prev_date_1, …}}
    delta_* — зміна НАЙВИЩОЇ пропозиції (шумно: інший покупець); med_delta_* — зміна МЕДІАНИ порівнюваних
    пропозицій (стабільніше). delta_1 — до попереднього знімка 1–3 дні тому (вихідні/пропуски CI).
    None → немає знімка в потрібному вікні.
    """
    snaps = {1: _find_snap(snapshots, 1, 2), 7: _find_snap(snapshots, 7), 30: _find_snap(snapshots, 30)}
    deltas = {}
    for c, d in prices.items():
        row = {}
        cur = d["best_price"]["price_uah"] if d and d.get("best_price") else None
        med = d.get("price_median") if d else None
        for n, sn in snaps.items():
            prev = (sn or {}).get("prices", {}).get(c) if sn else None
            row[f"delta_{n}"] = round(cur - prev["uah"]) if cur is not None and prev else None
            row[f"med_delta_{n}"] = (round(med - prev["med"]) if med is not None and prev and prev.get("med") is not None
                                     else None)
            row[f"prev_date_{n}"] = sn["date"] if sn and prev else None
        deltas[c] = row
    return deltas


def fuel_deltas(fuel: dict, snapshots: list) -> list:
    """Пальне: ціна, зміна за день (з minfin), за тиждень/місяць (з історії)."""
    out = []
    for i in (fuel or {}).get("items", []):
        row = dict(i)
        for n in (7, 30):
            sn = _find_snap(snapshots, n)
            prev = (sn or {}).get("fuel", {}).get(i["key"]) if sn else None
            row[f"delta_{n}"] = round(i["price"] - prev, 2) if prev is not None else None
            row[f"prev_date_{n}"] = sn.get("fuel_date") or sn["date"] if prev is not None else None
        out.append(row)
    return out


# ── Барометр «на зараз» ──────────────────────────────────────────────────────
# 0–100: вище = вигідніше продавати зараз. Лише з даних дня та історії; без ручних оцінок,
# без прогнозів. Сигнал без даних не рахується; < NOW_MIN_SIGNALS сигналів → бала немає.
NOW_WEIGHTS = {"premium": 40, "move": 30, "range": 30}
NOW_MIN_SIGNALS = 1   # бал показується з 1 сигналу, але з позначкою надійності (1/2/3 з 3)


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def now_score(culture: str, d: dict | None, snapshots: list) -> dict:
    sig = {}
    if d and d.get("best_price"):
        best = d["best_price"]["price_uah"]
        refs = d.get("reference") or []
        if refs:
            ref = max(r["price_uah"] for r in refs)
            p = (best - ref) / ref * 100
            sig["premium"] = {"score": round(_clamp(50 + p * 10)), "value_pct": round(p, 1),
                              "best": round(best), "ref": round(ref), "ref_basis": refs[0].get("basis"),
                              "note": f"Найкраща пропозиція {round(best):,} ₴/т проти середньої по Україні {round(ref):,} ₴/т "
                                      f"({'+' if p >= 0 else ''}{p:.1f}%). Вище ринку → краще продавати зараз.".replace(",", " ")}
        med = d.get("price_median")
        prev_sn = _find_snap(snapshots, 1, 2)
        prev = (prev_sn or {}).get("prices", {}).get(culture) if prev_sn else None
        if med is not None and prev and prev.get("med"):
            p = (med - prev["med"]) / prev["med"] * 100
            sig["move"] = {"score": round(_clamp(50 - p * 10)), "value_pct": round(p, 1), "prev_date": prev_sn["date"],
                           "note": f"Медіана пропозицій {round(med):,} ₴/т, {'+' if p >= 0 else ''}{p:.1f}% до {prev_sn['date'][:5]}. "
                                   f"Падає → продавати раніше; росте → можна почекати.".replace(",", " ")}
        today = datetime.now(KYIV).date()
        hist = [s["prices"][culture].get("med") for s in snapshots
                if (dd := _snap_date(s)) and (today - dd).days <= 30 and culture in s.get("prices", {})
                and s["prices"][culture].get("med") is not None]
        if med is not None and len(hist) >= 5:
            lo, hi = min(hist + [med]), max(hist + [med])
            if hi - lo >= 1:
                pos = (med - lo) / (hi - lo) * 100
                sig["range"] = {"score": round(pos), "days": len(hist), "lo": round(lo), "hi": round(hi),
                                "note": f"Медіана {round(med):,} ₴/т у діапазоні {len(hist)} днів {round(lo):,}–{round(hi):,}: "
                                        f"{'біля максимуму' if pos >= 70 else 'біля мінімуму' if pos <= 30 else 'посередині'}.".replace(",", " ")}
    used = {k: v for k, v in sig.items()}
    if len(used) < NOW_MIN_SIGNALS:
        need = []
        if "premium" not in sig: need.append("середньої ціни ринку (GrainTrade)")
        if "move" not in sig: need.append("знімка за попередній день")
        if "range" not in sig: need.append("історії ≥5 днів")
        return {"score": None, "signals": used, "n_signals": len(used),
                "why_none": ("немає порівнюваних пропозицій покупців" if not (d and d.get("best_price"))
                             else "бракує: " + ", ".join(need))}
    w = sum(NOW_WEIGHTS[k] for k in used)
    score = round(sum(used[k]["score"] * NOW_WEIGHTS[k] for k in used) / w)
    rel = {1: "низька", 2: "середня"}.get(len(used), "повна")
    return {"score": score, "signals": used, "n_signals": len(used), "of": len(NOW_WEIGHTS), "reliability": rel}


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


MAX_OFFER_AGE_DAYS = 2   # власник: розбіжність не більше 1–2 днів (08.11.2026)


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


REF_MAX_AGE_DAYS = 3   # середні GrainTrade не виходять у вихідні: п'ятниця → понеділок


def reference_prices(recs):
    """Середні по Україні (GrainTrade) — окремо від оферт; лише продукт культури, не «вис.ол.» тощо."""
    now = datetime.now(KYIV)
    refs = [r for r in recs if r.get("ref_kind") == "national_avg"
            and (dt := parse_date(r.get("date"))) and (now - dt).days <= REF_MAX_AGE_DAYS
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
        sp = sorted(prices)
        median = sp[len(sp)//2] if len(sp) % 2 else (sp[len(sp)//2 - 1] + sp[len(sp)//2]) / 2
        result[c] = {
            "emoji": CULTURE_EMOJI[c],
            "best_price": _slim(by_price[0]),
            "best_net": best_net,
            "price_min": min(prices), "price_max": max(prices), "price_median": median,
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
        const why=d?(d.reference&&d.reference.length&&d.reference.length===d.records_count?'Є лише середні ціни по Україні, пропозицій конкретних покупців немає':`${d.records_count} знайдених записів, але жоден не пройшов перевірку порівнюваності`):'За 2 дні жодної закупівельної ціни не знайдено';
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
    const sub=document.querySelector('#tgSection .sec-sub');if(sub)sub.textContent='Живі пости каналів за 2 дні · зібрано '+D.generated_at_kyiv+' · сірим — не порівнюються (експорт, викид тощо)';
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

  // ── Барометр «на зараз» (0–100) — живий, з даних дня ──
  const NOWC=v=>v==null?{c:'baro-neutral',l:'—'}:v<=25?{c:'baro-wait',l:'🔴 Чекати'}:v<=45?{c:'baro-caution',l:'🟠 Обережно'}:v<=60?{c:'baro-neutral',l:'🟡 Нейтрально'}:v<=75?{c:'baro-sell',l:'🟢 Продавати'}:{c:'baro-sell-now',l:'⚡ Продавати зараз'};
  const SIGN={premium:'Ціна vs ринок',move:'Рух за день',range:'Діапазон 30 дн.'};
  const nowPill=c=>{const n=(D.now||{})[c];if(!n)return'';const i=NOWC(n.score);
    return `<span class="now-pill ${i.c}${n.n_signals===1?' now-low':''}" title="${esc(n.score==null?('Бал не розраховано: '+(n.why_none||'')):('Барометр «на зараз», надійність '+(n.reliability||'')+' ('+n.n_signals+' з '+n.of+' сигналів)'))}">⏱ ${n.score==null?'—':n.score}<small>/100</small></span>`;};
  if(!document.getElementById('nowCss')){const st=document.createElement('style');st.id='nowCss';st.textContent=`
    .now-pill{display:inline-flex;align-items:baseline;gap:1px;font-weight:800;font-size:13px;padding:2px 7px;border-radius:999px;border:1.5px solid currentColor;white-space:nowrap;font-family:'IBM Plex Mono',monospace}
    .now-pill small{font-size:9px;font-weight:600;opacity:.75}
    .now-pill.now-low{border-style:dashed;opacity:.85}
    .baro-sig{font-size:11px;color:var(--fg2);margin-top:6px;line-height:1.35}
    .baro-sig b{font-family:'IBM Plex Mono',monospace}
    .baro-none{font-size:11px;color:var(--fg3);margin-top:6px}`;document.head.appendChild(st);}
  window.__AGRO_LIVE_BARO__=function(){
    const box=document.getElementById('baroCards');if(!box||!D.now)return;
    box.innerHTML=D.cultures.map(c=>{const n=D.now[c]||{};const i=NOWC(n.score);const d=D.prices[c];const t=c.charAt(0).toUpperCase()+c.slice(1);
      const sig=Object.entries(n.signals||{}).map(([k,v])=>`<div class="baro-sig"><b>${v.score}</b> · ${esc(SIGN[k]||k)}: ${esc(v.note)}</div>`).join('');
      return `<div class="baro-card expanded${n.score!=null&&n.score>=76?' baro-signal-now':''}">
        <div class="baro-crop-label">${d?d.emoji:'🌾'} ${esc(t)}</div>
        <div class="baro-score-wrap"><span class="baro-score ${i.c}">${n.score==null?'—':n.score}</span><span class="baro-score-max">/100</span></div>
        <div class="baro-signal-label ${i.c}">${n.score==null?'Даних замало':i.l}</div>
        ${n.score==null?`<div class="baro-none">${esc(n.why_none||'')}</div>`:''}${sig}
        ${n.score!=null?`<div class="baro-none">надійність: <b>${esc(n.reliability||'')}</b> (${n.n_signals} з ${n.of} сигналів) · ${esc(D.generated_at_kyiv)}</div>`:''}</div>`;}).join('');
    const disc=document.querySelector('.baro-disclaimer');
    if(disc&&!disc.dataset.live){disc.dataset.live=1;disc.innerHTML='⚠️ Бал «на зараз» рахується щоранку тільки з даних: найкраща пропозиція покупця проти середньої по Україні (GrainTrade), рух медіани пропозицій за день, положення ціни в діапазоні за 30 днів. Без ручних оцінок і без прогнозів; ціни — опубліковані пропозиції (<strong>published_unconfirmed</strong>). Сигнал без даних не рахується; надійність: 1 сигнал — низька, 2 — середня, 3 — повна.';}
  };
  window.__AGRO_LIVE_BARO__();
  // бал біля кожної культури: картки цін і висновків
  document.querySelectorAll('#cropsGrid .crop-card').forEach((card,idx)=>{const c=D.cultures[idx];const h=card.querySelector('.crop-icon-name');if(h&&c&&!h.querySelector('.now-pill'))h.insertAdjacentHTML('beforeend',' '+nowPill(c));});
  const _crObs=document.getElementById('cropsGrid');
  if(_crObs)new MutationObserver(()=>{document.querySelectorAll('#cropsGrid .crop-card').forEach((card,idx)=>{const c=D.cultures[idx];const h=card.querySelector('.crop-icon-name');if(h&&c&&!h.querySelector('.now-pill'))h.insertAdjacentHTML('beforeend',' '+nowPill(c));});}).observe(_crObs,{childList:true});
  document.querySelectorAll('#summaryLive .sum-card').forEach((card,idx)=>{const c=D.cultures.filter(x=>D.summaries&&D.summaries[x])[idx];const h=card.querySelector('.sum-name');if(h&&c)h.insertAdjacentHTML('beforeend',' '+nowPill(c));});

  // ── Трекер дельти — живий ──
  const sgn=v=>v>0?'+':'';const dcls=v=>v==null?'dci-fl':v>0?'dci-up':v<0?'dci-dn':'dci-fl';const arr=v=>v==null?'':v>0?'↑':v<0?'↓':'→';
  const dl=(v,u,dec)=>v==null?'<span style="color:var(--fg3)">н/д</span>':`<span class="${dcls(v)}">${arr(v)} ${fmt(Math.abs(v),dec)} ${u}</span>`;
  window.__AGRO_LIVE_DELTA__=function(){
    const g=document.getElementById('deltaGridInner');if(!g)return;
    const sec=g.closest('.delta-section');
    if(sec){const t=sec.querySelector('.charts-title');if(t)t.textContent='📊 Трекер дельти — на '+D.generated_at_kyiv;
      const n=sec.querySelector('.charts-note');if(n)n.innerHTML=`Культури — <strong>медіана</strong> порівнюваних пропозицій дня (стабільніше за «найвищу»); пальне — середня по АЗС України (minfin). Історія знімків: ${D.history_days} дн.${D.history_from?' з '+esc(D.history_from):''} — тиждень і місяць з'являться, коли назбирається історія.`;
      [...sec.children].forEach(el=>{if(/архів|bestPrice 22/.test(el.textContent)&&el!==g&&!el.classList.contains('charts-title'))el.style.display='none';});}
    const crops=D.cultures.map(c=>{const d=D.prices[c];const x=(D.deltas||{})[c]||{};if(!d||!d.best_price)return `<div class="delta-card-inner"><div class="dc-name-i">${d?d.emoji:'🌾'} ${esc(c)}</div><div class="dc-prev-i">немає порівнюваних пропозицій</div></div>`;
      return `<div class="delta-card-inner"><div class="dc-name-i">${d.emoji} ${esc(c)}</div>
        <div class="dc-price-i">${fmt(d.price_median)} <span class="dc-unit-i">₴/т медіана</span></div>
        <div class="dc-delta-i">день: ${dl(x.med_delta_1,'₴/т',0)}</div>
        <div class="dc-prev-i">тиждень: ${dl(x.med_delta_7,'₴/т',0)} · місяць: ${dl(x.med_delta_30,'₴/т',0)}</div>
        <div class="dc-prev-i">найвища ${fmt(d.best_price.price_uah)} (день ${x.delta_1==null?'н/д':arr(x.delta_1)+' '+fmt(Math.abs(x.delta_1))})</div></div>`;}).join('');
    const fu=((D.fuel||{}).items||[]).map(i=>`<div class="delta-card-inner"><div class="dc-name-i">⛽ ${esc(i.name)}</div>
        <div class="dc-price-i">${fmt(i.price,2)} <span class="dc-unit-i">₴/л</span></div>
        <div class="dc-delta-i">день: ${dl(i.delta_day,'₴',2)}</div>
        <div class="dc-prev-i">тиждень: ${dl(i.delta_7,'₴',2)} · місяць: ${dl(i.delta_30,'₴',2)}</div>
        <div class="dc-prev-i">дані на ${esc(D.fuel.date||'?')}</div></div>`).join('');
    g.innerHTML=crops+fu;
  };
  window.__AGRO_LIVE_DELTA__();

  // ── Паливо — живе (minfin) ──
  (function(){const rows=document.getElementById('fuelRows'),tt=document.getElementById('fuelTitle');const F=D.fuel||{};
    if(!rows||!F.items||!F.items.length){if(tt)tt.insertAdjacentHTML('beforeend',' <span class="status-badge badge-unconfirmed">не оновлено</span>');return;}
    if(tt)tt.innerHTML=`<span class="panel-title-icon">⛽</span> Паливо (${esc(F.date||'?')}, сер. по Україні)`;
    rows.innerHTML=F.items.map(i=>{const u=safeUrl(i.url);const cl=i.delta_day>0?' fuel-up':'';
      return `<div class="fuel-row"><span class="fuel-name">${esc(i.name)}</span><div class="fuel-price-wrap">
        ${u?`<a class="fuel-price${cl}" href="${u}" target="_blank" rel="noopener">${fmt(i.price,2)} ₴/л ↗</a>`:`<span class="fuel-price">${fmt(i.price,2)} ₴/л</span>`}
        ${i.delta_day!=null&&i.delta_day!==0?`<span class="status-badge badge-unconfirmed">${i.delta_day>0?'↑':'↓'} ${fmt(Math.abs(i.delta_day),2)} за день</span>`:''}</div></div>`;}).join('');
  })();
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
    fuel = load_json("fuel_data.json", {"items": []})
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
    new_snap = _snapshot_from_prices(prices, today_str, fuel)
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

    now_scores = {c: now_score(c, prices.get(c), snapshots) for c in CULTURES}
    for c in CULTURES:
        ns = now_scores[c]
        print(f"   ⏱ {c}: барометр зараз {ns['score'] if ns['score'] is not None else '—'}"
              f" ({ns['n_signals']} сигн.{'' if ns['score'] is not None else ' · ' + ns.get('why_none', '')})")
    fuel_rows = fuel_deltas(fuel, snapshots)

    print("\n=== Висновки по культурах ===")
    summaries = crop_summaries.generate(CULTURES, prices, deltas, news_items, USD_UAH, today_str, now_scores)

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
        "history_from": snapshots[0]["date"] if snapshots else None,
        "now": now_scores,
        "fuel": {"date": fuel.get("date"), "items": fuel_rows},
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
