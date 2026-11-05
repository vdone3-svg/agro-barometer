"""
AGRO BAROMETER — Земельний парсер
Канали: @landinvestua, @dobrozem_offers, @kupipai
Регіон: Кіровоградська область
Збирає: купівля паїв, орендна плата, нові лоти
"""

import re, json, asyncio, os
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

# Ті самі секрети, що й tg_web_parser.py (TG_*); старі назви TELEGRAM_* — як запасні
SESSION  = os.environ.get("TG_SESSION") or os.environ.get("TELEGRAM_SESSION") or ""
API_ID   = int(os.environ.get("TG_API_ID") or os.environ.get("TELEGRAM_API_ID") or "30430309")
API_HASH = os.environ.get("TG_API_HASH") or os.environ.get("TELEGRAM_API_HASH") or "4360b5aa9c5cf78aff7f3ba2d9c661fc"

LAND_CHANNELS = ["landinvestua", "dobrozem_offers", "kupipai"]

# Ключові слова для Кіровоградської обл.
KIRO_KW = [
    "кіровоградська", "кіровоград", "кировоград",
    "олександрійськ", "олександрі",
    "знам'янськ", "знам'янк", "знамянськ",
    "онуфріївськ", "новгородківськ", "бобринецьк",
    "світловодськ", "гайворонськ", "добровеличківськ",
    "кропивниц", "кропівниц",
    "3522",  # код кадастрового номера Кіровоградської обл.
    "3521", "3523", "3524", "3525",  # коди районів
]

# Патерни для витягування даних
PRICE_HA_RE = re.compile(
    r"(\d[\d\s']{3,8}\d)\s*(?:грн/га|грн\.\/га|\((\d[\d\s']+\d)\s*грн/га\))",
    re.IGNORECASE
)
PRICE_TOTAL_RE = re.compile(
    r"(?:вартість|ціна|ціна за ділянку)[^\d]*(\d[\d\s']{4,9}\d)\s*грн",
    re.IGNORECASE
)
RENT_RE = re.compile(
    r"(?:орендна плата|оренда|орендна)[^\d]*(\d[\d\s']{3,7}\d)\s*грн",
    re.IGNORECASE
)
YIELD_RE = re.compile(
    r"(?:дохідність|доходність)[^\d]*(\d+[.,]\d+)\s*%",
    re.IGNORECASE
)
SIZE_RE = re.compile(
    r"(\d+[.,]\d+)\s*(?:га|гектар)",
    re.IGNORECASE
)
DISTRICT_RE = re.compile(
    r"(?:Кіровоградська|Кіровоград)[^,\n]*,\s*([^\n,]+(?:район|р-н)[^\n,]*)",
    re.IGNORECASE
)
CADASTRAL_RE = re.compile(r"\b(\d{10}:\d{2}:\d{3}:\d{4})\b")
RENTER_RE = re.compile(
    r"(?:орендар|орендує)[^\n:]*[:\s]+([^\n]{5,60})",
    re.IGNORECASE
)


def is_kirovohrad(text):
    """Перевіряє чи повідомлення стосується Кіровоградської обл."""
    t = text.lower()
    return any(kw in t for kw in KIRO_KW)


def parse_land_message(text, channel, msg_date):
    """Парсить повідомлення про земельний лот."""
    if not text or not is_kirovohrad(text):
        return None

    date_str = msg_date.strftime("%d.%m.%Y %H:%M")

    # Визначаємо тип лоту
    t_lower = text.lower()
    if any(kw in t_lower for kw in ["продаж", "продам", "вартість", "ціна за ділянку", "купити"]):
        lot_type = "продаж"
    elif any(kw in t_lower for kw in ["оренда", "орендна плата", "орендар"]):
        lot_type = "оренда"
    else:
        lot_type = "невідомо"

    # Витягуємо дані
    record = {
        "source":     f"@{channel}",
        "type":       lot_type,
        "date":       date_str,
        "region":     "Кіровоградська обл.",
        "district":   "",
        "size_ha":    None,
        "price_total": None,
        "price_per_ha": None,
        "rent_per_lot": None,
        "rent_per_ha":  None,
        "yield_pct":  None,
        "renter":     "",
        "cadastral":  "",
        "raw":        text[:500],
    }

    # Район
    m = DISTRICT_RE.search(text)
    if m:
        record["district"] = m.group(1).strip()
    else:
        # Спрощений пошук назви района
        for kw in ["Олександрійський", "Знам'янський", "Онуфріївський",
                   "Новгородківський", "Бобринецький", "Гайворонський",
                   "Добровеличківський", "Світловодський", "Кіровоградський",
                   "Голованівський"]:
            if kw.lower() in t_lower:
                record["district"] = kw
                break

    # Площа
    m = SIZE_RE.search(text)
    if m:
        record["size_ha"] = float(m.group(1).replace(",", "."))

    # Ціна за ділянку
    m = PRICE_TOTAL_RE.search(text)
    if m:
        val = float(m.group(1).replace(" ", "").replace("'", ""))
        record["price_total"] = val

    # Ціна за га — з дужок типу "(126 709 грн/га)"
    m = re.search(r"\((\d[\d\s']+\d)\s*грн/га\)", text, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(" ", "").replace("'", ""))
        record["price_per_ha"] = val
    elif record["price_total"] and record["size_ha"]:
        record["price_per_ha"] = round(record["price_total"] / record["size_ha"])

    # Орендна плата
    m = RENT_RE.search(text)
    if m:
        val = float(m.group(1).replace(" ", "").replace("'", ""))
        if 1000 <= val <= 200000:
            record["rent_per_lot"] = val
            if record["size_ha"]:
                record["rent_per_ha"] = round(val / record["size_ha"])

    # Дохідність
    m = YIELD_RE.search(text)
    if m:
        record["yield_pct"] = float(m.group(1).replace(",", "."))

    # Орендар
    m = RENTER_RE.search(text)
    if m:
        record["renter"] = m.group(1).strip().strip('"').strip("'")

    # Кадастровий номер
    m = CADASTRAL_RE.search(text)
    if m:
        record["cadastral"] = m.group(1)

    return record


def format_land_summary(records):
    """Формує резюме для щоденного огляду."""
    if not records:
        return "Нових лотів по Кіровоградській обл. немає."

    sales = [r for r in records if r["type"] == "продаж"]
    rents = [r for r in records if r["type"] == "оренда"]
    unknown = [r for r in records if r["type"] == "невідомо"]

    lines = [f"🏡 ЗЕМЛЯ — Кіровоградська обл. ({len(records)} лотів за 24 год)\n"]

    if sales:
        lines.append(f"📋 КУПІВЛЯ/ПРОДАЖ ({len(sales)} лотів):")
        prices_ha = [r["price_per_ha"] for r in sales if r["price_per_ha"]]
        yields = [r["yield_pct"] for r in sales if r["yield_pct"]]
        if prices_ha:
            lines.append(f"   Ціна: {min(prices_ha):,.0f}–{max(prices_ha):,.0f} грн/га "
                        f"(середня {sum(prices_ha)/len(prices_ha):,.0f} грн/га)")
        if yields:
            lines.append(f"   Дохідність: {min(yields):.1f}–{max(yields):.1f}%")

        for r in sales:
            flag = "🔥 " if (r.get("yield_pct") or 0) >= 5.0 else ""
            price_str = f"{r['price_per_ha']:,.0f} грн/га" if r["price_per_ha"] else "ціна невідома"
            yield_str = f" | {r['yield_pct']:.1f}%" if r["yield_pct"] else ""
            size_str = f"{r['size_ha']:.2f} га" if r["size_ha"] else "? га"
            district = r["district"] or "район невідомий"
            rent_str = f" | оренда {r['rent_per_lot']:,.0f} грн/пай" if r.get("rent_per_lot") else ""
            renter_str = f" | {r['renter'][:30]}" if r.get("renter") else ""
            lines.append(f"   {flag}{district}, {size_str}: {price_str}{yield_str}{rent_str}{renter_str} [{r['source']}]")

    if rents:
        lines.append(f"\n📋 ОРЕНДА ({len(rents)} лотів):")
        rents_ha = [r["rent_per_ha"] for r in rents if r["rent_per_ha"]]
        if rents_ha:
            lines.append(f"   Орендна плата: {min(rents_ha):,.0f}–{max(rents_ha):,.0f} грн/га/рік")

        for r in rents:
            rent_str = (f"{r['rent_per_lot']:,.0f} грн/пай "
                       f"({r['rent_per_ha']:,.0f} грн/га)" if r.get("rent_per_lot") else "сума невідома")
            size_str = f"{r['size_ha']:.2f} га" if r["size_ha"] else "? га"
            district = r["district"] or "район невідомий"
            renter_str = f" | {r['renter'][:30]}" if r.get("renter") else ""
            lines.append(f"   {district}, {size_str}: {rent_str}{renter_str} [{r['source']}]")

    if unknown:
        lines.append(f"\n📋 ІНШЕ ({len(unknown)} оголошень):")
        for r in unknown:
            lines.append(f"   {r['district'] or '?'} | {r['source']} | {r['date']}")

    return "\n".join(lines)


async def main():
    print(f"=== AGRO BAROMETER Земельний парсер ===")
    print(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Регіон: Кіровоградська обл.")
    print()

    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    all_records = []

    if not SESSION:
        print("  ⚠️ TG_SESSION не задано — пропускаємо земельний парсер")
        return
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH,
                            system_version="4.16.30-vxCUSTOM")
    await client.connect()
    if not await client.is_user_authorized():
        print("  ❌ сесія недійсна — пропускаємо")
        await client.disconnect()
        return
    try:
      for ch in LAND_CHANNELS:
            try:
                found = 0
                total = 0
                async for msg in client.iter_messages(ch, limit=100):
                    if msg.date < cutoff:
                        break
                    if not msg.text:
                        continue
                    total += 1
                    record = parse_land_message(msg.text, ch, msg.date)
                    if record:
                        all_records.append(record)
                        found += 1

                print(f"  ✅ @{ch}: {total} повід., {found} лотів по Кіровоградщині")

            except Exception as e:
                print(f"  ❌ @{ch}: {e}")
    finally:
        await client.disconnect()

    print(f"\nВсього лотів: {len(all_records)}")
    print()
    print(format_land_summary(all_records))
    print()

    # Статистика
    sales = [r for r in all_records if r["type"] == "продаж"]
    if sales:
        prices = [r["price_per_ha"] for r in sales if r["price_per_ha"]]
        rents = [r["rent_per_lot"] for r in sales if r.get("rent_per_lot")]
        yields = [r["yield_pct"] for r in sales if r["yield_pct"]]
        print("📊 СТАТИСТИКА (продаж):")
        if prices:
            print(f"   Ціна/га: середня {sum(prices)/len(prices):,.0f} грн | "
                  f"мін {min(prices):,.0f} | макс {max(prices):,.0f}")
        if rents:
            print(f"   Оренда/пай: середня {sum(rents)/len(rents):,.0f} грн | "
                  f"мін {min(rents):,.0f} | макс {max(rents):,.0f}")
        if yields:
            print(f"   Дохідність: середня {sum(yields)/len(yields):.1f}% | "
                  f"макс {max(yields):.1f}%")

    # Збереження
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": "Кіровоградська обл.",
        "records_total": len(all_records),
        "summary_text": format_land_summary(all_records),
        "records": all_records,
    }

    out_path = "land_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nЗбережено: {out_path}")


asyncio.run(main())
