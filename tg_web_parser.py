"""
AGRO BAROMETER — Telegram Parser
Режим 1 (пріоритет): Telethon + TG_SESSION — читає приватні та публічні канали
Режим 2 (fallback):  Playwright — тільки публічні t.me/s/
Зберігає: telegram_prices.json
"""

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo
KYIV = ZoneInfo("Europe/Kyiv")
# Курс: NBU_USD_UAH (бере CI з bank.gov.ua) → USD_UAH_RATE (секрет) → запасний
USD_UAH = float(os.environ.get("NBU_USD_UAH") or os.environ.get("USD_UAH_RATE") or "45.47")
EUR_UAH = float(os.environ.get("NBU_EUR_UAH") or "0") or None  # без курсу EUR-ціни не конвертуємо

# ─── КАНАЛИ ───────────────────────────────────────────────────────────────────
# Telethon може читати всі; Playwright — тільки публічні (без *)
CHANNELS = [
    ("navigate_agro",        "prices"),   # щоденний прайс — основний
    ("agrohub_od",           "agrohub"),  # структурований прайс: #КУЛЬТУРА / ✅ пункт (область) Ф-2: ціна
    ("AgroBrok",             "prices"),   # EXW/DAP
    ("rawagro",              "prices"),   # РО АГРО ТРЕЙД — прайс 6 культур
    ("Agroprosperis_price",  "prices"),   # Агропросперіс
    ("GrainTradeUA",         "board"),    # біржа: беремо лише «Куплю …» + новини
    ("apkinform",            "prices"),   # АПК-Інформ ціни
    ("spike_brokers",        "context"),  # тижневий огляд
    ("latifundistmedia",     "news"),
]

# API credentials для Telethon
TG_API_ID   = int(os.environ.get("TG_API_ID",   "") or "30430309")
TG_API_HASH = os.environ.get("TG_API_HASH", "") or "4360b5aa9c5cf78aff7f3ba2d9c661fc"
TG_SESSION  = os.environ.get("TG_SESSION",  "")

# ─── МАПИ ─────────────────────────────────────────────────────────────────────
CULTURE_HEADERS = {
    "рапс": "ріпак", "ріпак": "ріпак", "соняшник": "соняшник",
    "соя": "соя", "пшениця": "пшениця", "кукуруз": "кукурудза",
    "ячмінь": "ячмінь",
}
CULTURE_KW = {   # основи слів — щоб ловити відмінки (пшеницю, кукурудзи, ячменю…)
    "ріпак":     ["ріпак", "рапс"],
    "соняшник":  ["соняшник", "подсолн"],
    "соя":       ["соя", "сої", "сою", "соєв"],
    "пшениця":   ["пшениц"],
    "кукурудза": ["кукуруд", "кукуруз"],
    "ячмінь":    ["ячмін", "ячмен"],
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
    if currency == "EUR": return round(val * EUR_UAH) if EUR_UAH else None
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



# ─── СТРУКТУРОВАНІ ПАРСЕРИ ────────────────────────────────────────────────────

REGION_WORDS = {
    "одес": "Одеська", "черкас": "Черкаська", "миколаїв": "Миколаївська",
    "кіровоград": "Кіровоградська", "вінниц": "Вінницька", "хмельниц": "Хмельницька",
    "полтав": "Полтавська", "дніпро": "Дніпропетровська", "київськ": "Київська",
    "житомир": "Житомирська", "запоріз": "Запорізька", "херсон": "Херсонська",
    "чернів": "Чернівецька", "тернопіл": "Тернопільська", "львів": "Львівська",
    "рівнен": "Рівненська", "волин": "Волинська", "сум": "Сумська",
    "харків": "Харківська", "чернігів": "Чернігівська", "івано-франк": "Івано-Франківська",
}

def _region_from_text(t):
    t = (t or "").lower()
    for k, v in REGION_WORDS.items():
        if k in t:
            return v
    return None

def _clean_md(t):
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t or "")
    return re.sub(r"[*_`]+", "", t).strip()

# Продукти переробки / нецільові — не плутати з насінням культури
NON_CROP_RE = re.compile(r"олі[яїює]|шрот|макуха|жмих|лушпин|насінн|посівн|тверд|борошн|висівк|фураж", re.I)

def _unbox(t):
    """🅺🅴🆁🅽🅴🅻 / 🄺🄴… → KERNEL (емодзі-літери, якими agrohub пише назви покупців)."""
    out = []
    for ch in t:
        o = ord(ch)
        if 0x1F170 <= o <= 0x1F189: out.append(chr(ord("A") + o - 0x1F170))
        elif 0x1F130 <= o <= 0x1F149: out.append(chr(ord("A") + o - 0x1F130))
        elif 0x1F150 <= o <= 0x1F169: out.append(chr(ord("A") + o - 0x1F150))
        else: out.append(ch)
    return "".join(out)


def parse_agrohub(text, date_str, channel="agrohub_od"):
    """@agrohub_od — блоки:
         🌻 #СОНЯШНИК
         ✅ ОЕЗ ЧОРНОМОРСЬК ⭐
         🅺🅴🆁🅽🅴🅻
         (Одеська область)
         Ф-2: 12700 грн
         (8/3/48 на сухе + за олійність)
       «Всі ціни вказані за умови доставки» → базис: доставка на пункт (CPT), Ф-2 = з ПДВ.
    """
    records = []
    culture = None
    blk = None

    def emit(price_line):
        pm_uah = re.search(r"(\d[\d\s']{2,6}\d)\s*грн", price_line, re.I)
        pm_usd = re.search(r"(\d{2,4})\s*\$", price_line)
        if pm_uah:
            raw_val = float(re.sub(r"[\s']", "", pm_uah.group(1))); cur = "UAH"; uah = raw_val
        elif pm_usd:
            raw_val = float(pm_usd.group(1)); cur = "USD"; uah = to_uah(raw_val, "USD")
        else:
            return None
        c = blk.get("culture", culture)
        if not c:
            return None
        loc = blk.get("location", "невідомо")
        rec = {
            "source": f"@{channel}", "culture": c, "quality": None,
            "price_raw": raw_val, "price_uah": float(uah), "currency": cur,
            "basis": "CPT пункт (Ф-2)" if re.search(r"Ф-?2", price_line) else "CPT пункт",
            "vat": "з ПДВ" if re.search(r"Ф-?2", price_line) else "невідомо",
            "location": loc[:40], "buyer": blk.get("buyer"),
            "region": blk.get("region") or _guess_region(loc),
            "date": date_str, "url": f"https://t.me/{channel}",
            "net_kopani": None, "net_dolynske": None,
        }
        records.append(rec)
        return rec

    last = None
    for raw in (text or "").split("\n"):
        line = _unbox(_clean_md(raw)).strip()
        if not line:
            continue
        hm = re.search(r"#\s*([А-ЯІЇЄA-Zа-яіїє]+)", line)
        if hm:
            culture = _find_culture(hm.group(1))   # нішеві / невідомі → None
            blk = None
            continue
        if line.startswith("✅"):
            blk = {"location": line.lstrip("✅ ").replace("⭐", "").strip()}
            last = None
            continue
        if blk is None:
            continue
        rm = re.match(r"^\((.+област[ьі].*)\)$", line, re.I)
        if rm:
            blk["region"] = _region_from_text(rm.group(1))
            continue
        if re.fullmatch(r"[A-Z0-9 .&-]{3,}", line):
            blk["buyer"] = line.strip()
            continue
        if re.search(r"Ф-?2\s*:|грн|\$", line) and re.search(r"\d", line):
            last = emit(line)
            continue
        if line.startswith("(") and last is not None:
            last["quality"] = line.strip("()")[:40]   # умови якості/знижок
            continue
        # назва культури всередині блоку (напр. «🌱КОРІАНДР») — перевизначає культуру блоку
        if len(line) < 30 and not line.startswith("👉"):
            c = _find_culture(line)
            blk["culture"] = c
    return records

BOARD_RE = re.compile(
    r"^\s*(Куплю|Продам)\s+([^,]+),\s*(.+?)\s*\(№\s*(\d+)\)\s*"
    r"(?:(\d[\d\s]*)\s*тон[а-я]*)?\s*за ціною\s*(\d[\d\s.,]*)\s*(грн|USD|\$|EUR|євро)\s*за тонну"
    r"(?:\s*на умовах\s*([A-ZА-Я]{3}))?", re.I | re.S)

def parse_board(text, date_str, channel="GrainTradeUA"):
    """@GrainTradeUA біржа: беремо лише «Куплю <культура>» — заявка покупця з посиланням на лот."""
    t = _clean_md(text)
    m = BOARD_RE.search(t)
    if not m or m.group(1).lower() != "куплю":
        return []
    product = m.group(2).strip()
    if NON_CROP_RE.search(product):
        return []
    culture = _find_culture(product)
    if not culture:
        return []
    val = float(re.sub(r"[\s,]", "", m.group(6)).rstrip("."))
    cur = {"грн": "UAH", "usd": "USD", "$": "USD"}.get(m.group(7).lower(), "EUR")
    uah = val if cur == "UAH" else to_uah(val, cur)
    if uah is None:
        return []
    url_m = re.search(r"https?://graintrade\.com\.ua/\S+", t)
    return [{
        "source": f"@{channel}", "culture": culture,
        "quality": _clean_md(product)[:30],
        "price_raw": val, "price_uah": float(uah), "currency": cur,
        "basis": (m.group(8) or "невідомо").upper(), "vat": "невідомо",
        "location": "невідомо", "region": "невідомо",
        "buyer": m.group(3).replace('\\"', '"').replace("✅", "").strip()[:50],
        "volume_t": float(re.sub(r"\s", "", m.group(5))) if m.group(5) else None,
        "date": date_str, "url": url_m.group(0) if url_m else f"https://t.me/{channel}",
        "net_kopani": None, "net_dolynske": None,
    }]

def is_board_ad(text):
    return bool(re.match(r"\s*\**\s*(Куплю|Продам)\s", _clean_md(text or ""), re.I))

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
    """Загальний парсер: розбирає по рядках; культура — із заголовка свого блоку або самого рядка."""
    records = []
    if not text or len(text) < 10:
        return records
    culture = None
    for raw in text.split("\n"):
        line = _clean_md(raw)
        if not line:
            continue
        c = _find_culture(line)
        if c:
            culture = c
        if not culture or NON_CROP_RE.search(line):
            continue
        if re.search(r'\bбн\b|без пдв', line.lower()):
            continue
        found = []
        for m in UAH_RE.finditer(line):
            try:
                v = float(m.group(1).replace(" ", "").replace("'", ""))
            except ValueError:
                continue
            if 3000 <= v <= 40000:
                found.append((v, "UAH", v))
        for m in USD_RE.finditer(line):
            v = float(m.group(1))
            if 80 <= v <= 900:
                found.append((v, "USD", float(to_uah(v, "USD"))))
        for raw_val, cur, uah in found:
            location = re.split(r"[-–—:]|\d", line)[0].strip(" ✅📍•")[:40] or "невідомо"
            records.append({
                "source": f"@{channel}", "culture": culture, "quality": None,
                "price_raw": raw_val, "price_uah": uah, "currency": cur,
                "basis": _find_basis(line), "vat": "невідомо",
                "location": location,
                "region": _region_from_text(line) or _guess_region(location),
                "date": date_str, "url": f"https://t.me/{channel}",
                "net_kopani": None, "net_dolynske": None,
            })
    return records


def _parse_by_role(channel, role, text, date_str):
    if role == "prices":
        if channel == "navigate_agro":
            return parse_navigate_agro(text, date_str)
        return parse_generic_msg(text, channel, date_str)
    if role == "agrohub":
        return parse_agrohub(text, date_str, channel)
    if role == "board":
        return parse_board(text, date_str, channel)
    return []


def _news_record(channel, text, msg_dt, msg_id=None):
    clean = _clean_md(text)
    clean = re.sub(r"\s+", " ", clean).strip()
    # Заголовок — перше речення/рядок до 140 символів
    first = re.split(r"(?<=[.!?])\s|\n", _clean_md(text).strip(), maxsplit=1)[0]
    title = re.sub(r"\s+", " ", first).strip()[:140] or clean[:140]
    summary = clean[len(title):].strip()[:300] if clean.startswith(title) else clean[:300]
    ext = re.search(r"\((https?://(?!t\.me)[^)\s]+)\)", text or "") or re.search(r"https?://(?!t\.me)\S+", text or "")
    tg_url = f"https://t.me/{channel}/{msg_id}" if msg_id else f"https://t.me/{channel}"
    return {
        "source":  f"@{channel}",
        "title":   title,
        "url":     (ext.group(1) if ext and ext.lastindex else ext.group(0)) if ext else tg_url,
        "tg_url":  tg_url,
        "date":    msg_dt.astimezone(KYIV).strftime("%d.%m.%Y %H:%M"),
        "ts":      msg_dt.astimezone(timezone.utc).isoformat(),
        "summary": summary,
    }


NEWS_MAX_AGE_H = 30   # новини з Telegram — тільки за останню добу (+запас на час запуску)

# ─── TELETHON SCRAPER ────────────────────────────────────────────────────────

# Ключові слова виключно про 6 культур і зерновий ринок — без "ринок", "прогноз" (занадто широко)
AGRO_NEWS_KW = [
    "пшениц", "кукурудз", "соняшник", "сої", "соя", "ріпак", "рапс",
    "ячмінь", "ячменю",
    "зернов", "олія соняшник", "шрот соняшник", "шрот соєв",
    "USDA", "WASDE", "IGC", "чорноморськ зерн",
    "нібулон", "кернел", "астарта",
    "wheat", "corn", "maize", "sunflower", "soybean", "rapeseed", "barley",
    "grain export", "grain market", "ukraine grain",
]

# Паттерни прайс-повідомлень — відразу відкидаємо
_PRICE_MSG_RE = re.compile(
    r'ЦІНИ ЗАКУПІВЛІ|ЦІНИ ПРОДАЖУ|прайс[\s-]*лист|'
    r'Ф-2\s*:|\bФ2\b|ЕXW\s*:\s*\d|CPT\s*:\s*\d|'
    r'КОНТЕЙНЕРНИЙ ТЕРМІНАЛ|ЕЛЕВАТОР.*Ф-2|'
    r'\*\*#\w+\*\*.*Ф-2',
    re.IGNORECASE,
)

def _is_news_msg(text: str) -> bool:
    """Чи є повідомлення аналітикою/новиною, а не прайс-таблицею."""
    if not text or len(text) < 80:
        return False
    # Явні прайс-повідомлення — відкидаємо одразу
    if _PRICE_MSG_RE.search(text):
        return False
    t = text.lower()
    if not any(kw.lower() in t for kw in AGRO_NEWS_KW):
        return False
    head = t[:200]
    if re.search(r"\b(?:молок|молоч|тваринн|свин|птах|птиц|яйц|м'яс|мясн|укрзалізн|залізниц|вагон)", head):
        return False   # нецільові теми (якщо в заголовку, а не мимохідь)
    if re.search(r"актуальні закупівельні ціни|контакти для співпраці|пишіть в особисті|за телефоном", t) and len(t) < 600:
        return False   # рекламні/контактні пости без змісту
    # Відкидаємо, якщо забагато цін і мало зв'язного тексту
    price_hits = len(UAH_RE.findall(text)) + len(USD_RE.findall(text))
    words = len(re.findall(r'[а-яіїєa-z]{4,}', t))
    bold_markers = text.count("**")
    if price_hits >= 4 and words < 25:
        return False  # цінова таблиця
    if bold_markers >= 8 and price_hits >= 2:
        return False  # markdown прайс (agrohub_od стиль)
    return True


async def _telethon_fetch_all(cutoff: datetime) -> tuple[list, list]:
    """Читає всі канали через Telethon (потребує TG_SESSION).
    Повертає (price_records, news_records).
    """
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError

    all_prices = []
    all_news   = []

    client = TelegramClient(StringSession(TG_SESSION), TG_API_ID, TG_API_HASH,
                            system_version="4.16.30-vxCUSTOM")
    await client.connect()

    if not await client.is_user_authorized():
        print("  [telethon] ❌ сесія недійсна — переавторизуйся")
        await client.disconnect()
        return [], []

    me = await client.get_me()
    print(f"  [telethon] ✅ авторизовано як @{me.username or me.first_name}")

    news_cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_MAX_AGE_H)
    for channel, role in CHANNELS:
        try:
            msgs = []
            async for msg in client.iter_messages(channel, limit=80):
                if not msg.date:
                    continue
                msg_dt = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                if msg_dt < cutoff:
                    break
                if msg.text:
                    msgs.append({"text": msg.text, "datetime": msg_dt, "id": msg.id})

            print(f"  [telethon] @{channel} ({role}): {len(msgs)} свіжих повід.")

            price_count = 0
            news_count  = 0
            for m in msgs:
                date_str = m["datetime"].astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
                text = m["text"]
                recs = _parse_by_role(channel, role, text, date_str)
                for r in recs:
                    if r.get("url", "").rstrip("/") == f"https://t.me/{channel}":
                        r["url"] = f"https://t.me/{channel}/{m['id']}"
                all_prices.extend(recs)
                price_count += len(recs)

                if (m["datetime"] >= news_cutoff and not recs
                        and not is_board_ad(text) and _is_news_msg(text)):
                    all_news.append(_news_record(channel, text, m["datetime"], m["id"]))
                    news_count += 1

            if price_count:
                print(f"  [telethon] @{channel}: {price_count} цінових записів")
            elif role in ("prices", "agrohub") and msgs:
                # діагностика: сирий початок повідомлень, з яких нічого не розпізнано
                for m in msgs[:2]:
                    print(f"  [debug] @{channel} не розпізнано: {m['text'][:120]!r}")
            if news_count:
                print(f"  [telethon] @{channel}: {news_count} новинних повід.")

        except FloodWaitError as e:
            print(f"  [telethon] @{channel}: FloodWait {e.seconds}s — пропускаємо")
        except (ChannelPrivateError, UsernameNotOccupiedError) as e:
            print(f"  [telethon] @{channel}: ❌ {e}")
        except Exception as e:
            print(f"  [telethon] @{channel}: помилка ({e})")

        await asyncio.sleep(1)  # щоб не тригернути flood limit

    await client.disconnect()
    return all_prices, all_news


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

            if not text:
                continue

            msg_count += 1
            date_str = msg_date.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
            recs = _parse_by_role(channel, role, text, date_str)

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
    """Net рахуємо лише коли регіон покупця відомий і є в таблиці фрахту — не вигадуємо ставку."""
    for r in records:
        region = r.get("region", "невідомо")
        fk = FREIGHT["Копані"].get(region) if region != "невідомо" else None
        fd = FREIGHT["Долинське"].get(region) if region != "невідомо" else None
        r["net_kopani"]   = r["price_uah"] - fk if fk is not None else None
        r["net_dolynske"] = r["price_uah"] - fd if fd is not None else None
    return records


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def _run_all():
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)

    # ── Режим 1: Telethon ──────────────────────────────────────────────────────
    if TG_SESSION:
        print("  [tg] Режим: Telethon (авторизований)")
        try:
            prices, news = await _telethon_fetch_all(cutoff)
            # Зберігаємо новини окремо для news_parser.py
            if True:  # пишемо завжди, навіть порожній — щоб не підхопити застарілий файл
                import pathlib
                pathlib.Path("telegram_news.json").write_text(
                    json.dumps({"records": news, "total": len(news),
                                "generated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"  [tg] ✅ telegram_news.json: {len(news)} новинних повід.")
            if prices:
                return _add_net(prices)
            print("  [tg] Telethon повернув 0 цінових записів — fallback на Playwright")
        except Exception as e:
            print(f"  [tg] Telethon помилка ({e}) — fallback на Playwright")
    else:
        print("  [tg] TG_SESSION не задано — режим Playwright (тільки публічні)")

    # ── Режим 2: Playwright fallback ──────────────────────────────────────────
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ПОМИЛКА: pip3 install playwright && python3 -m playwright install chromium")
        return []

    all_records = []

    async with async_playwright() as pw:
        for channel, role in CHANNELS:
            recs = await _scrape_channel(pw, channel, role, cutoff)
            all_records.extend(recs)

    return _add_net(all_records)


def main():
    print(f"=== Telegram Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")
    mode = "Telethon" if TG_SESSION else "Playwright (публічні)"
    print(f"Режим: {mode}\n")

    all_records = asyncio.run(_run_all())

    # ─── Підсумок по культурах ────────────────────────────────────────────────
    CULTURE_ORDER = ["ріпак", "соняшник", "соя", "кукурудза", "ячмінь", "пшениця"]
    summary = {}
    print("\n── Підсумок по культурах ──")

    for culture in CULTURE_ORDER:
        recs = [r for r in all_records if r["culture"] == culture]
        if not recs:
            continue
        with_net = [r for r in recs if r.get("net_kopani") is not None]
        best_price = max(recs, key=lambda x: x["price_uah"])
        best_net  = max(with_net, key=lambda x: x["net_kopani"]) if with_net else best_price
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
        nk = best_net.get('net_kopani')
        print(f"  {culture.upper()}: найвища {best_price['price_uah']:,.0f} ₴ | "
              f"net Копані {(f'{nk:,.0f}' if nk is not None else '—')} ₴ | "
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
