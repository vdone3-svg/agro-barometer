"""
AGRO BAROMETER — ціни на пальне (середні по Україні на АЗС)
Джерело: index.minfin.com.ua/ua/markets/fuel/ (оновлюється в робочі дні; дані А-95 Консалтинг).
Запасний шлях: Playwright, якщо urllib заблоковано з IP GitHub.
Зберігає: fuel_data.json
16.11.2026: minfin (А-95 Консалтинг) не публікує у вихідні й оновлюється ~14:00, тож ранковий прогін у сб/нд/пн
показував п'ятницю. Додано auto.ria.com/uk/toplivo/ (середня по Україні, джерело — Мінфін, але дата оновлення
є й у вихідні). Береться джерело з новішою датою; при однаковій даті — minfin.
Додано 08.11.2026 — до цього блок «Паливо» на сайті був статичним (29.10) і не оновлювався.
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

URL = "https://index.minfin.com.ua/ua/markets/fuel/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "uk-UA,uk;q=0.9",
}
# назва на сайті → ключ і підпис на барометрі; порядок = порядок показу
FUEL_KEYS = [
    ("дизель", "Дизельне паливо", "Дизель (ДП) АЗС сер."),
    ("а95", "Бензин А-95", "Бензин А-95"),
    ("а95п", "Бензин А-95 преміум", "А-95 Преміум"),
    ("газ", "Газ авто", "Автогаз"),
]
SANITY = (20.0, 250.0)   # ₴/л — лише відсіяти помилки розбору


def _num(s):
    s = (s or "").replace(" ", "").replace(" ", "").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_minfin(html: str) -> dict:
    """Чиста функція: HTML сторінки → {"date": "ДД.ММ.РРРР", "items": [...]}; тестується на фікстурі."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.find("table", class_="line")
    if table is None:
        table = next((t for t in soup.find_all("table") if "дизель" in t.get_text(" ").lower()), None)
    if table is None:
        return {"date": None, "items": []}
    date = None
    cap = table.find("caption")
    m = re.search(r"(\d{1,2})\.(\d{2})\.(\d{4})", cap.get_text(" ") if cap else "")
    if not m:   # «останнє оновлення: 06.11.2026 13:24»
        m = re.search(r"оновлення:\s*(\d{1,2})\.(\d{2})\.(\d{4})", soup.get_text(" "))
    if m:
        date = f"{int(m.group(1)):02d}.{m.group(2)}.{m.group(3)}"
    items = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        name = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True).replace("­", ""))
        big = row.find("big")
        price = _num(big.get_text() if big else cells[2].get_text())
        if price is None or not (SANITY[0] <= price <= SANITY[1]):
            continue
        smalls = row.find_all("small")
        delta = _num(smalls[0].get_text()) if smalls else None
        pct = _num(smalls[1].get_text()) if len(smalls) > 1 else None
        nl = name.lower()
        key = label = None
        for k, src, lab in FUEL_KEYS:
            s = src.lower()
            if k == "а95" and "преміум" in nl:
                continue
            if nl.startswith(s) or (k == "газ" and nl.startswith("газ")):
                key, label = k, lab
                break
        if not key or any(i["key"] == key for i in items):
            continue
        items.append({"key": key, "name": label, "price": price, "delta_day": delta, "pct_day": pct,
                      "unit": "₴/л", "source": "index.minfin.com.ua", "url": URL})
    order = [k for k, _, _ in FUEL_KEYS]
    items.sort(key=lambda i: order.index(i["key"]))
    return {"date": date, "items": items}


AUTORIA_URL = "https://auto.ria.com/uk/toplivo/"
AUTORIA_KEYS = {"a-95+": "а95п", "a-95": "а95", "дп": "дизель", "газ": "газ"}


def parse_autoria(html: str) -> dict:
    """auto.ria.com/uk/toplivo/: «Інформація оновлена 2026-11-14», таблиця «Пальне | Ціна, грн/л | Динаміка».
    Береться перша (загальноукраїнська) таблиця; регіональна має назви областей у першій колонці й не збігається."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text("\n")
    date = None
    m = re.search(r"оновлен\w*\s*:?\s*(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        date = f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    else:
        m = re.search(r"оновлен\w*\s*:?\s*(\d{1,2})\.(\d{2})\.(\d{4})", text)
        if m:
            date = f"{int(m.group(1)):02d}.{m.group(2)}.{m.group(3)}"
    label = {k: lab for k, _, lab in FUEL_KEYS}
    found = {}

    def norm(n):   # «А-95» кирилицею і «A-95» латиницею — однаково
        return re.sub(r"\s+", "", n).lower().replace("а", "a")
    keys = {norm(k): v for k, v in AUTORIA_KEYS.items()}

    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        key = keys.get(norm(cells[0]))
        price = _num(cells[1])
        if not key or key in found or price is None or not (SANITY[0] <= price <= SANITY[1]):
            continue
        delta = _num(cells[2]) if len(cells) > 2 and re.search(r"\d", cells[2]) else None
        found[key] = {"key": key, "name": label[key], "price": price, "delta_day": delta, "pct_day": None,
                      "unit": "₴/л", "source": "auto.ria.com (дані Мінфіну)", "url": AUTORIA_URL}
    if not found:   # запасний розбір по тексту
        for m in re.finditer(r"(?m)^\s*([AА]-95\+?|ДП|Газ)\s*$\s*(\d{2,3}[.,]\d{1,2})", text):
            key = keys.get(norm(m.group(1)))
            price = _num(m.group(2))
            if key and key not in found and price and SANITY[0] <= price <= SANITY[1]:
                found[key] = {"key": key, "name": label[key], "price": price, "delta_day": None, "pct_day": None,
                              "unit": "₴/л", "source": "auto.ria.com (дані Мінфіну)", "url": AUTORIA_URL}
    order = [k for k, _, _ in FUEL_KEYS]
    return {"date": date, "items": sorted(found.values(), key=lambda i: order.index(i["key"]))}


def _ddmmyyyy(s):
    try:
        return datetime.strptime(s or "", "%d.%m.%Y")
    except ValueError:
        return None


def pick_fresher(minfin: dict, autoria: dict) -> dict:
    """Новіша дата перемагає; при рівних — minfin (першоджерело). Позиції, яких бракує, добираються з іншого."""
    dm, da = _ddmmyyyy(minfin.get("date")), _ddmmyyyy(autoria.get("date"))
    if autoria.get("items") and (not minfin.get("items") or (da and (not dm or da > dm))):
        main, other = autoria, minfin
    else:
        main, other = minfin, autoria
    if not main.get("items"):
        return {"date": None, "items": []}
    have = {i["key"] for i in main["items"]}
    if other.get("date") == main.get("date"):
        main = dict(main, items=main["items"] + [i for i in other.get("items", []) if i["key"] not in have])
    order = [k for k, _, _ in FUEL_KEYS]
    main["items"].sort(key=lambda i: order.index(i["key"]))
    main["source_used"] = main["items"][0]["source"]
    main["dates_seen"] = {"minfin": minfin.get("date"), "autoria": autoria.get("date")}
    return main


def _fetch_urllib(url=URL):
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [fuel] urllib: {e}")
        return None


async def _fetch_playwright(url=URL):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="uk-UA")).new_page()
            await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            return await page.content()
        except Exception as e:
            print(f"  [fuel] playwright: {e}")
            return None
        finally:
            await browser.close()


def _get(url, parser):
    html = _fetch_urllib(url)
    data = parser(html) if html else {"date": None, "items": []}
    if not data["items"]:
        print(f"  [fuel] {url}: urllib не дав даних — пробую Playwright")
        html = asyncio.run(_fetch_playwright(url))
        if html:
            data = parser(html)
    print(f"  [fuel] {url}: дата {data['date']}, позицій {len(data['items'])}")
    return data


def main():
    print(f"=== Fuel Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")
    minfin = _get(URL, parse_minfin)
    try:
        autoria = _get(AUTORIA_URL, parse_autoria)
    except Exception as e:
        print(f"  [fuel] auto.ria: {e}")
        autoria = {"date": None, "items": []}
    data = pick_fresher(minfin, autoria)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    for i in data["items"]:
        print(f"  {i['name']:24s} {i['price']:.2f} ₴/л  ({i['delta_day']:+.2f} за день)" if i["delta_day"] is not None
              else f"  {i['name']:24s} {i['price']:.2f} ₴/л")
    print(f"  дата даних: {data['date']} · позицій: {len(data['items'])}")
    with open("fuel_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
