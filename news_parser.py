"""
AGRO BAROMETER — News Parser
Збирає агро-новини за останні 30 год
Джерела: agroportal.ua, ukrinform.net/agro, graintrade.com.ua, ukragroconsult.com
Зберігає: news_data.json
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────
NEWS_FILE = "news_data.json"
MAX_AGE_HOURS = 24          # суворо 24 год — тільки свіже
MAX_ITEMS_TOTAL = 50
MAX_PER_SOURCE = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ─── КЛЮЧОВІ СЛОВА: тільки 6 культур і прямий ринок збуту ───────────────────
# НЕ включаємо: молоко, тваринництво, ЖД, дороги, добрива, пестициди,
# загальні слова "агро"/"аграр"/"хліб"/"ціна" (надто широко)
AGRO_KEYWORDS_UK = [
    # 6 культур
    "пшениц", "кукурудз", "соняшник", "соняшнику",
    "сої", "соя", "соєв",
    "ріпак", "рапс",
    "ячмінь", "ячменю",
    # ринок збуту зернових
    "зерновий ринок", "зерновий експорт", "зернові",
    "олія соняшникова", "шрот соняшниковий", "шрот соєвий",
    "врожай зерн", "збирання зерн", "посівна кампані",
    "елеватор", "зернотрейдер",
    "нібулон", "кернел", "астарта",
    "USDA", "WASDE", "IGC", "чорноморськ зерн",
    "прогноз врожаю", "баланс зерн", "світовий ринок зерн",
]
AGRO_KEYWORDS_EN = [
    "wheat", "corn", "maize", "sunflower",
    "soybean", "soy meal", "soy oil",
    "rapeseed", "canola", "barley",
    "grain export", "grain market", "grain harvest",
    "oilseed", "USDA", "WASDE", "IGC", "Black Sea grain",
    "ukraine grain", "ukrainian grain",
]

def _is_agro(title: str, text: str = "") -> bool:
    combined = (title + " " + text).lower()
    return (
        any(kw.lower() in combined for kw in AGRO_KEYWORDS_UK) or
        any(kw.lower() in combined for kw in AGRO_KEYWORDS_EN)
    )

def _fetch(url: str, timeout: int = 20) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            # Handle gzip
            if r.info().get('Content-Encoding') == 'gzip':
                import gzip
                raw = gzip.decompress(raw)
            enc = r.headers.get_content_charset("utf-8")
            return raw.decode(enc, errors="replace")
    except urllib.error.HTTPError as e:
        print(f"  [fetch] ❌ {url}: HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  [fetch] ❌ {url}: {e}")
        return None

def _parse_rss_item(item_xml: str) -> dict | None:
    def _tag(tag):
        m = re.search(rf'<{tag}[^>]*>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>', item_xml, re.S | re.I)
        return m.group(1).strip() if m else ""
    title = re.sub(r'<[^>]+>', '', _tag("title")).strip()
    link  = _tag("link") or _tag("guid")
    # <link> sometimes contains whitespace/newlines around CDATA
    link  = re.sub(r'\s+', '', link)
    pub   = _tag("pubDate") or _tag("dc:date") or _tag("published") or _tag("updated")
    desc  = re.sub(r'<[^>]+>', '', _tag("description") or _tag("summary")).strip()[:300]
    if not title or not link:
        return None
    # Fix relative links
    if link.startswith("/"):
        return None  # will fix in caller
    return {"title": title, "url": link.strip(), "pub": pub.strip(), "summary": desc}

def _parse_rss_date(pub: str) -> datetime | None:
    if not pub:
        return None
    # RFC 2822
    m = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4}|UTC|GMT)', pub)
    if m:
        MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                  "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
        day, mon_s, yr, hh, mm, ss, tz_s = m.groups()
        mon = MONTHS.get(mon_s, 1)
        offset = 0
        if tz_s not in ("UTC", "GMT"):
            sign = 1 if tz_s[0]=='+' else -1
            offset = sign*(int(tz_s[1:3])*60 + int(tz_s[3:5]))
        dt = datetime(int(yr), mon, int(day), int(hh), int(mm), int(ss),
                      tzinfo=timezone(timedelta(minutes=offset)))
        return dt.astimezone(timezone.utc)
    # ISO 8601
    m2 = re.search(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})', pub)
    if m2:
        yr,mo,dy,hh,mm = m2.groups()
        return datetime(int(yr),int(mo),int(dy),int(hh),int(mm), tzinfo=timezone.utc)
    return None

def _rss_items(rss_text: str) -> list[dict]:
    items = re.findall(r'<item[^>]*>(.*?)</item>', rss_text, re.S | re.I)
    if not items:
        # Atom feed
        items = re.findall(r'<entry[^>]*>(.*?)</entry>', rss_text, re.S | re.I)
    result = []
    for item_xml in items:
        parsed = _parse_rss_item(item_xml)
        if parsed:
            result.append(parsed)
    return result

def _age_ok(pub_str: str, now: datetime, unknown_ok: bool = False) -> bool:
    """unknown_ok=True тільки для RSS (дата є завжди); False для HTML (дата невідома = пропустити)."""
    dt = _parse_rss_date(pub_str)
    if not dt:
        return unknown_ok  # HTML без дати — пропускаємо, щоб не тягнути застарілі
    return (now - dt).total_seconds() / 3600 <= MAX_AGE_HOURS

def _fmt_dt(pub_str: str) -> str:
    dt = _parse_rss_date(pub_str)
    if dt:
        # Convert to Kyiv time (UTC+2)
        kyiv = dt + timedelta(hours=2)
        return kyiv.strftime("%d.%m.%Y %H:%M")
    return pub_str[:16]

# ─── ДЖЕРЕЛА ─────────────────────────────────────────────────────────────────

def parse_agroportal() -> list[dict]:
    """agroportal.ua — RSS (пробуємо uk та /en)."""
    print("  [agroportal] Завантаження RSS...")
    rss = None
    for url in [
        "https://agroportal.ua/uk/rss",
        "https://agroportal.ua/rss",
        "https://agroportal.ua/en/rss",
        "https://agroportal.ua/news/rss",
    ]:
        rss = _fetch(url)
        if rss and ("<item" in rss or "<entry" in rss):
            print(f"  [agroportal] RSS знайдено: {url}")
            break

    if not rss:
        print("  [agroportal] ❌ RSS недоступний — парсимо HTML")
        return _parse_agroportal_html()

    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:40]:
        if not _age_ok(item["pub"], now, unknown_ok=True):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        records.append({
            "source": "agroportal.ua",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   _fmt_dt(item["pub"]),
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [agroportal] ✅ {len(records)} новин")
    return records

def _parse_agroportal_html() -> list[dict]:
    """Fallback: парсимо HTML головної сторінки agroportal.ua."""
    html = _fetch("https://agroportal.ua/news/", timeout=25)
    if not html:
        return []
    records = []
    now = datetime.now(timezone.utc)
    # <a href="/news/...">Title</a>
    for m in re.finditer(r'<a[^>]+href="(/(?:uk/)?news/[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{15,200}?)\s*</[^>]+>', html):
        path, title = m.group(1), m.group(2).strip()
        title = re.sub(r'\s+', ' ', title)
        if not _is_agro(title):
            continue
        full_url = f"https://agroportal.ua{path}"
        snippet  = html[max(0,m.start()-300):m.end()+300]
        dm = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', snippet)
        if not dm:
            continue
        date_str = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"
        records.append({"source":"agroportal.ua","title":title[:200],"url":full_url,"date":date_str,"summary":""})
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [agroportal HTML] ✅ {len(records)} новин")
    return records


def parse_ukrinform_agro() -> list[dict]:
    """ukrinform.net — RSS розділу Агро/Економіка."""
    print("  [ukrinform] Завантаження RSS...")
    rss = None
    for url in [
        "https://www.ukrinform.ua/rss/block-agroindustrial_complex",
        "https://www.ukrinform.net/rss/block-economy.rss",
        "https://www.ukrinform.ua/rss/rubric-economy",
    ]:
        rss = _fetch(url)
        if rss and ("<item" in rss or "<entry" in rss):
            print(f"  [ukrinform] RSS знайдено: {url}")
            break

    if not rss:
        print("  [ukrinform] ❌ RSS недоступний")
        return []

    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:50]:
        if not _age_ok(item["pub"], now, unknown_ok=True):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        records.append({
            "source": "ukrinform.ua",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   _fmt_dt(item["pub"]),
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [ukrinform] ✅ {len(records)} новин")
    return records


def parse_graintrade_news() -> list[dict]:
    """graintrade.com.ua — сторінка новин (вже парсили ціни, тут беремо новинні статті)."""
    print("  [graintrade] Завантаження новин...")
    html = _fetch("https://graintrade.com.ua/novosti", timeout=25)
    if not html:
        print("  [graintrade] ❌ недоступний")
        return []

    now = datetime.now(timezone.utc)
    records = []
    # graintrade: <a href="/novosti/...">title</a> + дата поруч
    for m in re.finditer(
        r'<a[^>]+href="(/novosti/[^"?#]+)"[^>]*>\s*([^<]{15,250}?)\s*</a>',
        html
    ):
        path, title = m.group(1), m.group(2).strip()
        title = re.sub(r'\s+', ' ', title)
        if len(title) < 15 or not _is_agro(title):
            continue
        full_url = f"https://graintrade.com.ua{path}"
        # Шукаємо дату поблизу (формат DD.MM.YYYY або словесний)
        snippet = html[max(0, m.start()-200):m.end()+200]
        dm = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', snippet)
        if dm:
            yr, mo, dy = int(dm.group(3)), int(dm.group(2)), int(dm.group(1))
            pub_dt = datetime(yr, mo, dy, 12, 0, tzinfo=timezone.utc)
            if (now - pub_dt).total_seconds() / 3600 > MAX_AGE_HOURS + 24:
                continue
            date_str = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"
        else:
            continue   # без дати не беремо — інакше стара стаття висить днями
        if full_url not in {r["url"] for r in records}:
            records.append({"source":"graintrade.com.ua","title":title[:200],"url":full_url,"date":date_str,"summary":""})
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [graintrade] ✅ {len(records)} новин")
    return records


def parse_ukragroconsult() -> list[dict]:
    """ukragroconsult.com — головна сторінка аналітики."""
    print("  [ukragroconsult] Завантаження...")
    html = _fetch("https://ukragroconsult.com/analytikacin/", timeout=20)
    if not html:
        print("  [ukragroconsult] ❌ недоступний")
        return []

    now = datetime.now(timezone.utc)
    records = []
    for m in re.finditer(
        r'<a[^>]+href="(/analytikacin/[^"]+)"[^>]*>\s*([^<]{10,200}?)\s*</a>',
        html
    ):
        url_path, title = m.group(1), m.group(2).strip()
        title = re.sub(r'\s+', ' ', title)
        if not _is_agro(title):
            continue
        full_url = f"https://ukragroconsult.com{url_path}"
        snippet = html[max(0, m.start()-200):m.end()+200]
        dm = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', snippet)
        if dm:
            yr, mo, dy = int(dm.group(3)), int(dm.group(2)), int(dm.group(1))
            pub_dt = datetime(yr, mo, dy, 12, 0, tzinfo=timezone.utc)
            if (now - pub_dt).total_seconds() / 3600 > MAX_AGE_HOURS + 36:
                continue
            date_str = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"
        else:
            continue   # без дати не беремо — інакше стара стаття висить днями
        if full_url not in {r["url"] for r in records}:
            records.append({"source":"ukragroconsult.com","title":title[:200],"url":full_url,"date":date_str,"summary":""})
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [ukragroconsult] ✅ {len(records)} новин")
    return records


def parse_latifundist_html() -> list[dict]:
    """latifundist.com — парсимо HTML розділу новин (RSS повертає 404)."""
    print("  [latifundist] Завантаження HTML новин...")
    html = _fetch("https://latifundist.com/novosti/", timeout=25)
    if not html:
        print("  [latifundist] ❌ недоступний")
        return []

    now = datetime.now(timezone.utc)
    records = []
    # latifundist: <a href="/novosti/..."> або абсолютне посилання
    for m in re.finditer(
        r'<a[^>]+href="((?:https?://latifundist\.com)?/novosti/[^"?#]{5,})"[^>]*>\s*([^<]{15,250}?)\s*</a>',
        html
    ):
        raw_url, title = m.group(1), m.group(2).strip()
        url = raw_url if raw_url.startswith("http") else f"https://latifundist.com{raw_url}"
        title = re.sub(r'\s+', ' ', title)
        if len(title) < 25 or not _is_agro(title):
            continue   # «Елеватори» тощо — це рубрика, не стаття
        snippet = html[max(0, m.start()-300):m.end()+300]
        dm = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', snippet)
        if dm:
            yr, mo, dy = int(dm.group(3)), int(dm.group(2)), int(dm.group(1))
            pub_dt = datetime(yr, mo, dy, 12, 0, tzinfo=timezone.utc)
            if (now - pub_dt).total_seconds() / 3600 > MAX_AGE_HOURS + 24:
                continue
            date_str = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"
        else:
            continue   # без дати не беремо — інакше стара стаття висить днями
        if url not in {r["url"] for r in records}:
            records.append({"source":"latifundist.com","title":title[:200],"url":url,"date":date_str,"summary":""})
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [latifundist] ✅ {len(records)} новин")
    return records


def parse_infagro() -> list[dict]:
    """infagro.com.ua — агро-новини."""
    print("  [infagro] Завантаження...")
    rss = None
    for url in [
        "https://infagro.com.ua/rss/",
        "https://infagro.com.ua/feed/",
        "https://infagro.com.ua/rss.xml",
    ]:
        rss = _fetch(url, timeout=15)
        if rss and ("<item" in rss or "<entry" in rss):
            print(f"  [infagro] RSS знайдено: {url}")
            break
    if not rss:
        print("  [infagro] ❌ RSS недоступний")
        return []
    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:40]:
        if not _age_ok(item["pub"], now, unknown_ok=True):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        records.append({
            "source": "infagro.com.ua",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   _fmt_dt(item["pub"]),
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [infagro] ✅ {len(records)} новин")
    return records


def parse_telegram_news() -> list[dict]:
    """Читає telegram_news.json, збережений tg_web_parser.py."""
    tg_file = Path("telegram_news.json")
    if not tg_file.exists():
        print("  [tg-news] telegram_news.json не знайдено — пропускаємо")
        return []
    try:
        data = json.loads(tg_file.read_text(encoding="utf-8"))
        records = data.get("records", [])
    except Exception as e:
        print(f"  [tg-news] ❌ помилка читання: {e}")
        return []

    # Додаткова фільтрація + дедуп за title (повідомлення можуть повторюватись)
    seen_titles: set[str] = set()
    result = []
    for r in records:
        t = r.get("title", "")[:80]
        if t in seen_titles:
            continue
        seen_titles.add(t)
        result.append({
            "source":  r.get("source", "@telegram"),
            "title":   r.get("title", "")[:200],
            "url":     r.get("url", ""),
            "tg_url":  r.get("tg_url", ""),
            "date":    r.get("date", ""),
            "ts":      r.get("ts", ""),
            "summary": r.get("summary", "")[:300],
        })
    # не більше 12 з одного каналу, щоб один канал не забивав стрічку
    per = {}
    capped = []
    for r in sorted(result, key=lambda x: x.get("ts", ""), reverse=True):
        per[r["source"]] = per.get(r["source"], 0) + 1
        if per[r["source"]] <= 12:
            capped.append(r)
    result = capped
    print(f"  [tg-news] ✅ {len(result)} повідомлень з Telegram")
    return result


# ─── ГОЛОВНА ФУНКЦІЯ ──────────────────────────────────────────────────────────

def main():
    print(f"=== News Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")

    all_news: list[dict] = []
    for parser_fn in [
        parse_telegram_news,       # Telegram — найбільше свіжої аналітики
        parse_latifundist_html,
        parse_infagro,
        parse_agroportal,
        parse_ukrinform_agro,
        parse_graintrade_news,
        parse_ukragroconsult,
    ]:
        try:
            all_news.extend(parser_fn())
        except Exception as e:
            print(f"  ❌ {parser_fn.__name__}: {e}")

    # Дедуплікація: за URL якщо унікальний, або за title[:60] для Telegram
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for item in all_news:
        u = item["url"].rstrip("/")
        t = item.get("title", "")[:60].lower().strip()
        # Telegram канали мають однаковий URL — дедублюємо за title
        is_tg = u.startswith("https://t.me/")
        if is_tg:
            if t in seen_titles:
                continue
            seen_titles.add(t)
        else:
            if u in seen_urls:
                continue
            seen_urls.add(u)
            seen_titles.add(t)
        unique.append(item)

    # Сортуємо за справжнім часом (рядок «дд.мм.рррр» сортується неправильно між місяцями)
    def _key(x):
        if x.get("ts"):
            return x["ts"]
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?", x.get("date", ""))
        if not m:
            return ""
        d, mo, y, hh, mm = m.groups()
        return f"{y}-{mo}-{d}T{hh or '12'}:{mm or '00'}"
    unique.sort(key=_key, reverse=True)
    unique = unique[:MAX_ITEMS_TOTAL]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(unique),
        "items": unique,
    }
    Path(NEWS_FILE).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {NEWS_FILE}: {len(unique)} новин")
    for n in unique[:8]:
        print(f"   [{n['source']}] {n['date']} — {n['title'][:70]}")
    return 0


if __name__ == "__main__":
    exit(main())
