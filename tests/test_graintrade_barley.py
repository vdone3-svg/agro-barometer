"""Тести парсера GrainTrade (ячмінь) і обробки «орієнтиру» в build_barometer.
Фікстура — реальна таблиця статті від 06.11.2026 (збережена 08.11.2026).
Запуск: python -m pytest tests -q   (лише в CI / хмарі; на iMac Python не встановлений)
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fetch_web_prices as fw          # noqa: E402
import build_barometer as bb           # noqa: E402

FIX = ROOT / "tests" / "fixtures"
URL = "https://graintrade.com.ua/novosti/zakupivelni-tcini-na-zerno-v-ukraini-na-6-listopada-2026-roku.html"


def _recs():
    html = (FIX / "graintrade_2026-11-06.html").read_text(encoding="utf-8")
    return fw.parse_graintrade_table(html, "06.11.2026", URL)


def _find(recs, culture, basis, quality=None):
    return [r for r in recs if r["culture"] == culture and r["basis"] == basis and r.get("quality") == quality]


def test_barley_cpt_terminal_found():
    recs = _recs()
    b = _find(recs, "ячмінь", "CPT термінал")
    assert len(b) == 1 and b[0]["price_uah"] == 7150


def test_malting_barley_separate_quality():
    recs = _recs()
    assert _find(recs, "ячмінь", "CPT переробник", "пивоварений")[0]["price_uah"] == 6500
    assert _find(recs, "ячмінь", "FCA", "пивоварений")[0]["price_uah"] == 5500


def test_delta_arrows_not_glued_to_price():
    recs = _recs()
    assert _find(recs, "пшениця", "CPT термінал", "2 клас")[0]["price_uah"] == 8353   # не 8353149
    assert _find(recs, "кукурудза", "FCA")[0]["price_uah"] == 4800


def test_only_uah_columns_and_no_byproducts():
    recs = _recs()
    assert all(r["basis"] in {"CPT термінал", "EXW елеватор", "CPT переробник", "FCA"} for r in recs)
    assert all(r["price_uah"] >= 3000 for r in recs)               # $-стовпці (125, 430…) не потрапили
    names = {(r["culture"], r.get("quality")) for r in recs}
    assert not any("олі" in str(q) or "шрот" in str(q) or "макух" in str(q) for _, q in names)
    # «Соєва олія», «Макуха соняшникова», «Олія соняшникова» не стали соєю/соняшником
    assert _find(recs, "соя", "CPT термінал")[0]["price_uah"] == 17000
    assert len([r for r in recs if r["culture"] == "соняшник"]) == 4   # 15263, 15267 + вис.ол. 17000, 18500


def test_sidebar_table_ignored():
    recs = _recs()
    assert not any(r["price_uah"] == 6113 for r in recs)


def test_records_are_reference_without_net():
    for r in _recs():
        assert r["ref_kind"] == "national_avg"
        assert r["net_kopani"] is None and r["net_dolynske"] is None
        assert r["date"] == "06.11.2026"


def test_article_links_from_listing():
    html = (FIX / "graintrade_novosti_links.html").read_text(encoding="utf-8")
    links = fw._gt_article_links(html)
    assert [u for u, _ in links] == [
        URL,
        "https://graintrade.com.ua/novosti/zakupivelni-tcini-na-zerno-v-ukraini-na-5-listopada-2026-roku.html",
    ]
    assert links[0][1] == datetime(2026, 11, 6)


def test_guessed_url_format_matches_site():
    urls = [u for u, _ in fw._gt_guess_urls(datetime(2026, 11, 8), days=3)]
    assert URL in urls          # день без нуля, «listopada»


def test_build_reference_not_eligible_but_shown():
    recs = bb.enrich([dict(r, date=datetime.now().strftime("%d.%m.%Y")) for r in _recs()])
    assert all(not r["eligible"] and "орієнтир" in r["excluded_reason"] for r in recs)
    prices = bb.best_prices(recs)
    barley = prices["ячмінь"]
    assert barley["best_price"] is None and barley["eligible_count"] == 0
    assert [r["price_uah"] for r in barley["reference"]] == [7150, 6500, 5500]
    # високоолеїновий соняшник не потрапляє в орієнтир звичайного соняшнику
    assert [r["price_uah"] for r in prices["соняшник"]["reference"]] == [15267, 15263]


def test_reference_does_not_displace_real_offer():
    offer = {"source": "nibulon.com", "culture": "пшениця", "quality": "2 кл", "price_uah": 8000.0,
             "price_raw": 8000.0, "currency": "UAH", "basis": "з ПДВ", "location": "Глобинська",
             "region": "Полтавська", "date": datetime.now().strftime("%d.%m.%Y")}
    recs = bb.enrich([offer] + [dict(r, date=offer["date"]) for r in _recs()])
    w = bb.best_prices(recs)["пшениця"]
    assert w["best_price"]["price_uah"] == 8000 and w["eligible_count"] == 1
    assert w["reference"][0]["price_uah"] == 8353
