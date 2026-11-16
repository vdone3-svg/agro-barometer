"""
AGRO BAROMETER — ціни на мінеральні добрива (₴/т)
Додано 16.11.2026: до цього блок «Добрива» на сайті був статичним (жовт. 2026) і не оновлювався зовсім.

Джерела:
  • grossdorf.com/price/ — оптовий прайс дистриб'ютора з датою «від ДД.ММ.РРРР» (оновлюється часто),
    колонки — склади (Хацьки/Черкаська, Маяки/Вінницька, Полтава, Вознесенськ, Прилуки, Тернопіль);
    «уточнюється» → ціни немає. Роздрібна таблиця (фасування 1,5 кг) не береться.
  • e-zerno.com/fertilizer-prices — картки дистриб'юторів «Ціни на ДД.ММ.РРРР»; беремо не старші FRESH_DAYS.
Усе це — опубліковані прайси, не підтверджені оферти. Ціни не вигадуються: немає в джерелі → немає на сайті.
Зберігає: fert_data.json
"""
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
GROSSDORF_URL = "https://grossdorf.com/price/"
EZERNO_URL = "https://e-zerno.com/fertilizer-prices"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "uk-UA,uk;q=0.9",
}
SANITY = (8000, 90000)   # ₴/т — лише відсіяти помилки розбору
FRESH_DAYS = 21          # картки e-zerno старші — не беремо

# (ключ, regex назви, підпис, чи важлива формула NPK); порядок = порядок показу
PRODUCTS = [
    ("селітра",     r"аміачн\w*\s+селітр|селітра\s+аміачн", "Аміачна селітра N:34", False),
    ("карбамід",    r"карбамід|сечовин",                     "Карбамід N:46", False),
    ("кас",         r"\bкас\b",                              "КАС", True),
    ("сульфат",     r"сульфат\w*\s+амон",                    "Сульфат амонію N:21 S:24", False),
    ("нафоска",     r"нітроамофоск|\bнаф\b|нітроамофос",     "Нітроамофоска (НАФ)", True),
    ("діамофоска",  r"діамофоск",                            "Діамофоска", True),
    ("діамофос",    r"діамофос(?!к)|\bdap\b",                "Діамофос (DAP)", True),
    ("амофос",      r"(?<!ді)амофос(?!к)|\bmap\b",           "Амофос (MAP)", True),
]
ORDER = [p[0] for p in PRODUCTS]


def _num(s):
    s = re.sub(r"[\s  ]", "", s or "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def classify(name: str):
    n = (name or "").lower()
    for key, rx, label, npk in PRODUCTS:
        if re.search(rx, n):
            return key, label, npk
    return None, None, False


def formula(text: str) -> str | None:
    """«( N:15 P:15 K:15 )», «N15:P15:K15+11S», «КАС-32», «15:15:15» → «15:15:15» / «32»."""
    t = text or ""
    parts = re.findall(r"([NPK])\s*:?\s*(\d{1,2})", t)
    if parts:
        return ":".join(v for _, v in parts)
    m = re.search(r"\b(\d{1,2})(?:\s*:\s*(\d{1,2}))(?:\s*:\s*(\d{1,2}))?", t)
    if m:
        return ":".join(g for g in m.groups() if g)
    m = re.search(r"кас\s*[-–]?\s*(\d{2})", t, re.I)
    return m.group(1) if m else None


def _rec(name, price, date, source, url, location=None, company=None):
    key, label, npk = classify(name)
    if not key or price is None or not (SANITY[0] <= price <= SANITY[1]):
        return None
    f = formula(name) if npk else None
    if key == "кас" and not f:
        f = "32" if "32" in name else None
    return {"key": key + (f":{f}" if f else ""), "base": key,
            "name": label + (f" {f}" if f and key != "кас" else (f"-{f}" if f else "")),
            "price": round(price), "date": date, "source": source, "url": url,
            "location": location, "company": company}


# ── Grossdorf ────────────────────────────────────────────────────────────────

def parse_grossdorf(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" "))
    m = (re.search(r"опт\w*\D{0,60}?від\s*(\d{2}\.\d{2}\.\d{4})", text, re.I)
         or re.search(r"від\s*(\d{2}\.\d{2}\.\d{4})", text))
    date = m.group(1) if m else None
    out = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        if any("пакуван" in h.lower() for h in head):   # роздріб 1,5 кг — не порівнюється з ₴/т
            continue
        for row in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            for i, cell in enumerate(cells[2:], start=2):
                if not re.search(r"\d", cell) or "уточн" in cell.lower():
                    continue
                loc = head[i] if i < len(head) else None
                r = _rec(cells[0], _num(cell), date, "Grossdorf", GROSSDORF_URL, location=loc, company="GROSSDORF")
                if r:
                    out.append(r)
    # примітка під таблицею: «Карбамід (порт Чорноморськ) – 31 000 грн/т»
    for m2 in re.finditer(r"((?:Карбамід|Аміачна селітра|Сульфат амонію)[^–\-\d]{0,40})[–\-]\s*(\d{1,3}(?:\s\d{3})+|\d{4,6})\s*грн\s*/\s*т", text):
        loc = re.search(r"\(([^)]+)\)", m2.group(1))
        r = _rec(m2.group(1), _num(m2.group(2)), date, "Grossdorf", GROSSDORF_URL,
                 location=loc.group(1) if loc else None, company="GROSSDORF")
        if r and not any(x["base"] == r["base"] and x["price"] == r["price"] for x in out):
            out.append(r)
    return out


# ── e-zerno ──────────────────────────────────────────────────────────────────

_EZ_PROD = r"(Аміачна селітра|Селітра аміачна|Карбамід|Сечовина|КАС|Сульфат амонію|Нітроамофоска|Діамофоска|Діамофос|Амофос)"
_EZ_ROW = re.compile(_EZ_PROD + r"[^()\d]{0,30}\(\s*([^)]{1,40})\)\s*(\d{1,3}(?:[   ]\d{3})+|\d{4,6})")


def parse_ezerno_text(text: str, today=None) -> list[dict]:
    """Текст сторінки → записи. Картка: «… Ціни на 30.10.2026 … Аміачна селітра( N:34 )27 500 Україна / OSTCHEM …»."""
    today = today or datetime.now(KYIV).date()
    t = re.sub(r"\s+", " ", text or "")
    segs = re.split(r"Ціни на\s+", t)
    out = []
    for seg in segs[1:]:
        m = re.match(r"(\d{2}\.\d{2}\.\d{4}|сьогодні)", seg, re.I)
        if not m:
            continue
        if m.group(1).lower() == "сьогодні":
            continue   # «Ціни на сьогодні» без дати — свіжість не підтверджена, не беремо
        else:
            try:
                d = datetime.strptime(m.group(1), "%d.%m.%Y").date()
            except ValueError:
                continue
        if (today - d).days > FRESH_DAYS or d > today + timedelta(days=1):
            continue
        for rm in _EZ_ROW.finditer(seg[:600]):
            tail = seg[rm.end():rm.end() + 80]
            loc = re.search(r"([А-ЯІЇЄҐ][а-яіїєґ'’]+ обл\.\s*[А-ЯІЇЄҐ][\w'’\-]+)", tail)
            r = _rec(f"{rm.group(1)} ({rm.group(2)})", _num(rm.group(3)), d.strftime("%d.%m.%Y"),
                     "e-zerno", EZERNO_URL, location=loc.group(1) if loc else None)
            if r:
                out.append(r)
    return out


# ── збірка ───────────────────────────────────────────────────────────────────

def aggregate(records: list[dict]) -> list[dict]:
    """Групує за продуктом (+формула): мін–макс, к-сть, найсвіжіша дата. Не усереднює різні формули."""
    groups: dict[str, dict] = {}
    for r in records:
        g = groups.setdefault(r["key"], {"key": r["key"], "base": r["base"], "name": r["name"], "records": []})
        g["records"].append(r)
    out = []
    for g in groups.values():
        ps = [r["price"] for r in g["records"]]
        dates = [datetime.strptime(r["date"], "%d.%m.%Y") for r in g["records"] if r.get("date")]
        g.update(min=min(ps), max=max(ps), n=len(ps),
                 date_latest=max(dates).strftime("%d.%m.%Y") if dates else None,
                 sources=sorted({r["source"] for r in g["records"]}))
        g["records"].sort(key=lambda r: r["price"])
        out.append(g)
    out.sort(key=lambda g: (ORDER.index(g["base"]), g["key"]))
    return out


def _fetch_urllib(url):
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [fert] urllib {url}: {e}")
        return None


async def _fetch_playwright(url, text=False):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="uk-UA")).new_page()
            await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            return await (page.inner_text("body") if text else page.content())
        except Exception as e:
            print(f"  [fert] playwright {url}: {e}")
            return None
        finally:
            await browser.close()


def _html_text(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html or "", "html.parser").get_text(" ")


def main():
    print(f"=== Fertilizer Parser {datetime.now(KYIV).strftime('%d.%m.%Y %H:%M')} ===")
    recs = []
    gd = []
    html = _fetch_urllib(GROSSDORF_URL)
    if html:
        gd = parse_grossdorf(html)
    if not gd:
        html = asyncio.run(_fetch_playwright(GROSSDORF_URL))
        gd = parse_grossdorf(html) if html else []
    print(f"  [fert] Grossdorf: {len(gd)} цін")
    ez = []
    html = _fetch_urllib(EZERNO_URL)
    if html:
        ez = parse_ezerno_text(_html_text(html))
    if not ez:
        txt = asyncio.run(_fetch_playwright(EZERNO_URL, text=True))
        ez = parse_ezerno_text(txt) if txt else []
    print(f"  [fert] e-zerno: {len(ez)} цін (не старші {FRESH_DAYS} дн.)")
    recs = gd + ez
    items = aggregate(recs)
    for g in items:
        print(f"  {g['name']:30s} {g['min']:>7,}–{g['max']:>7,} ₴/т  n={g['n']}  {g['date_latest']}  {', '.join(g['sources'])}")
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), "fresh_days": FRESH_DAYS,
            "counts": {"grossdorf": len(gd), "ezerno": len(ez)}, "items": items}
    with open("fert_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
