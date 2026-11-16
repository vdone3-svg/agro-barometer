"""Вимоги власника 16.11.2026: висновок без оферт/дзвінків, фрахт туди-назад, пальне у вихідні,
живі добрива, без @zakaz_agro у новинах."""
import datetime as dt
import pathlib

import build_barometer as bb
import crop_summaries as cs
import fert_parser as fp
import fuel_parser as fu
import news_parser as npr

AUTORIA = '''<html><body><p>Інформація оновлена 2026-11-14</p><table>
<tr><th>Пальне</th><th>Ціна, грн/л</th><th>Динаміка</th></tr><tr><td>A-100</td><td>-</td><td></td></tr>
<tr><td>A-95+</td><td>91.12</td><td></td></tr><tr><td>A-95</td><td>88.03</td><td></td></tr>
<tr><td>A-92</td><td>84.58</td><td></td></tr><tr><td>ДП</td><td>103.22</td><td>-0.02</td></tr><tr><td>Газ</td><td>61.86</td><td></td></tr>
</table><table><tr><td>Кіровоградська</td><td>-</td><td>90.90</td></tr></table></body></html>'''


def test_freight_round_trip():
    for farm, regs in bb.FREIGHT_ONE_WAY.items():
        for reg, v in regs.items():
            assert bb.FREIGHT[farm][reg] == 2 * v
    r = bb.enrich([{"source": "x", "culture": "пшениця", "price_uah": 8000, "location": "Одеса", "date": "16.11.2026"}])[0]
    assert r["net_dolynske"] == 8000 - 2 * bb.FREIGHT_ONE_WAY["Долинське"]["Одеська"]


def test_autoria_parse_and_pick_fresher():
    a = fu.parse_autoria(AUTORIA)
    assert a["date"] == "14.11.2026"
    assert {i["key"]: i["price"] for i in a["items"]} == {"дизель": 103.22, "а95": 88.03, "а95п": 91.12, "газ": 61.86}
    m = fu.parse_minfin(pathlib.Path("tests/fixtures/minfin_fuel_2026-11-06.html").read_text(encoding="utf-8"))
    assert fu.pick_fresher(m, a)["date"] == "14.11.2026"          # вихідні: auto.ria новіша
    m["date"] = "14.11.2026"
    assert fu.pick_fresher(m, a)["source_used"] == "index.minfin.com.ua"   # рівні дати — першоджерело
    assert fu.pick_fresher({"date": None, "items": []}, {"date": None, "items": []})["items"] == []


def test_fert_parsers():
    g = '''<p>Прайс опт від 16.11.2026</p><table><tr><th>Найменування</th><th>Виробник</th><th>с. Хацьки</th><th>м. Полтава</th></tr>
    <tr><td>КАС-32</td><td>Україна</td><td>26 200</td><td>26 900</td></tr>
    <tr><td>Аміачна селітра</td><td>Україна</td><td>уточнюється</td><td>уточнюється</td></tr></table>
    <p>Карбамід (порт Чорноморськ) – 31 000 грн/т</p>
    <table><tr><th>Найменування</th><th>Пакування</th><th>Виробник</th><th>Ціна</th></tr><tr><td>Карбамід</td><td>1,5 кг</td><td>Україна</td><td>196</td></tr></table>'''
    r = fp.parse_grossdorf(g)
    assert sorted((x["base"], x["price"]) for x in r) == [("карбамід", 31000), ("кас", 26200), ("кас", 26900)]
    assert all(x["date"] == "16.11.2026" for x in r)
    t = ("A Ціни на 12.11.2026 Карбамід( N:46 )31 500 Україна / OSTCHEM Черкаська обл.Черкаси "
         "B Ціни на 01.08.2026 Амофос( N:11 P:52 )57 300 Болгарія "          # застаріла — відкидається
         "C Ціни на сьогодні Нітроамофоска( N:15 P:15 K:15 )36 000 Греція "   # без дати — відкидається
         "D Ціни на 04.11.2026 Діамофоска( N:9 P:25 K:25 )46 200 Болгарія Ціни на 04.11.2026 Діамофос( N:18 P:46 )57 200")
    e = fp.parse_ezerno_text(t, today=dt.date(2026, 11, 16))
    assert sorted(x["key"] for x in e) == ["діамофос:18:46", "діамофоска:9:25:25", "карбамід"]
    agg = {a["key"]: a for a in fp.aggregate(r + e)}
    assert agg["карбамід"]["min"] == 31000 and agg["карбамід"]["max"] == 31500 and agg["карбамід"]["n"] == 2


def test_news_exclude_zakaz_agro():
    assert npr.news_excluded({"source": "@zakaz_agro", "url": "https://t.me/zakaz_agro/123"})
    assert npr.news_excluded({"source": "x", "url": "https://t.me/zakaz_agro/5"})
    assert not npr.news_excluded({"source": "@elevatorist", "url": "https://t.me/elevatorist/1"})


def test_summary_context_has_no_offers_or_buyers():
    d = {"best_price": {"price_uah": 8000, "location": "Ізмаїл", "source": "@x"}, "price_median": 7600,
         "price_min": 7000, "price_max": 8000, "eligible_count": 9, "records_count": 12,
         "best_net": {"Долинське": {"net_dolynske": 5000, "price_uah": 8000, "location": "Ізмаїл"}}, "top": [], "reference": []}
    ctx, allowed = cs.build_context("пшениця", d, {"med_delta_7": -25}, [], 43.9, "16.11.2026")
    blob = str(ctx)
    for bad in ("найвища_ціна", "найкраща_чиста_виручка", "мін_ціни_для_торгу", "місцеві_покупці", "топ_пропозицій", "Ізмаїл"):
        assert bad not in blob
    assert ctx["рівень_ринку"]["медіана_₴/т"] == 7600 and 7600 in allowed
    for bad in ("кому подзвонити", "Що робити: першим ділом подзвонити"):
        assert bad not in cs.SYSTEM
    s = cs._parse('{"verdict":"hold","label":"Тримати","paragraphs":["a b c.","d e f."],"todo":"Що робити: тримати"}')
    assert s["todo"] == "Висновок: тримати"


def test_logistics_panel_removed():
    t = pathlib.Path("barometer_template.html").read_text(encoding="utf-8")
    assert "Автомобільний фрахт" not in t and 'class="logistics-panel"' not in t
    assert 'id="fertPanel"' in t
