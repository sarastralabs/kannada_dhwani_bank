"""Landing-page data: the rates are turned into numbers the page can show."""

from __future__ import annotations

import json
import os

from api.routes import landing


def test_spoken_rates_become_numbers():
    assert landing.rate_percent("3 point 5 percent per annum") == 3.5
    assert landing.rate_percent("11 percent per annum") == 11.0
    assert landing.rate_percent("7 point 25 percent per annum") == 7.25
    assert landing.rate_percent("8 point 5 percent per annum, floating rate") == 8.5
    assert landing.rate_percent("") is None and landing.rate_percent("no number here") is None


def test_every_real_rate_is_understood_and_floating_is_flagged():
    path = os.path.join(landing.PROJECT_ROOT, "data", "bank_info.json")
    with open(path, encoding="utf-8") as f:
        rates = json.load(f)["interest_rates"]
    table = landing.rates_table(rates)
    assert set(table) == set(rates)  # nothing silently dropped
    assert table["home_loan"] == {"percent": 8.5, "floating": True}
    assert table["savings_account"] == {"percent": 3.5, "floating": False}
    assert all(0 < row["percent"] < 30 for row in table.values())
