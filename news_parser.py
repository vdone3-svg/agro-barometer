"""
AGRO BAROMETER — News Parser
Збирає агро-новини за останні 24 год (вікно 7:00–7:00)
Джерела: latifundist.com (RSS + web), agroportal.ua, apk-inform.com, ukragroconsult.com
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
MAX_AGE_HOURS = 30          # вікно: 30 год назад (щоб не пропустити ніч)
MAX_ITEMS_TOTAL = 25        # макс новин у підсумковому файлі
MAX_PER_SOURCE = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.9",
}

# Ключові слова для фільтрації релевантних агро-новин (достатньо одного)
AGRO_KEYWORDS = [
    "пшениц", "кукурудз", "соняшник", "соя", "ріпак", "ячмінь",
    "зерно", "олія", "шрот", "врожай", "збирання", "посів",
    "експорт", "imporт", "ціна", "тонна", "елеватор",
    "USDA", "ФАО", "FAO", "агро", "зернов", "хліб", "борошн",
    "тариф", "ПДВ", "митниц", "залізниц", "укрзалізниц",
    "nibulon", "нібулон", "кернел", "kernel", "астарта",
]

def _is_agro(title: str, text: str = "") -> bool:
    combined = (title + " " + text).lower()
    return any(kw.lower() in combined for kw in AGRO_KEYWORDS)

def _fetch(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            enc = r.headers.get_content_charset("utf-8")
            return raw.decode(enc, errors="replace")
    except Exception as e:
        print(f"  [fetch] ❌ {url}: {e}")
        return None

def _parse_rss_item(item_xml: str) -> dict | None:
    """Витягує title, link, pubDate, description з одного <item> RSS."""
    def _tag(tag):
        m = re.search(rf'<{tag}[^>]*>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>', item_xml, re.S)
        return m.group(1).strip() if m else ""
    title = re.sub(r'<[^>]+>', '', _tag("title")).strip()
    link  = _tag("link") or _tag("guid")
    pub   = _tag("pubDate") or _tag("dc:date") or _tag("published")
    desc  = re.sub(r'<[^>]+>', '', _tag("description")).strip()[:300]
    if not title or not link:
        return None
    return {"title": title, "url": link.strip(), "pub": pub.strip(), "summary": desc}

def _parse_rss_date(pub: str) -> datetime | None:
    """Намагається розпарсити RSS pubDate у timezone-aware datetime."""
    if not pub:
        return None
    # RFC 2822: Thu, 01 Nov 2026 10:30:00 +0200
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
    m2 = re.search(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})', pub)
    if m2:
        yr,mo,dy,hh,mm = m2.groups()
        return datetime(int(yr),int(mo),int(dy),int(hh),int(mm), tzinfo=timezone.utc)
    return None

def _rss_items(rss_text: str) -> list[dict]:
    items = re.findall(r'<item[^>]*>(.*?)</item>', rss_text, re.S)
    result = []
    for item_xml in items:
        parsed = _parse_rss_item(item_xml)
        if parsed:
            result.append(parsed)
    return result

def _age_ok(pub_str: str, now: datetime, max_hours: int) -> bool:
    dt = _parse_rss_date(pub_str)
    if not dt:
        return True  # якщо не парситься дата — беремо
    return (now - dt).total_seconds() / 3600 <= max_hours

# ─── ДЖЕРЕЛА ─────────────────────────────────────────────────────────────────

def parse_latifundist() -> list[dict]:
    """latifundist.com — RSS-стрічка новин."""
    print("  [latifundist] Завантаження RSS...")
    rss = _fetch("https://latifundist.com/rss/news", timeout=20)
    if not rss:
        rss = _fetch("https://latifundist.com/feed", timeout=20)
    if not rss:
        print("  [latifundist] ❌ RSS недоступний")
        return []
    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:40]:
        if not _age_ok(item["pub"], now, MAX_AGE_HOURS):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        dt = _parse_rss_date(item["pub"])
        records.append({
            "source": "latifundist.com",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   dt.strftime("%d.%m.%Y %H:%M") if dt else item["pub"][:16],
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [latifundist] ✅ {len(records)} новин")
    return records


def parse_agroportal() -> list[dict]:
    """agroportal.ua — RSS-стрічка."""
    print("  [agroportal] Завантаження RSS...")
    rss = _fetch("https://agroportal.ua/rss/news.xml", timeout=20)
    if not rss:
        rss = _fetch("https://agroportal.ua/rss/", timeout=20)
    if not rss:
        print("  [agroportal] ❌ RSS недоступний")
        return []
    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:40]:
        if not _age_ok(item["pub"], now, MAX_AGE_HOURS):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        dt = _parse_rss_date(item["pub"])
        records.append({
            "source": "agroportal.ua",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   dt.strftime("%d.%m.%Y %H:%M") if dt else item["pub"][:16],
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [agroportal] ✅ {len(records)} новин")
    return records


def parse_apkinform() -> list[dict]:
    """apk-inform.com — RSS."""
    print("  [apk-inform] Завантаження RSS...")
    rss = _fetch("https://www.apk-inform.com/uk/rss/news", timeout=20)
    if not rss:
        rss = _fetch("https://www.apk-inform.com/rss/", timeout=20)
    if not rss:
        print("  [apk-inform] ❌ RSS недоступний")
        return []
    items = _rss_items(rss)
    now = datetime.now(timezone.utc)
    records = []
    for item in items[:40]:
        if not _age_ok(item["pub"], now, MAX_AGE_HOURS):
            continue
        if not _is_agro(item["title"], item["summary"]):
            continue
        dt = _parse_rss_date(item["pub"])
        records.append({
            "source": "apk-inform.com",
            "title":  item["title"][:200],
            "url":    item["url"],
            "date":   dt.strftime("%d.%m.%Y %H:%M") if dt else item["pub"][:16],
            "summary": item["summary"][:250],
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [apk-inform] ✅ {len(records)} новин")
    return records


def parse_ukragroconsult() -> list[dict]:
    """ukragroconsult.com — розбираємо головну сторінку новин."""
    print("  [ukragroconsult] Завантаження...")
    html = _fetch("https://ukragroconsult.com/analytikacin/", timeout=20)
    if not html:
        print("  [ukragroconsult] ❌ недоступний")
        return []
    # Шукаємо блоки новин: <a href="/analytikacin/...">Заголовок</a> + дата
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
        # Шукаємо дату поблизу
        snippet = html[max(0,m.start()-200):m.end()+200]
        dm = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', snippet)
        date_str = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else ""
        if date_str and not _age_ok(date_str+"T12:00", now, MAX_AGE_HOURS+24):
            continue
        records.append({
            "source": "ukragroconsult.com",
            "title":  title[:200],
            "url":    full_url,
            "date":   f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}" if dm else "?",
            "summary": "",
        })
        if len(records) >= MAX_PER_SOURCE:
            break
    print(f"  [ukragroconsult] ✅ {len(records)} новин")
    return records


# ─── ГОЛОВНА ФУНКЦІЯ ──────────────────────────────────────────────────────────

def main():
    print(f"=== News Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")

    all_news: list[dict] = []
    for parser_fn in [parse_latifundist, parse_agroportal, parse_apkinform, parse_ukragroconsult]:
        try:
            all_news.extend(parser_fn())
        except Exception as e:
            print(f"  ❌ {parser_fn.__name__}: {e}")

    # Дедуплікація за URL
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for item in all_news:
        u = item["url"].rstrip("/")
        if u not in seen_urls:
            seen_urls.add(u)
            unique.append(item)

    # Сортуємо: найновіші вперед (за date string — підходить якщо DD.MM.YYYY HH:MM)
    # Тримаємо тільки MAX_ITEMS_TOTAL
    unique.sort(key=lambda x: x.get("date",""), reverse=True)
    unique = unique[:MAX_ITEMS_TOTAL]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(unique),
        "items": unique,
    }
    Path(NEWS_FILE).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {NEWS_FILE} збережено: {len(unique)} новин")
    for n in unique[:5]:
        print(f"   [{n['source']}] {n['date']} — {n['title'][:70]}")
    return 0


if __name__ == "__main__":
    exit(main())
