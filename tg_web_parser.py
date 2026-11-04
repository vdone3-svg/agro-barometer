"""
AGRO BAROMETER — Telegram Web Parser
Читає публічні канали через t.me/s/ (без авторизації, без Telethon)
Зберігає: telegram_prices.json
"""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

USD_UAH = 45.47
EUR_UAH = 50.80

# ─── КАНАЛИ ───────────────────────────────────────────────────────────────────
CHANNELS = [
    ("navigate_agro", "prices"),   # щоденний прайс — основний
    ("agrohub_od",    "prices"),   # CPT термінали, Ф-2
    ("AgroBrok",      "prices"),   # EXW/DAP
    ("rawagro",       "prices"),   # РО АГРО ТРЕЙД — прайс 6 культур
    ("Agroprosperis_price", "prices"),  # Агропросперіс
    ("spike_brokers", "context"),  # тижневий огляд
    ("latifundistmedia", "news"),
]

# ─── МАПИ ─────────────────────────────────────────────────────────────────────
CULTURE_HEADERS = {
    "рапс": "ріпак", "ріпак": "ріпак", "соняшник": "соняшник",
    "соя": "соя", "пшениця": "пшениця", "кукуруз": "кукурудза",
    "ячмінь": "ячмінь",
}
CULTURE_KW = {
    "ріпак":     ["#ріпак", "#рапс", "ріпак", "рапс"],
    "соняшник":  ["#соняшник", "соняшник"],
    "соя":       ["#соя", "соя"],
    "пшениця":   ["#пшениця", "пшениця"],
    "кукурудза": ["#кукурудза", "кукурудза", "кукуруза"],
    "ячмінь":    ["#ячмінь", "ячмінь"],
}
LOCATION_REGION = {
    "НОВОТЕХ": "Одеська", "ІЗМАЇЛ": "Одеська", "РЕНІ": "Одеська",
    "ОДЕСА": "Одеська", "ПІВДЕННИЙ": "Одеська", "ЧОРНОМОРСЬК": "Одеська",
    "ЕРКИ": "Черкаська", "ВЛАСІВКА": "Черкаська", "ЧОРНОБАЙ": "Черкаська",
    "КРОПІВНИЦЬКИЙ": "Кіровоградська", "КРОПИВНИЦЬКИЙ": "Кіровоградська",
    "БАНДУРКА": "Миколаївська", "МИКОЛАЇВ": "Миколаївська",
    "СТАРКОН": "Хмельницька", "СТАРОКОСТЯНТИНІВ": "Хмельницька",
    "ЛАДИЖИН": "Вінницька", "ВІННИЦЯ": "Вінницька",
    "ГЛОБИНЕ": "Полтавська", "ПОЛТАВА": "Полтавська",
    "ЧЕРКАСИ": "Черкаська",
}

UAH_RE = re.compile(r"(\d[\d\s']{2,6}\d)\s*грн", re.IGNORECASE)
USD_RE = re.compile(r"(\d{2,4})\s*\$", re.IGNORECASE)
EUR_RE = re.compile(r"(\d{2,4})\s*(?:євро|eur|€)", re.IGNORECASE)


# ─── ХЕЛПЕРИ ──────────────────────────────────────────────────────────────────

def to_uah(val, currency):
    if currency == "USD": return round(val * USD_UAH)
    if currency == "EUR": return round(val * EUR_UAH)
    return val


def _guess_region(location):
    loc_upper = location.upper()
    for key, region in LOCATION_REGION.items():
        if key in loc_upper:
            return region
    return "невідомо"


def _find_basis(text):
    t = text.lower()
    if "бн" in t: return "БН"
    if "ндс" in t or "з пдв" in t: return "з ПДВ"
    if "exw" in t: return "EXW"
    if "dap" in t: return "DAP"
    if "cpt" in t: return "CPT"
    if "fca" in t: return "FCA"
    return "невідомо"


def _find_culture(text):
    t = text.lower()
    for culture, kws in CULTURE_KW.items():
        if any(kw.lower() in t for kw in kws):
            return culture
    return None


# ─── ПАРСЕРИ ПОВІДОМЛЕНЬ ──────────────────────────────────────────────────────

def parse_navigate_agro(text, date_str):
    """Спеціальний парсер для @navigate_agro — структуровані прайси."""
    records = []
    current_culture = None

    for line in text.split("\n"):
        clean = line.strip().strip("*").strip()
        clean_lower = clean.lower()

        # Заголовок культури
        for kw, culture in CULTURE_HEADERS.items():
            if kw in clean_lower and (":" in clean or any(
                e in clean for e in ["🌱","🌻","🫘","🌾","🌽"]
            )):
                current_culture = culture
                break

        if not current_culture or not clean or len(clean) < 5:
            continue
        if clean.endswith(":"):
            continue
        # Пропускаємо БН (без ПДВ)
        if re.search(r'\bбн\b', clean_lower):
            continue

        clean_line = re.sub(r"^[-–—\s]+", "", clean)

        # Ціни
        uah_prices, usd_prices, eur_prices = [], [], []
        for m in UAH_RE.finditer(clean_line):
            v = float(m.group(1).replace(" ", "").replace("'", ""))
            if 4000 <= v <= 60000: uah_prices.append(v)
        for m in USD_RE.finditer(clean_line):
            v = float(m.group(1))
            if 80 <= v <= 1200: usd_prices.append(v)
        for m in EUR_RE.finditer(clean_line):
            v = float(m.group(1))
            if 80 <= v <= 1200: eur_prices.append(v)

        all_uah = ([(v, "UAH") for v in uah_prices]
                   + [(to_uah(v, "USD"), "USD") for v in usd_prices]
                   + [(to_uah(v, "EUR"), "EUR") for v in eur_prices])
        if not all_uah:
            continue

        best_uah, best_curr = max(all_uah, key=lambda x: x[0])
        raw_val = (uah_prices[0] if best_curr == "UAH"
                   else usd_prices[0] if best_curr == "USD" else eur_prices[0])

        loc_match = re.match(r"^([А-ЯІЇЄа-яіїєA-Za-z\s/]+)", clean_line)
        location = loc_match.group(1).strip().rstrip("-").strip() if loc_match else "невідомо"
        if not location or location in ("-", "–", "—"):
            continue

        records.append({
            "source":    "@navigate_agro",
            "culture":   current_culture,
            "quality":   None,
            "price_raw": raw_val,
            "price_uah": float(best_uah),
            "currency":  best_curr,
            "basis":     _find_basis(clean_line),
            "location":  location[:40],
            "region":    _guess_region(location),
            "date":      date_str,
            "net_kopani":   None,
            "net_dolynske": None,
        })
    return records


def parse_generic_msg(text, channel, date_str):
    """Загальний парсер для решти цінових каналів."""
    records = []
    if not text or len(text) < 10:
        return records

    culture = _find_culture(text)
    if not culture:
        return records

    for m in UAH_RE.finditer(text):
        raw = m.group(1).replace(" ", "").replace("'", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        if 4000 <= v <= 60000:
            ctx = text[max(0, m.start()-80):m.start()+30]
            if re.search(r'\bбн\b', ctx.lower()):
                continue
            records.append({
                "source":    f"@{channel}",
                "culture":   culture,
                "quality":   None,
                "price_raw": v, "price_uah": v, "currency": "UAH",
                "basis":     _find_basis(text),
                "location":  "невідомо",
                "region":    "невідомо",
                "date":      date_str,
                "net_kopani":   None,
                "net_dolynske": None,
            })

    for m in USD_RE.finditer(text):
        v = float(m.group(1))
        if 80 <= v <= 1200:
            ctx = text[max(0, m.start()-80):m.start()+30]
            if re.search(r'\bбн\b', ctx.lower()):
                continue
            uah = to_uah(v, "USD")
            records.append({
                "source":    f"@{channel}",
                "culture":   culture,
                "quality":   None,
                "price_raw": v, "price_uah": float(uah), "currency": "USD",
                "basis":     _find_basis(text),
                "location":  "невідомо",
                "region":    "невідомо",
                "date":      date_str,
                "net_kopani":   None,
                "net_dolynske": None,
            })

    return records


# ─── PLAYWRIGHT SCRAPER ───────────────────────────────────────────────────────

async def _scrape_channel(pw, channel: str, role: str, cutoff: datetime) -> list:
    """Відкриває t.me/s/<channel>, витягує повідомлення за останні 3 дні."""
    url = f"https://t.me/s/{channel}"
    records = []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  [tg] playwright не встановлено")
        return []

    browser = await pw.chromium.launch(headless=True)
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="uk-UA",
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        except Exception:
            pass  # partial load — беремо що є

        await page.wait_for_timeout(2000)

        # Витягуємо повідомлення через JS
        messages = await page.evaluate("""
            () => {
                const result = [];
                const wraps = document.querySelectorAll('.tgme_widget_message_wrap');
                wraps.forEach(wrap => {
                    const textEl = wrap.querySelector('.tgme_widget_message_text');
                    const timeEl = wrap.querySelector('time');
                    if (!textEl) return;
                    result.push({
                        text:     textEl.innerText || textEl.textContent || '',
                        datetime: timeEl ? timeEl.getAttribute('datetime') : null,
                    });
                });
                return result;
            }
        """)

        print(f"  [tg] @{channel}: знайдено {len(messages)} повідомлень")

        if not messages:
            # Дебаг: показуємо що взагалі є на сторінці
            title = await page.title()
            print(f"  [tg] @{channel}: title='{title}', url={page.url}")

        msg_count = 0
        price_count = 0

        for msg in messages:
            text = msg.get('text', '').strip()
            dt_str = msg.get('datetime')

            # Парсимо дату
            if dt_str:
                try:
                    msg_date = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except Exception:
                    msg_date = datetime.now(timezone.utc)
            else:
                msg_date = datetime.now(timezone.utc)

            # Пропускаємо старі
            if msg_date < cutoff:
                continue

            if not text or role not in ("prices",):
                continue

            msg_count += 1
            date_str = msg_date.strftime("%d.%m.%Y %H:%M")

            if channel == "navigate_agro":
                recs = parse_navigate_agro(text, date_str)
            else:
                recs = parse_generic_msg(text, channel, date_str)

            records.extend(recs)
            price_count += len(recs)

        print(f"  [tg] @{channel}: {msg_count} свіжих повід., {price_count} цінових записів")

    except Exception as e:
        print(f"  [tg] @{channel}: помилка ({e})")
    finally:
        await browser.close()

    return records


# ─── ФРАХТ ────────────────────────────────────────────────────────────────────

FREIGHT = {
    "Копані": {
        "Одеська": 1400, "Черкаська": 375, "Миколаївська": 975,
        "Кіровоградська": 105, "Вінницька": 600, "Хмельницька": 750,
        "Полтавська": 450, "невідомо": 700,
    },
    "Долинське": {
        "Одеська": 1500, "Черкаська": 525, "Миколаївська": 1050,
        "Кіровоградська": 275, "Вінницька": 700, "Хмельницька": 900,
        "Полтавська": 600, "невідомо": 800,
    },
}


def _add_net(records):
    for r in records:
        region = r.get("region", "невідомо")
        r["net_kopani"]   = r["price_uah"] - FREIGHT["Копані"].get(region, 700)
        r["net_dolynske"] = r["price_uah"] - FREIGHT["Долинське"].get(region, 800)
    return records


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def _run_all():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ПОМИЛКА: pip3 install playwright && python3 -m playwright install chromium")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    all_records = []

    async with async_playwright() as pw:
        for channel, role in CHANNELS:
            recs = await _scrape_channel(pw, channel, role, cutoff)
            all_records.extend(recs)

    return _add_net(all_records)


def main():
    print(f"=== Telegram Web Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")
    print(f"Джерело: t.me/s/ (без авторизації)\n")

    all_records = asyncio.run(_run_all())

    # ─── Підсумок по культурах ────────────────────────────────────────────────
    CULTURE_ORDER = ["ріпак", "соняшник", "соя", "кукурудза", "ячмінь", "пшениця"]
    summary = {}
    print("\n── Підсумок по культурах ──")

    for culture in CULTURE_ORDER:
        recs = [r for r in all_records if r["culture"] == culture]
        if not recs:
            continue
        best_net  = max(recs, key=lambda x: x["net_kopani"])
        best_price = max(recs, key=lambda x: x["price_uah"])
        summary[culture] = {
            "records": len(recs),
            "best_price_uah":      best_price["price_uah"],
            "best_price_location": best_price["location"],
            "best_net_kopani":     best_net["net_kopani"],
            "best_net_dolynske":   best_net["net_dolynske"],
            "best_net_location":   best_net["location"],
            "best_net_region":     best_net["region"],
            "best_net_source":     best_net["source"],
            "best_net_date":       best_net["date"],
        }
        print(f"  {culture.upper()}: найвища {best_price['price_uah']:,.0f} ₴ | "
              f"net Копані {best_net['net_kopani']:,.0f} ₴ | "
              f"{best_net['location']} | {best_net['source']}")

    if not all_records:
        print("  ⚠️  0 записів — канали або приватні, або змінили структуру")
        print("  Перевір у браузері: https://t.me/s/navigate_agro")

    # ─── Збереження ───────────────────────────────────────────────────────────
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usd_uah": USD_UAH,
        "eur_uah": EUR_UAH,
        "records_total": len(all_records),
        "summary": summary,
        "records": all_records,
    }
    with open("telegram_prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nЗбережено: telegram_prices.json ({len(all_records)} записів)")


if __name__ == "__main__":
    main()
