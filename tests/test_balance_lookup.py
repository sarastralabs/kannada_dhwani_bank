"""Balance lookup tests."""
from __future__ import annotations

import unittest

from backend.balance_lookup import lookup_balance


class TestBalanceLookup(unittest.TestCase):
    def test_known_account(self) -> None:
        r = lookup_balance("1234567890")
        self.assertTrue(r["found"])
        self.assertAlmostEqual(r["balance_inr"], 45230.50)
        self.assertIn("ನಲವತ್ತೈದು ಸಾವಿರ", r["message_kn"])
        self.assertIn("ಐವತ್ತು ಪೈಸೆ", r["message_kn"])
        self.assertNotIn("1234567890", r["message_kn"])

    def test_unknown_account(self) -> None:
        r = lookup_balance("0000000000")
        self.assertFalse(r["found"])

    def test_short_number(self) -> None:
        r = lookup_balance("123")
        self.assertFalse(r["found"])


if __name__ == "__main__":
    unittest.main()
