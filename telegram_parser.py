"""
AGRO BAROMETER — Telegram Parser v4
Канали:
  @navigate_agro  — щоденний прайс по культурах (основний!)
  @agrohub_od     — CPT термінали, USD Ф-2
  @AgroBrok       — EXW/DAP ціни
  @spike_brokers  — тижневий огляд (контекст)
  @ags_grain      — DAP Болгарія (експортний орієнтир)
"""

import re, json, asyncio, os
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

SESSION  = os.environ["TELEGRAM_SESSION"]
API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

USD_UAH = 45.47
EUR_UAH = 50.80

# ─── КОНФІГУРАЦІЯ КАНАЛІВ ─────────────────────────────────────────────────────
CHANNELS = {
    "navigate_agro": "prices",   # щоденний прайс — основний
    "agrohub_od":    "prices",   # CPT термінали
    "AgroBrok":      "prices",   # EXW/DAP
    "spike_brokers": "context",  # тижневий огляд
    "ags_grain":     "context",  # DAP Болгарія
    "apk_informUA":  "news",
    "UkrAgroConsult":"news",
    "latifundistmedia": "news",
}

# ─── МАПИ КУЛЬТУР ─────────────────────────────────────────────────────────────
CULTURE_HEADERS = {
    # navigate_agro використовує жирні заголовки
    "рапс":      "ріпак",
    "ріпак":     "ріпак",
    "соняшник":  "соняшник",
    "соя":       "соя",
    "пшениця":   "пшениця",
    "кукуруз":   "кукурудза",   # "кукуруза" або "кукурудза"
    "ячмінь":    "ячмінь",
}

CULTURE_KW = {
    "ріпак":     ["#ріпак", "#рапс", "ріпак", "рапс"],
    "соняшник":  ["#соняшник", "соняшник"],
    "соя":       ["#соя", "соя"],
    "пшениця":   ["#пшениця", "пшениця"],
    "кукурудза": ["#кукурудза", "кукурудза", "кукуруза"],
    "ячмінь":    ["#ячмінь", "ячмінь"],
}

# ─── ПАТЕРНИ ЦІН ──────────────────────────────────────────────────────────────
# "20000грн", "20 000грн", "20000 грн", "20'000грн"
UAH_RE = re.compile(r"(\d[\d\s']{2,6}\d)\s*грн", re.IGNORECASE)

# "445$", "445 $", "410$", "107$"
USD_RE = re.compile(r"(\d{2,4})\s*\$", re.IGNORECASE)

# "167 євро", "167eur"
EUR_RE = re.compile(r"(\d{2,4})\s*(?:євро|eur|€)", re.IGNORECASE)

# Заголовок культури у navigate_agro: "**РАПС ГМО/НЕ ГМО🌱:**"
HEADER_RE = re.compile(
    r"\*{1,2}([А-ЯІЇЄA-Z][А-ЯІЇЄа-яіїєA-Za-z\s/]+)"
    r"(?:\s*(?:ГМО|НЕ\s*ГМО|🌱|🌻|🫘|🌾|🌽|[А-ЯA-Z\s/]*))*"
    r"\*{0,2}\s*:",
    re.IGNORECASE
)


def to_uah(val, currency):
    if currency == "USD":
        return round(val * USD_UAH)
    if currency == "EUR":
        return round(val * EUR_UAH)
    return val


def parse_navigate_agro(text, msg_date):
    """
    Спеціальний парсер для @navigate_agro.
    Структура:
      **КУЛЬТУРА:**
      ПУНКТ - ціна
      ПУНКТ - ціна
      **НАСТУПНА КУЛЬТУРА:**
      ...
    """
    records = []
    date_str = msg_date.strftime("%d.%m.%Y %H:%M")

    current_culture = None
    lines = text.split("\n")

    for line in lines:
        clean = line.strip().strip("*").strip()

        # Перевіряємо чи це заголовок культури
        for kw, culture in CULTURE_HEADERS.items():
            if kw.upper() in clean.upper() and (":" in clean or "🌱" in clean or
               "🌻" in clean or "🫘" in clean or "🌾" in clean or "🌽" in clean):
                current_culture = culture
                break

        if not current_culture:
            continue

        # Пропускаємо заголовки і порожні рядки
        if not clean or clean.endswith(":") or len(clean) < 5:
            continue

        # Шукаємо пункт і ціну в рядку
        # Формат: "ПУНКТ - ціна" або "ПУНКТ.-ціна" або "-ПУНКТ - ціна"
        # Прибираємо ведучі тире
        clean_line = re.sub(r"^[-–—\s]+", "", clean)

        # Витягуємо пункт — все до першої цифри або "-"
        location_match = re.match(r"^([А-ЯІЇЄA-ZА-яіїєa-z\s/]+)", clean_line)
        location = location_match.group(1).strip().rstrip("-").strip() if location_match else "невідомо"

        # Пропускаємо рядки де пункт порожній або "-"
        if not location or location in ("-", "–", "—"):
            continue

        # ❌ ПРОПУСКАЄМО БН (без накладної = готівка без ПДВ)
        # Господарство працює з ПДВ — БН-ціни нерелевантні
        line_lower = clean_line.lower()
        is_bn = bool(re.search(r'\bбн\b', line_lower))
        if is_bn:
            continue

        # Знаходимо ціни — беремо найвищу грн, якщо немає грн — конвертуємо USD
        uah_prices = []
        usd_prices = []
        eur_prices = []

        for m in UAH_RE.finditer(clean_line):
            v = float(m.group(1).replace(" ", "").replace("'", ""))
            if 4000 <= v <= 60000:
                uah_prices.append(v)

        for m in USD_RE.finditer(clean_line):
            v = float(m.group(1))
            if 80 <= v <= 1200:
                usd_prices.append(v)

        for m in EUR_RE.finditer(clean_line):
            v = float(m.group(1))
            if 80 <= v <= 1200:
                eur_prices.append(v)

        # Збираємо всі ціни в UAH еквіваленті
        all_uah = [(v, "UAH") for v in uah_prices]
        all_uah += [(to_uah(v, "USD"), "USD") for v in usd_prices]
        all_uah += [(to_uah(v, "EUR"), "EUR") for v in eur_prices]

        if not all_uah:
            continue

        # Беремо найвищу ціну
        best_uah, best_curr = max(all_uah, key=lambda x: x[0])
        raw_val = uah_prices[0] if best_curr == "UAH" else (
            usd_prices[0] if best_curr == "USD" else eur_prices[0]
        )

        # Визначаємо базис (БН вже відфільтровано вище)
        basis = "CPT"
        line_lower = clean_line.lower()
        if "ндс" in line_lower or "з пдв" in line_lower or "нДС" in clean_line:
            basis = "з ПДВ"
        elif "exw" in line_lower:
            basis = "EXW"
        elif "dap" in line_lower:
            basis = "DAP"

        records.append({
            "source":    "@navigate_agro",
            "culture":   current_culture,
            "price_raw": raw_val,
            "price_uah": best_uah,
            "currency":  best_curr,
            "basis":     basis,
            "location":  location[:30],
            "region":    _guess_region(location),
            "date":      date_str,
            "text":      clean_line[:150],
        })

    return records


def parse_generic(text, channel, msg_date):
    """Загальний парсер для інших каналів."""
    records = []
    if not text or len(text) < 15:
        return records

    culture = _find_culture(text)
    if not culture:
        return records

    date_str = msg_date.strftime("%d.%m.%Y %H:%M")

    # Шукаємо ціни в тексті
    for m in USD_RE.finditer(text):
        v = float(m.group(1))
        if 80 <= v <= 1200:
            uah = to_uah(v, "USD")
            location = _nearest_location(text, m.start())
            records.append({
                "source": f"@{channel}", "culture": culture,
                "price_raw": v, "price_uah": uah, "currency": "USD",
                "basis": _find_basis(text), "location": location,
                "region": _guess_region(location), "date": date_str,
                "text": text[max(0, m.start()-50):m.start()+50].replace("\n", " "),
            })

    for m in UAH_RE.finditer(text):
        raw = m.group(1).replace(" ", "").replace("'", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        if 4000 <= v <= 60000:
            location = _nearest_location(text, m.start())
            records.append({
                "source": f"@{channel}", "culture": culture,
                "price_raw": v, "price_uah": v, "currency": "UAH",
                "basis": _find_basis(text), "location": location,
                "region": _guess_region(location), "date": date_str,
                "text": text[max(0, m.start()-50):m.start()+50].replace("\n", " "),
            })

    return records


def _find_culture(text):
    t = text.lower()
    for culture, kws in CULTURE_KW.items():
        if any(kw.lower() in t for kw in kws):
            return culture
    return None


def _find_basis(text):
    t = text.lower()
    if "бн" in t:         return "БН"
    if "ндс" in t or "з пдв" in t: return "з ПДВ"
    if "exw" in t:        return "EXW"
    if "dap" in t:        return "DAP"
    if "cpt" in t:        return "CPT"
    if "fca" in t:        return "FCA"
    return "невідомо"


def _nearest_location(text, pos):
    segment = text[max(0, pos-100):pos]
    lines = segment.split("\n")
    for line in reversed(lines):
        line = line.strip().strip("*-– ").strip()
        if line and len(line) > 2 and not re.match(r"^\d", line):
            return line[:30]
    return "невідомо"


# Маппінг пунктів до регіонів
LOCATION_REGION = {
    "НОВОТЕХ": "Одеська", "ІЗМАЇЛ": "Одеська", "РЕНІ": "Одеська",
    "ОДЕСА": "Одеська", "ПІВДЕННИЙ": "Одеська", "ЧОРНОМОРСЬК": "Одеська",
    "ЕРКИ": "Черкаська", "ВЛАСІВКА": "Черкаська", "ЧОРНОБАЙ": "Черкаська",
    "КРОПІВНИЦЬКИЙ": "Кіровоградська", "КРОПИВНИЦЬКИЙ": "Кіровоградська",
    "БАНДУРКА": "Миколаївська",
    "СТАРКОН": "Хмельницька", "СТАРОКОСТЯНТИНІВ": "Хмельницька",
    "ЛАДИЖИН": "Вінницька", "ВІННИЦЯ": "Вінницька",
    "МИКОЛАЇВ": "Миколаївська",
}


def _guess_region(location):
    loc_upper = location.upper()
    for key, region in LOCATION_REGION.items():
        if key in loc_upper:
            return region
    return "невідомо"


# ─── ГОЛОВНА ФУНКЦІЯ ──────────────────────────────────────────────────────────

async def main():
    print(f"=== AGRO BAROMETER Telegram Parser v4 ===")
    print(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"USD/UAH: {USD_UAH} | EUR/UAH: {EUR_UAH}")
    print()

    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    all_records = []

    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        for ch, role in CHANNELS.items():
            try:
                msg_count = 0
                price_count = 0

                async for msg in client.iter_messages(ch, limit=50):
                    if msg.date < cutoff:
                        break
                    if not msg.text:
                        continue
                    msg_count += 1

                    if role == "prices":
                        if ch == "navigate_agro":
                            records = parse_navigate_agro(msg.text, msg.date)
                        else:
                            records = parse_generic(msg.text, ch, msg.date)
                        all_records.extend(records)
                        price_count += len(records)

                icon = "💰" if role == "prices" else ("📰" if role == "news" else "📊")
                print(f"  {icon} @{ch}: {msg_count} повід., {price_count} записів")

            except Exception as e:
                print(f"  ❌ @{ch}: {e}")

    print(f"\n{'='*55}")
    print(f"Всього цінових записів: {len(all_records)}")
    print()

    # ─── ПІДСУМОК ПО КУЛЬТУРАХ ────────────────────────────────────────────────
    CULTURE_ORDER = ["ріпак", "соняшник", "соя", "кукурудза", "ячмінь", "пшениця"]
    NET_FREIGHT = {
        # Долинське → пункт (₴/т)
        "Долинське": {
            "Одеська": 1500, "Черкаська": 525, "Миколаївська": 1050,
            "Кіровоградська": 275, "Вінницька": 700, "Хмельницька": 900,
            "Полтавська": 600, "невідомо": 800,
        },
        # Копані → пункт (₴/т)
        "Копані": {
            "Одеська": 1400, "Черкаська": 375, "Миколаївська": 975,
            "Кіровоградська": 105, "Вінницька": 600, "Хмельницька": 750,
            "Полтавська": 450, "невідомо": 700,
        },
    }

    summary = {}
    for culture in CULTURE_ORDER:
        recs = [r for r in all_records if r["culture"] == culture]
        if not recs:
            continue

        # Рахуємо net для кожного запису
        for r in recs:
            region = r.get("region", "невідомо")
            r["net_dolynske"] = r["price_uah"] - NET_FREIGHT["Долинське"].get(region, 800)
            r["net_kopani"]   = r["price_uah"] - NET_FREIGHT["Копані"].get(region, 700)

        best_net = max(recs, key=lambda x: x["net_kopani"])
        best_price = max(recs, key=lambda x: x["price_uah"])

        summary[culture] = {
            "records": len(recs),
            "sources": list(set(r["source"] for r in recs)),
            "best_price_uah": best_price["price_uah"],
            "best_price_location": best_price["location"],
            "best_net_kopani": best_net["net_kopani"],
            "best_net_dolynske": best_net["net_dolynske"],
            "best_net_location": best_net["location"],
            "best_net_region": best_net["region"],
            "best_net_source": best_net["source"],
            "best_net_date": best_net["date"],
        }

        print(f"🌾 {culture.upper()}")
        print(f"   Найвища ціна:  {best_price['price_uah']:>8,.0f} грн | {best_price['location']} ({best_price.get('region','?')}) | {best_price['source']}")
        print(f"   Найкращий net: {best_net['net_kopani']:>8,.0f} грн від Копані | {best_net['net_dolynske']:>8,.0f} грн від Долинського")
        print(f"   Пункт:         {best_net['location']} ({best_net.get('region','?')}) | {best_net['basis']} | {best_net['source']} | {best_net['date']}")
        print(f"   Записів: {len(recs)} з {len(set(r['source'] for r in recs))} джерел")
        print()

    # ─── ЗБЕРЕЖЕННЯ ───────────────────────────────────────────────────────────
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usd_uah": USD_UAH,
        "eur_uah": EUR_UAH,
        "records_total": len(all_records),
        "summary": summary,
        "records": all_records,
    }

    out_path = "telegram_prices.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Збережено: {out_path}")


asyncio.run(main())
