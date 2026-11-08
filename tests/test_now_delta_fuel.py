"""Тести: барометр «на зараз», трекер дельт, пальне (minfin), свіжість ≤2 дні.
Запуск: python -m pytest tests -q
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_barometer as bb   # noqa: E402
import fuel_parser as fp       # noqa: E402

FIX = ROOT / "tests" / "fixtures"
KYIV = bb.KYIV


def _d(days_ago):
    return (datetime.now(KYIV) - timedelta(days=days_ago)).strftime("%d.%m.%Y")


def _offer(c, p, region, days_ago=0, **kw):
    r = {"source": "@navigate_agro", "culture": c, "quality": None, "price_uah": float(p), "price_raw": float(p),
         "currency": "UAH", "basis": "CPT", "location": region, "region": region, "date": _d(days_ago)}
    r.update(kw)
    return r


def _ref(c, p, basis="CPT термінал", days_ago=1):
    return {"source": "graintrade.com.ua", "culture": c, "quality": None, "price_uah": float(p), "price_raw": float(p),
            "currency": "UAH", "basis": basis, "location": "Середня по Україні (GrainTrade) · " + basis,
            "region": "Україна", "date": _d(days_ago), "ref_kind": "national_avg"}


def _snap(days_ago, med, best=None, fuel=None):
    s = {"date": _d(days_ago), "prices": {"ячмінь": {"uah": best or med + 100, "src": "x", "med": med, "n": 3}}}
    if fuel:
        s["fuel"] = fuel
    return s


# ── свіжість ────────────────────────────────────────────────────────────────

def test_offer_older_than_two_days_excluded():
    ok, why = bb.classify(bb.enrich([_offer("ячмінь", 7000, "Одеська", days_ago=3)])[0])
    assert not ok and "застаріла" in why
    assert bb.enrich([_offer("ячмінь", 7000, "Одеська", days_ago=2)])[0]["eligible"]


def test_reference_older_than_three_days_dropped():
    recs = bb.enrich([_ref("ячмінь", 7150, days_ago=4), _offer("ячмінь", 7000, "Одеська")])
    assert bb.best_prices(recs)["ячмінь"]["reference"] == []


# ── барометр «на зараз» ─────────────────────────────────────────────────────

def _prices():
    recs = bb.enrich([_offer("ячмінь", 7300, "Одеська"), _offer("ячмінь", 7000, "Миколаївська"),
                      _offer("ячмінь", 6900, "Кіровоградська"), _ref("ячмінь", 7150)])
    return bb.best_prices(recs)


def test_median_computed():
    assert _prices()["ячмінь"]["price_median"] == 7000


def test_now_score_all_three_signals_math():
    snaps = [_snap(k, m) for k, m in [(8, 7050), (7, 7100), (6, 7000), (5, 6950), (3, 7150), (1, 7200)]]
    n = bb.now_score("ячмінь", _prices()["ячмінь"], snaps)
    s = n["signals"]
    assert s["premium"]["score"] == 71           # 7300 vs 7150 = +2,1% → 50+21
    assert s["move"]["score"] == 78              # 7000 vs 7200 = −2,8% → 50+28
    assert s["range"]["score"] == 20             # (7000−6950)/(7200−6950)
    assert n["score"] == round((71 * 40 + 78 * 30 + 20 * 30) / 100) == 58
    assert n["n_signals"] == 3 and n["reliability"] == "повна"


def test_now_score_single_signal_low_reliability():
    n = bb.now_score("ячмінь", _prices()["ячмінь"], [])     # лише premium
    assert n["score"] == 71 and n["n_signals"] == 1 and n["reliability"] == "низька"


def test_now_score_no_signals_no_score():
    recs = bb.enrich([_offer("ячмінь", 7000, "Одеська")])  # без орієнтиру й історії
    n = bb.now_score("ячмінь", bb.best_prices(recs)["ячмінь"], [])
    assert n["score"] is None and n["n_signals"] == 0 and "бракує" in n["why_none"]


def test_now_score_no_offers():
    recs = bb.enrich([_ref("ячмінь", 7150)])
    n = bb.now_score("ячмінь", bb.best_prices(recs)["ячмінь"], [])
    assert n["score"] is None and "немає порівнюваних" in n["why_none"]


def test_now_score_clamped():
    snaps = [_snap(1, 3500)]                              # медіана подвоїлась → move = 0, не від'ємне
    n = bb.now_score("ячмінь", _prices()["ячмінь"], snaps)
    assert 0 <= n["signals"]["move"]["score"] <= 100 and n["signals"]["move"]["score"] == 0


# ── дельти ──────────────────────────────────────────────────────────────────

def test_deltas_day_week_and_missing_month():
    snaps = [_snap(1, 7200, best=7250), _snap(7, 7100, best=7400)]
    dl = bb.compute_deltas(_prices(), snaps, _d(0))["ячмінь"]
    assert dl["delta_1"] == 7300 - 7250 and dl["med_delta_1"] == -200
    assert dl["delta_7"] == -100 and dl["med_delta_7"] == -100
    assert dl["delta_30"] is None and dl["med_delta_30"] is None


def test_delta_day_skips_weekend_gap_and_today():
    snaps = [_snap(3, 6900), _snap(0, 9999)]             # сьогоднішній знімок не порівнюється сам із собою
    dl = bb.compute_deltas(_prices(), snaps, _d(0))["ячмінь"]
    assert dl["med_delta_1"] == 100 and dl["prev_date_1"] == _d(3)


def test_old_snapshots_without_median_dont_crash():
    snaps = [{"date": _d(1), "prices": {"ячмінь": {"uah": 7000.0, "src": "x"}}}]
    dl = bb.compute_deltas(_prices(), snaps, _d(0))["ячмінь"]
    assert dl["delta_1"] == 300 and dl["med_delta_1"] is None


def test_snapshot_contains_median_and_fuel():
    fuel = {"date": "06.11.2026", "items": [{"key": "дизель", "price": 104.57}]}
    s = bb._snapshot_from_prices(_prices(), _d(0), fuel)
    assert s["prices"]["ячмінь"]["med"] == 7000 and s["fuel"] == {"дизель": 104.57}


# ── пальне ──────────────────────────────────────────────────────────────────

def test_minfin_parse():
    d = fp.parse_minfin((FIX / "minfin_fuel_2026-11-06.html").read_text(encoding="utf-8"))
    assert d["date"] == "06.11.2026"
    by = {i["key"]: i for i in d["items"]}
    assert by["дизель"]["price"] == 104.57 and by["дизель"]["delta_day"] == -0.07
    assert by["а95"]["price"] == 89.57 and by["а95п"]["price"] == 93.37 and by["газ"]["price"] == 59.93
    assert [i["key"] for i in d["items"]] == ["дизель", "а95", "а95п", "газ"]   # А-92 не показуємо


def test_fuel_week_delta_from_history():
    fuel = {"items": [{"key": "дизель", "name": "Дизель", "price": 104.57}]}
    rows = bb.fuel_deltas(fuel, [{"date": _d(7), "prices": {}, "fuel": {"дизель": 103.9}}])
    assert rows[0]["delta_7"] == 0.67 and rows[0]["delta_30"] is None
