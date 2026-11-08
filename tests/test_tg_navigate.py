"""Парсер @navigate_agro на реальному пості 02.11.2026 (t.me/navigate_agro/1949)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TG_API_ID", "1")      # модуль вимагає змінні при імпорті; мережі тест не чіпає
os.environ.setdefault("TG_API_HASH", "test")

import tg_web_parser as tg   # noqa: E402

TEXT = (ROOT / "tests" / "fixtures" / "tg_navigate_agro_2026-11-02.txt").read_text(encoding="utf-8")


def _recs():
    return tg._parse_by_role("navigate_agro", "prices", TEXT, "02.11.2026 15:45")


def test_barley_with_ship_emoji_has_location():
    b = [r for r in _recs() if r["culture"] == "ячмінь"]
    assert len(b) == 1 and b[0]["price_uah"] == 4500 and b[0]["location"] == "РЕНІ"


def test_multi_class_wheat_split():
    w = {(r["location"], r["quality"]): r["price_uah"] for r in _recs() if r["culture"] == "пшениця"}
    assert w[("ВІННИЦЯ", "2 кл")] == 6000 and w[("ВІННИЦЯ", "3 кл")] == 5300
    assert w[("САРАТА КХП", "4 кл")] == 4300


def test_bn_lines_skipped_and_empty_buyers_ignored():
    recs = _recs()
    assert not any(r["location"] in ("БАНДУРКА", "СТАРКОН") for r in recs)
    assert not any(r["price_raw"] == 445 for r in recs)       # «445$ БН» — без ПДВ, пропускаємо
