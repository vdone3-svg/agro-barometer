"""
AGRO BAROMETER — Парсер веб-джерел
Читає: nibulon.com (Playwright), tripoli.land (Playwright), e-zerno.com (Playwright)
Зберігає: web_prices.json
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.request import urlopen, Request

USD_UAH = float(os.environ.get('NBU_USD_UAH') or os.environ.get('USD_UAH_RATE') or os.environ.get('USD_UAH') or '45.47')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'uk-UA,uk;q=0.9',
}

# Маппінг: назва елеватора Nibulon → регіон
ELEVATOR_REGION = {
    "Бессарабська": "Одеська", "м.Ізмаїл": "Одеська",
    "АК Врадіївський": "Миколаївська", "Вознесенська": "Миколаївська",
    "Колосівський ел-р": "Миколаївська", "Новоодеська": "Миколаївська",
    "Термінал": "Миколаївська", "Зеленодольська": "Дніпропетровська",
    "Тернівська": "Запорізька", "Хортиця": "Запорізька",
    "Глобинська": "Полтавська", "Градизьк": "Полтавська",
    "Кременчуцька": "Полтавська", "Мар'янівська": "Полтавська",
    "Решетилівська": "Полтавська", "Ромодан": "Полтавська",
    "Скороходівська": "Полтавська", "Вітове": "Черкаська",
    "Золотоніська": "Черкаська", "Денихівська": "Київська",
    "Переяславська": "Київська", "Смотрич": "Хмельницька",
    "Тетерів": "Житомирська", "ЕК Хмільник": "Вінницька",
}

FREIGHT_KOPANI = {
    "Одеська": 1400, "Миколаївська": 975, "Черкаська": 375,
    "Кіровоградська": 105, "Полтавська": 450, "Дніпропетровська": 600,
    "Запорізька": 700, "Вінницька": 600, "Хмельницька": 750,
    "Київська": 600, "Житомирська": 800, "Харківська": 700,
}
FREIGHT_DOLYNSKE = {
    "Одеська": 1500, "Миколаївська": 1050, "Черкаська": 525,
    "Кіровоградська": 275, "Полтавська": 600, "Дніпропетровська": 700,
    "Запорізька": 800, "Вінницька": 700, "Хмельницька": 900,
    "Київська": 700, "Житомирська": 900, "Харківська": 800,
}

NIBULON_URL = "https://www.nibulon.com/zakupivelni-tsiny-na-zernovi-kultury/"
NIBULON_CULTURE_COLS = [
    ("пшениця", "2 кл"), ("пшениця", "3 кл"),
    ("пшениця", "4 кл"), ("кукурудза", None),
]

# e-zerno: відомі публічні профілі покупців олійних
# Формат: (назва, url, регіон)
EZERNO_PROFILES = [
    ("КОРОЛІВСТВО СМАК", "https://e-zerno.com/profile/korolivstvo-smak",   "Кіровоградська"),
    ("РО АГРО ТРЕЙД",    "https://e-zerno.com/profile/ro-agro-trade",       "Черкаська"),
    ("ASTARTA",          "https://e-zerno.com/profile/astarta",             "Полтавська"),
    ("МХП",              "https://e-zerno.com/profile/mkhp",                "Черкаська"),
    ("RISOIL",           "https://e-zerno.com/profile/risoil",              "Одеська"),
    ("ГЛЕНПОРТ",         "https://e-zerno.com/profile/glenport",            "Одеська"),
    ("В АГРО",           "https://e-zerno.com/profile/v-agro",              "Одеська"),
]

EZERNO_CULTURE_MAP = {
    'соняшник': 'соняшник', 'соя': 'соя', 'ріпак': 'ріпак',
    'пшениця': 'пшениця', 'кукурудза': 'кукурудза', 'ячмінь': 'ячмінь',
}
EZERNO_REGION_MAP = {
    'одеська': 'Одеська', 'миколаївська': 'Миколаївська',
    'черкаська': 'Черкаська', 'кіровоградська': 'Кіровоградська',
    'полтавська': 'Полтавська', 'дніпропетровська': 'Дніпропетровська',
    'запорізька': 'Запорізька', 'вінницька': 'Вінницька',
    'хмельницька': 'Хмельницька', 'київська': 'Київська',
    'житомирська': 'Житомирська', 'харківська': 'Харківська',
}


# ─────────────────────────────────────────────────────────────────────────────
# Спільні хелпери
# ─────────────────────────────────────────────────────────────────────────────

def _make_record(source, culture, quality, price, region, location, date_str, basis="з ПДВ", url=""):
    fk = FREIGHT_KOPANI.get(region)      # невідомий регіон → net не рахуємо
    fd = FREIGHT_DOLYNSKE.get(region)
    return {
        "source":       source,
        "culture":      culture,
        "quality":      quality,
        "price_raw":    float(price),
        "price_uah":    float(price),
        "currency":     "UAH",
        "basis":        basis,
        "location":     (location or source)[:60],
        "region":       region,
        "date":         date_str,
        "url":          url,
        "net_kopani":   float(price) - fk if fk is not None else None,
        "net_dolynske": float(price) - fd if fd is not None else None,
    }


def _detect_quality(text: str):
    if re.search(r'1\s*кл', text, re.I):  return '1 кл'
    if re.search(r'2\s*кл', text, re.I):  return '2 кл'
    if re.search(r'3\s*кл', text, re.I):  return '3 кл'
    if re.search(r'4\s*кл', text, re.I):  return '4 кл'
    if re.search(r'вис.*ол|high.?oil', text, re.I): return 'вис.ол.'
    if re.search(r'без\s*гмо|non.?gmo',  text, re.I): return 'не-ГМО'
    return None


def _detect_region(text: str):
    t = text.lower()
    for key, val in EZERNO_REGION_MAP.items():
        if key in t:
            return val
    return "невідомо"


async def _new_playwright_context(pw):
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="uk-UA",
    )
    return browser, context


async def _dismiss_banners(page):
    for txt in ["Прийняти", "Accept", "Accept All", "Прийняти всі", "OK", "Погодитися", "Зрозуміло"]:
        try:
            await page.click(f"text={txt}", timeout=1200)
            await page.wait_for_timeout(200)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# NIBULON
# ─────────────────────────────────────────────────────────────────────────────

async def _parse_nibulon(pw) -> list:
    records = []
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    browser, context = await _new_playwright_context(pw)
    try:
        page = await context.new_page()
        await page.goto(NIBULON_URL, timeout=45_000, wait_until="networkidle")
        await _dismiss_banners(page)
        await page.wait_for_timeout(1500)

        data = await page.evaluate("""
            () => {
                const links  = [...document.querySelectorAll('a[href*="/wp_mapit_pin/"]')];
                const names  = links.map(l => l.textContent.replace(/\\s+/g,' ').trim());
                const bodyText = document.body.innerText || '';
                const kukIdx   = bodyText.lastIndexOf('КУКУРУДЗА');
                const section  = kukIdx >= 0 ? bodyText.slice(kukIdx + 'КУКУРУДЗА'.length) : bodyText;
                const stopIdx  = section.search(/НОВИНИ|АКТУАЛЬНЕ/);
                const part     = stopIdx > 0 ? section.slice(0, stopIdx) : section;
                const tokens = [];
                const re = /(\\d{4,5}|-)/g;
                let m;
                while ((m = re.exec(part)) !== null) {
                    const t = m[1];
                    if (t === '-') { tokens.push(null); }
                    else { const n = parseInt(t); if (n >= 2000 && n <= 20000) tokens.push(n); }
                }
                return { names, tokens };
            }
        """)

        names  = data.get('names', [])
        tokens = data.get('tokens', [])
        needed = len(names) * 4
        if len(tokens) < needed:
            tokens += [None] * (needed - len(tokens))

        print(f"  [nibulon] Елеваторів: {len(names)}, токенів: {len(tokens)}")

        for i, elev in enumerate(names):
            base = i * 4
            if base + 3 >= len(tokens):
                break
            group = tokens[base:base+4]
            for j, (culture, quality) in enumerate(NIBULON_CULTURE_COLS):
                price = group[j] if j < len(group) else None
                if price is None:
                    continue
                region = ELEVATOR_REGION.get(elev, "невідомо")
                if region == "невідомо":
                    for k, v in ELEVATOR_REGION.items():
                        if k in elev or elev in k:
                            region = v; break
                records.append(_make_record("nibulon.com", culture, quality, price, region, elev, now_str,
                                            url=NIBULON_URL))

        print(f"  [nibulon] Записів: {len(records)}")
    except Exception as e:
        print(f"  [nibulon] Помилка: {e}")
        import traceback; traceback.print_exc()
    finally:
        await browser.close()
    return records


# ─────────────────────────────────────────────────────────────────────────────
# TRIPOLI.LAND — Playwright (urllib давав 403)
# ─────────────────────────────────────────────────────────────────────────────

async def _parse_tripoli(pw) -> list:
    records = []
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    browser, context = await _new_playwright_context(pw)
    try:
        page = await context.new_page()
        # networkidle ніколи не настає (ads/analytics) — ловимо timeout і читаємо що є
        try:
            await page.goto("https://tripoli.land/ua/traders", timeout=60_000, wait_until="networkidle")
        except Exception:
            pass  # сторінка могла завантажитись, просто фонові запити тривають
        await _dismiss_banners(page)
        await page.wait_for_timeout(1000)

        body = await page.evaluate("() => document.body.innerText || ''")

        culture_map = {
            'kukuruza': 'кукурудза', 'pshenitsa-2': 'пшениця',
            'pshenitsa-3': 'пшениця', 'yachmen': 'ячмінь',
            'raps': 'ріпак', 'podsolnechnik': 'соняшник', 'soya': 'соя',
        }

        # Спроба 1: із bodyText — шукаємо рядки виду "Соняшник\n18 700 грн"
        culture_patterns = {
            'соняшник': 'соняшник', 'соя': 'соя', 'ріпак': 'ріпак',
            'пшениця': 'пшениця', 'кукурудза': 'кукурудза', 'ячмінь': 'ячмінь',
        }
        seen = set()
        lines = body.split('\n')
        for idx, line in enumerate(lines):
            line_l = line.strip().lower()
            for key, culture in culture_patterns.items():
                if key in line_l and culture not in seen:
                    # Шукаємо ціну в наступних 5 рядках
                    ctx = '\n'.join(lines[idx:idx+5])
                    pm = re.search(r'(\d[\d\s\u00a0]{3,5}\d)\s*грн', ctx)
                    if not pm:
                        pm = re.search(r'\b(\d{4,6})\b', ctx)
                    if pm:
                        try:
                            price = float(re.sub(r'[\s\u00a0]', '', pm.group(1)))
                            if 3000 <= price <= 60000:
                                quality = None
                                if 'пшениця' in culture:
                                    if '2' in line_l: quality = '2 кл'
                                    elif '3' in line_l: quality = '3 кл'
                                records.append(_make_record(
                                    "tripoli.land", culture, quality, price,
                                    "невідомо", "Україна (трейдери)", now_str, "трейдери"
                                ))
                                records[-1]["net_kopani"]   = None
                                records[-1]["net_dolynske"] = None
                                seen.add(culture)
                        except ValueError:
                            pass
            if len(seen) == len(culture_patterns):
                break

        # Спроба 2: якщо bodyText не дав — парсимо HTML через innerHTML
        if len(records) < 3:
            html = await page.evaluate("() => document.body.innerHTML || ''")
            price_re = re.compile(
                r'href="/ua/(kukuruza|pshenitsa-2|pshenitsa-3|yachmen|raps|podsolnechnik|soya)[^"]*"'
                r'[^>]*>(\d[\d\s ]+\d)\s*грн',
                re.IGNORECASE,
            )
            seen2 = set()
            for m in price_re.finditer(html):
                slug = m.group(1).lower()
                culture = culture_map.get(slug)
                if not culture or slug in seen2:
                    continue
                try:
                    price = float(re.sub(r'\s| ', '', m.group(2)))
                    if 3000 <= price <= 60000:
                        quality = "2 кл" if slug == "pshenitsa-2" else ("3 кл" if slug == "pshenitsa-3" else None)
                        rec = _make_record("tripoli.land", culture, quality, price,
                                           "невідомо", "Україна (трейдери)", now_str, "трейдери")
                        rec["net_kopani"] = None
                        rec["net_dolynske"] = None
                        records.append(rec)
                        seen2.add(slug)
                except ValueError:
                    pass

        print(f"  [tripoli] Записів: {len(records)}")
        if not records:
            print(f"  [tripoli] DEBUG bodyText (перші 600 символів):")
            print(body[:600])

    except Exception as e:
        print(f"  [tripoli] Помилка: {e}")
        import traceback; traceback.print_exc()
    finally:
        await browser.close()
    return records


# ─────────────────────────────────────────────────────────────────────────────
# E-ZERNO.COM — парсинг профілів покупців
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ezerno_bodytext(text: str, company: str, default_region: str, now_str: str,
                            target_cultures=None) -> list:
    """Парсить bodyText профільної сторінки e-zerno."""
    records = []
    if target_cultures is None:
        target_cultures = list(EZERNO_CULTURE_MAP.keys())

    # Знаходимо блоки: "Культура X клас\nЦіна\nUAH/т\nМісто\nОбласть"
    culture_re = '|'.join(re.escape(c) for c in target_cultures)
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip().lower()
        matched_culture = None
        for c in target_cultures:
            if c in line:
                matched_culture = c
                break

        if matched_culture:
            ctx = '\n'.join(lines[max(0, i-2):i+5])
            # Ціна — 4–6-значне число
            price = None
            for chunk in lines[i:i+6]:
                pm = re.search(r'\b(\d{4,6})\b', chunk.strip().replace('\u00a0', ''))
                if pm:
                    p = float(pm.group(1))
                    if 3000 <= p <= 60000:
                        price = p
                        break
            if price:
                # Шукаємо регіон по-рядково у вузькому вікні (перший hit = найближчий)
                quality = _detect_quality(ctx)
                # Локація — місто/область (рядок після ціни)
                location = company
                for chunk in lines[i:i+8]:
                    s = chunk.strip()
                    if s and re.match(r'[А-ЯІЄЇ]', s) and not re.search(r'\d{4}', s) and matched_culture not in s.lower():
                        location = s[:60]
                        break
                # Регіон: спершу з локації покупця, потім лише вперед від назви культури
                # (раніше вікно i-2 підхоплювало область попереднього блоку)
                region = _detect_region(location)
                if region == "невідомо":
                    for cl in lines[i:i+6]:
                        r = _detect_region(cl)
                        if r != "невідомо":
                            region = r
                            break
                if region == "невідомо":
                    region = default_region
                # Дата
                dm = re.search(r'\d{2}[./]\d{2}[./]\d{4}', ctx)
                date_str = dm.group(0) if dm else now_str

                # URL профілю покупця якщо є
                buyer_url = "https://e-zerno.com/grain-prices"
                for bname, burl, _ in EZERNO_PROFILES:
                    if bname.lower() in company.lower() or company.lower() in bname.lower():
                        buyer_url = burl; break
                rec = _make_record("e-zerno.com", matched_culture, quality,
                                   price, region, location, date_str, "EXW",
                                   url=buyer_url)
                rec["buyer"] = company[:50] if company and company.lower() not in ("e-zerno", "e-zerno.com") else None
                records.append(rec)
        i += 1

    # Дедуплікація
    seen, unique = set(), []
    for r in records:
        key = (r['culture'], r['price_uah'], r['location'][:20])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


async def _parse_ezerno(pw, target_cultures=None) -> list:
    """Парсить профілі e-zerno.com через Playwright.

    Стратегія:
    1. Пробуємо головну сторінку + клік "Ціни на зерно" → якщо відкрито → парсимо
    2. Далі пробуємо EZERNO_PROFILES по черзі
    """
    if target_cultures is None:
        target_cultures = list(EZERNO_CULTURE_MAP.keys())

    all_records = []
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    browser, context = await _new_playwright_context(pw)

    try:
        page = await context.new_page()

        # ── Спроба 1: головна → "Ціни на зерно" ──────────────────────────────
        print("  [ezerno] Спроба через головну сторінку...")
        await page.goto("https://e-zerno.com/", timeout=35_000, wait_until="networkidle")
        await _dismiss_banners(page)
        await page.wait_for_timeout(1500)

        try:
            await page.click("text=Ціни на зерно", timeout=3000)
            await page.wait_for_timeout(2500)
        except Exception:
            pass

        url_now = page.url
        print(f"  [ezerno] Поточний URL: {url_now}")
        body = await page.evaluate("() => document.body.innerText || ''")

        # Якщо не на профілі (зміг відкрити список) — парсимо
        if '/grain-prices' in url_now or 'price' in url_now.lower():
            recs = _parse_ezerno_bodytext(body, "e-zerno", "невідомо", now_str, target_cultures)
            if recs:
                print(f"  [ezerno] Головна: {len(recs)} записів")
                all_records.extend(recs)

        # Профілі з числовими ID додавати після ручної перевірки на сайті
        # EZERNO_PROFILES наразі містить slug-based URL що дають 404
        # → коментар залишаємо, профілі не запускаємо

    except Exception as e:
        print(f"  [ezerno] Загальна помилка: {e}")
        import traceback; traceback.print_exc()
    finally:
        await browser.close()

    # Hard cap: відсіюємо явні помилки парсингу
    PRICE_CAP = {
        'ріпак': 24_000, 'соя': 21_500, 'соняшник': 21_000,
        'пшениця': 12_000, 'кукурудза': 10_000, 'ячмінь': 10_000,
    }
    all_records = [
        r for r in all_records
        if r['price_uah'] <= PRICE_CAP.get(r['culture'], 60_000)
    ]

    # Дедуплікація по всіх профілях
    seen, unique = set(), []
    for r in all_records:
        key = (r['culture'], r['price_uah'], r['location'][:20])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    print(f"  [ezerno] Всього записів (олійні): {len(unique)}")
    if not unique:
        print("  [ezerno] ⚠️  0 записів. Можливі причини:")
        print("           1. Профільні URL змінились — потрібно перевірити в браузері")
        print("           2. Компанії на e-zerno не публікують олійні публічно")
        print("           3. Потрібна реєстрація на e-zerno.com")
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# GRAINTRADE.COM.UA — щоденна стаття «Закупівельні ціни на зерно в Україні на …»
# Таблиця-матриця: рядок = продукт, стовпці = базиси (CPT термінал, EXW елеватори,
# CPT переробник, FCA — у грн; FCA/CPT/DAF/CIF — у $). Значення — СЕРЕДНІ по Україні,
# без пункту приймання → це орієнтир (ref_kind="national_avg"), а не оферта: net не рахуємо.
# Виправлено 08.11.2026: (1) URL статті тепер «na-6-listopada» (день без нуля, інша
# транслітерація) — беремо посилання зі стрічки новин; (2) раніше парсер читав
# «стовпець 1 = базис, стовпець 2 = ціна» → ячмінь (лише CPT термінал) не потрапляв.
# ─────────────────────────────────────────────────────────────────────────────

GT_BASE = "https://graintrade.com.ua"
GT_NEWS_URL = GT_BASE + "/novosti"
GT_ARTICLE_RE = re.compile(
    r'href="((?:https://graintrade\.com\.ua)?/novosti/zakupivelni-tcini-na-zerno-v-ukraini-na-(\d{1,2})-([a-z]+)-(\d{4})-roku\.html)"')
GT_MONTHS = {  # транслітерація graintrade (перевірено: listopada)
    'sichnya': 1, 'lyutogo': 2, 'lutogo': 2, 'bereznya': 3, 'kvitnya': 4, 'travnya': 5,
    'chervnya': 6, 'lipnya': 7, 'serpnya': 8, 'veresnya': 9, 'zhovtnya': 10,
    'listopada': 11, 'grudnya': 12,
}
GT_MONTHS_INV = {v: k for k, v in GT_MONTHS.items() if k != 'lutogo'}
# Порядок важливий: перший збіг виграє
GT_CULTURES = [('ячмін', 'ячмінь'), ('пшениц', 'пшениця'), ('кукурудз', 'кукурудза'),
               ('соняшник', 'соняшник'), ('соя', 'соя'), ('ріпак', 'ріпак')]
GT_NON_CROP = re.compile(r'олі[яї]|шрот|макух|жмих|висівк|лушпин', re.I)
GT_BASIS = [('cpt термінал', 'CPT термінал'), ('exw елеватор', 'EXW елеватор'),
            ('cpt переробник', 'CPT переробник'), ('fca', 'FCA')]
GT_LOCATION = "Середня по Україні (GrainTrade)"


def _gt_fetch(url: str):
    """urllib → (html, final_url) або (None, None)."""
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=25) as resp:
            if resp.getcode() != 200:
                print(f"  [graintrade] HTTP {resp.getcode()} {url}")
                return None, None
            return resp.read().decode('utf-8', errors='replace'), resp.geturl()
    except Exception as e:
        print(f"  [graintrade] urllib: {e} ({url})")
        return None, None


def _gt_article_links(listing_html: str) -> list:
    """[(url, date), …] статей із цінами, найновіші першими."""
    out, seen = [], set()
    for m in GT_ARTICLE_RE.finditer(listing_html or ''):
        href, day, mon, year = m.groups()
        mo = GT_MONTHS.get(mon)
        if not mo:
            continue
        try:
            d = datetime(int(year), mo, int(day))
        except ValueError:
            continue
        url = href if href.startswith('http') else GT_BASE + href
        if url not in seen:
            seen.add(url)
            out.append((url, d))
    return sorted(out, key=lambda x: x[1], reverse=True)


def _gt_guess_urls(today: datetime, days: int = 5) -> list:
    from datetime import timedelta
    res = []
    for delta in range(days):
        d = today - timedelta(days=delta)
        res.append((f"{GT_BASE}/novosti/zakupivelni-tcini-na-zerno-v-ukraini-na-"
                    f"{d.day}-{GT_MONTHS_INV[d.month]}-{d.year}-roku.html",
                    datetime(d.year, d.month, d.day)))
    return res


def _gt_cell_price(text: str):
    """«8353 ↓ 149» → 8353.0; порожньо/«&nbsp;» → None. Береться лише перше число (до стрілки)."""
    t = (text or '').replace('\u00a0', ' ').strip()
    t = re.split(r'[↑↓]', t)[0]
    m = re.search(r'\d[\d\s]*', t)
    if not m:
        return None
    try:
        return float(re.sub(r'\s', '', m.group(0)))
    except ValueError:
        return None


def parse_graintrade_table(html: str, date_str: str, url: str) -> list:
    """Розбирає таблицю цін зі статті. Чиста функція — тестується на збереженому HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  [graintrade] bs4 не встановлено")
        return []
    soup = BeautifulSoup(html or '', 'html.parser')
    table = soup.find('table', class_='news-table-price')
    if table is None:   # запасний варіант: перша таблиця з «термінал» у шапці
        table = next((t for t in soup.find_all('table') if 'термінал' in t.get_text(' ').lower()), None)
    if table is None:
        return []
    rows = table.find_all('tr')
    if not rows:
        return []
    header = [c.get_text(' ', strip=True).lower() for c in rows[0].find_all(['th', 'td'])]
    cols = {}   # індекс стовпця → базис (лише гривневі)
    for i, h in enumerate(header):
        if 'грн' not in h:
            continue
        hn = re.sub(r'\s+', ' ', h)
        for key, name in GT_BASIS:
            if key in hn:
                cols[i] = name
                break
    records = []
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        name = cells[0].get_text(' ', strip=True)
        nl = name.lower()
        if GT_NON_CROP.search(nl):
            continue
        culture = next((c for k, c in GT_CULTURES if nl.startswith(k) or f' {k}' in f' {nl}'), None)
        if not culture:
            continue
        quality = re.sub(r'(?i)^(ячмінь|пшениця|кукурудза|соняшник|соя|ріпак)\s*', '', name).strip() or None
        for i, basis in cols.items():
            if i >= len(cells):
                continue
            price = _gt_cell_price(cells[i].get_text(' ', strip=True))
            if price is None or not (3000 <= price <= 60000):
                continue
            rec = _make_record("graintrade.com.ua", culture, quality, price, "Україна",
                               f"{GT_LOCATION} · {basis}", date_str, basis, url=url)
            rec["net_kopani"] = None
            rec["net_dolynske"] = None
            rec["ref_kind"] = "national_avg"
            rec["vat"] = "невідомо"
            records.append(rec)
    return records


async def _gt_fetch_playwright(pw, url: str):
    """Запасний шлях, якщо urllib заблоковано (403 з IP GitHub)."""
    browser, context = await _new_playwright_context(pw)
    try:
        page = await context.new_page()
        await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        return await page.content(), page.url
    except Exception as e:
        print(f"  [graintrade] playwright: {e} ({url})")
        return None, None
    finally:
        await browser.close()


async def _parse_graintrade(pw=None) -> list:
    """Знаходить найсвіжішу статтю з цінами (до 5 днів — вихідні без статей) і розбирає таблицю."""
    async def fetch(url):
        html, final = _gt_fetch(url)
        if html is None and pw is not None:
            html, final = await _gt_fetch_playwright(pw, url)
        return html, final

    listing, _ = await fetch(GT_NEWS_URL)
    candidates = _gt_article_links(listing)
    if not candidates:
        print("  [graintrade] у стрічці новин статей з цінами не знайдено — пробую сконструйовані URL")
        candidates = _gt_guess_urls(datetime.now())
    cutoff = datetime.now() - __import__('datetime').timedelta(days=6)
    for url, d in candidates[:4]:
        if d < cutoff:
            break
        html, final = await fetch(url)
        if not html:
            continue
        if final and final.rstrip('/').endswith('/novosti'):
            print(f"  [graintrade] {url} → редирект на стрічку (статті немає)")
            continue
        recs = parse_graintrade_table(html, d.strftime("%d.%m.%Y"), url)
        if recs:
            by_c = {}
            for r in recs:
                by_c[r['culture']] = by_c.get(r['culture'], 0) + 1
            print(f"  [graintrade] {d.strftime('%d.%m')}: {len(recs)} записів {by_c} | {url}")
            return recs
        print(f"  [graintrade] {url}: таблицю не розпізнано")
    print("  [graintrade] ⚠️  0 записів")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — всі парсери через єдиний Playwright контекст
# ─────────────────────────────────────────────────────────────────────────────

async def _run_all() -> list:
    """Запускає всі парсери послідовно (один Playwright процес → менше ресурсів)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ПОМИЛКА: playwright не встановлено. Запусти:")
        print("  pip3 install playwright && python3 -m playwright install chromium")
        return []

    all_records = []

    async with async_playwright() as pw:
        # 1. Nibulon
        print("Завантажую nibulon.com ...")
        recs = await _parse_nibulon(pw)
        print(f"  Знайдено: {len(recs)} записів Нібулон")
        all_records.extend(recs)

        # 2. Tripoli.land
        print("Завантажую tripoli.land ...")
        recs = await _parse_tripoli(pw)
        print(f"  Знайдено: {len(recs)} записів tripoli.land")
        all_records.extend(recs)

        # 3. E-zerno.com (соняшник, соя, ріпак через профілі покупців)
        print("Завантажую e-zerno.com (профілі покупців — соняшник / соя / ріпак) ...")
        recs = await _parse_ezerno(pw, ['соняшник', 'соя', 'ріпак'])
        print(f"  Знайдено: {len(recs)} записів e-zerno.com")
        all_records.extend(recs)

        # 4. Graintrade.com.ua — середні по Україні (орієнтир; єдине стабільне джерело ячменю)
        print("Завантажую graintrade.com.ua (середні ціни по базисах, вкл. ячмінь) ...")
        recs = await _parse_graintrade(pw)
        print(f"  Знайдено: {len(recs)} записів graintrade.com.ua")
        all_records.extend(recs)


    return all_records


def main():
    print(f"=== Web Prices Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")

    all_records = asyncio.run(_run_all())

    # Вивід зведення
    print("\n── Результат ──")
    for r in all_records:
        q   = f" ({r['quality']})" if r.get('quality') else ""
        net = f" | net Копані {r['net_kopani']:,.0f}" if r.get('net_kopani') is not None else ""
        print(f"  {r['culture']:12s}{q:8s} {r['price_uah']:>7,.0f} ₴{net}"
              f" | {r['location']} ({r['region']}) | {r['source']}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usd_uah": USD_UAH,
        "records": all_records,
    }
    with open("web_prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nЗбережено: web_prices.json ({len(all_records)} записів)")


if __name__ == "__main__":
    main()
