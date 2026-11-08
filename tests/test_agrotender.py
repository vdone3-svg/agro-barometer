"""Agrotender: структура реальної сторінки ячменю 08.11.2026 (рядки скорочено до 8)."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fetch_web_prices as fw   # noqa: E402
import build_barometer as bb    # noqa: E402

HTML = (ROOT / "tests" / "fixtures" / "agrotender_yachmen_2026-11-08.html").read_text(encoding="utf-8")
URL = "https://agrotender.com.ua/traders/region_ukraine/yachmen"


def _recs(today=datetime(2026, 11, 8)):
    return [r for r in fw.parse_agrotender_table(HTML, "ячмінь", None, URL, today=today, usd_uah=45.0)
            if r["currency"] == "UAH"]


def test_usd_row_converted_not_read_as_uah():
    usd = [r for r in fw.parse_agrotender_table(HTML, "ячмінь", None, URL, today=datetime(2026, 11, 8), usd_uah=45.0)
           if r["currency"] == "USD"]
    assert len(usd) == 1 and usd[0]["price_raw"] == 148 and usd[0]["price_uah"] == 6660


def test_fresh_only_and_bn_skipped():
    prices = sorted(r["price_uah"] for r in _recs())
    assert prices == [4400, 4800, 4900, 5100, 6900]      # 7000 (03.11), 4500 (27.10) — старі; 6000 «БН» — пропуск


def test_fields():
    r = {x["price_uah"]: x for x in _recs()}
    assert r[6900]["basis"] == "CPT порт" and r[6900]["date"] == "06.11.2026" and r[6900]["buyer"] == "АГРО ФОНД"
    assert r[4800]["basis"] == "EXW самовивіз" and r[4800]["region"] == "Чернігівська" and r[4800]["pickup"]
    assert r[4900]["location"].startswith("Черкаси")


def test_build_regions_and_pickup_freight():
    recs = bb.enrich([dict(r, date=datetime.now(bb.KYIV).strftime("%d.%m.%Y")) for r in _recs()])
    by = {r["price_uah"]: r for r in recs}
    assert by[6900]["region_norm"] == "Дунай"                       # Ізмаїл → Дунай, без фрахту
    assert by[5100]["region_norm"] == "Кіровоградська"
    assert by[5100]["net_dolynske"] == 5100 and by[5100]["net_kopani"] == 5100   # самовивіз у нашій області
    assert all(r["eligible"] for r in recs)
    assert bb.best_prices(recs)["ячмінь"]["best_price"]["price_uah"] == 6900


def test_foreign_port_skipped():
    allr = fw.parse_agrotender_table(HTML, "ячмінь", None, URL, today=datetime(2026, 11, 8), usd_uah=45.0)
    assert not any("Варна" in r["location"] or r.get("buyer") == "GLOBAL GRAIN" for r in allr)
