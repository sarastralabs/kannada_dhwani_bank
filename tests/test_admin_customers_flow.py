"""Admin customers + conversation flow API tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class TestAdminCustomerApis(unittest.TestCase):
    def setUp(self) -> None:
        self._prev = {
            "BANK_CUSTOMER_STORE": os.environ.get("BANK_CUSTOMER_STORE"),
            "BANK_CUSTOMER_DB_PATH": os.environ.get("BANK_CUSTOMER_DB_PATH"),
        }
        import backend.db.customers as customers

        customers._demo_cache = None

    def tearDown(self) -> None:
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        import backend.db.customers as customers

        customers._demo_cache = None

    def test_list_customers_json(self) -> None:
        os.environ["BANK_CUSTOMER_STORE"] = "json"
        from backend.db.customers import list_customers

        rows = list_customers()
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(any(r["account_number"] == "1234567890" for r in rows))

    def test_list_customers_sqlite(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.environ["BANK_CUSTOMER_STORE"] = "sqlite"
            os.environ["BANK_CUSTOMER_DB_PATH"] = str(Path(tmp) / "c.db")
            from backend.db.customers import list_customers, seed_from_demo

            seed_from_demo(force=True)
            rows = list_customers()
            self.assertGreaterEqual(len(rows), 6)
            first = next(r for r in rows if r["account_number"] == "1234567890")
            self.assertEqual(first["source"], "sqlite")
            self.assertTrue(first["loans"])

    def test_conversation_flow_map(self) -> None:
        from backend.admin_flow import build_conversation_flow

        flow = build_conversation_flow()
        self.assertTrue(flow["phases"])
        intents = {row["intent"]: row for row in flow["intents"]}
        self.assertIn("check_balance", intents)
        self.assertEqual(intents["check_balance"]["form_id"], "balance_inquiry")
        self.assertTrue(intents["check_balance"]["fields"])
        self.assertEqual(intents["interest_rate_query"]["route"], "informational")
        self.assertTrue(flow["form_menu"])


if __name__ == "__main__":
    unittest.main()
