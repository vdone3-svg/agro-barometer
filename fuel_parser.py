"""
AGRO BAROMETER — ціни на пальне (середні по Україні на АЗС)
Джерело: index.minfin.com.ua/ua/markets/fuel/ (оновлюється в робочі дні; дані А-95 Консалтинг).
Запасний шлях: Playwright, якщо urllib заблоковано з IP GitHub.
Зберігає: fuel_data.json
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


def _fetch_urllib():
    try:
        with urlopen(Request(URL, headers=HEADERS), timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [fuel] urllib: {e}")
        return None


async def _fetch_playwright():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="uk-UA")).new_page()
            await page.goto(URL, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            return await page.content()
        except Exception as e:
            print(f"  [fuel] playwright: {e}")
            return None
        finally:
            await browser.close()


def main():
    print(f"=== Fuel Parser {datetime.now().strftime('%d.%m.%Y %H:%M')} ===")
    data = {"date": None, "items": []}
    html = _fetch_urllib()
    if html:
        data = parse_minfin(html)
    if not data["items"]:
        print("  [fuel] urllib не дав даних — пробую Playwright")
        html = asyncio.run(_fetch_playwright())
        if html:
            data = parse_minfin(html)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    for i in data["items"]:
        print(f"  {i['name']:24s} {i['price']:.2f} ₴/л  ({i['delta_day']:+.2f} за день)" if i["delta_day"] is not None
              else f"  {i['name']:24s} {i['price']:.2f} ₴/л")
    print(f"  дата даних: {data['date']} · позицій: {len(data['items'])}")
    with open("fuel_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
