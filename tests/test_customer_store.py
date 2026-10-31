"""Customer store repository tests (json + sqlite)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class TestCustomerStore(unittest.TestCase):
    def setUp(self) -> None:
        # Isolate store env for every test.
        self._prev_store = os.environ.get("BANK_CUSTOMER_STORE")
        self._prev_path = os.environ.get("BANK_CUSTOMER_DB_PATH")
        # Reset demo cache between modes.
        import backend.db.customers as customers

        customers._demo_cache = None

    def tearDown(self) -> None:
        if self._prev_store is None:
            os.environ.pop("BANK_CUSTOMER_STORE", None)
        else:
            os.environ["BANK_CUSTOMER_STORE"] = self._prev_store
        if self._prev_path is None:
            os.environ.pop("BANK_CUSTOMER_DB_PATH", None)
        else:
            os.environ["BANK_CUSTOMER_DB_PATH"] = self._prev_path
        import backend.db.customers as customers

        customers._demo_cache = None

    def test_json_lookup_matches_demo(self) -> None:
        os.environ["BANK_CUSTOMER_STORE"] = "json"
        from backend.db.customers import get_account_balance

        row = get_account_balance("1234567890")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["source"], "json")
        self.assertAlmostEqual(row["balance_inr"], 45230.50)
        self.assertEqual(row["holder_name"], "Ramesh Kumar")
        self.assertIsNone(get_account_balance("0000000000"))

    def test_sqlite_seed_and_lookup(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "customer_banking.db"
            os.environ["BANK_CUSTOMER_STORE"] = "sqlite"
            os.environ["BANK_CUSTOMER_DB_PATH"] = str(db_path)

            from backend.db.customers import (
                get_account_balance,
                init_customer_db,
                list_customer_loans,
                seed_from_demo,
                write_balance_audit,
            )

            self.assertEqual(init_customer_db(), "sqlite")
            seeded = seed_from_demo(force=True)
            self.assertEqual(seeded["accounts"], 25)
            self.assertEqual(seeded["skipped"], 0)

            row = get_account_balance("1234567890")
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["source"], "sqlite")
            self.assertAlmostEqual(row["balance_inr"], 45230.50)
            self.assertTrue(row["customer_id"])

            loans = list_customer_loans(row["customer_id"])
            self.assertEqual(len(loans), 1)
            self.assertEqual(loans[0]["loan_type"], "personal")

            write_balance_audit(
                account_number="1234567890",
                found=True,
                customer_id=row["customer_id"],
                source="test",
            )
            # Second seed without force should skip.
            again = seed_from_demo(force=False)
            self.assertEqual(again["skipped"], 1)

    def test_balance_lookup_json_unchanged(self) -> None:
        os.environ["BANK_CUSTOMER_STORE"] = "json"
        from backend.balance_lookup import lookup_balance

        ok = lookup_balance("1234567890")
        self.assertTrue(ok["found"])
        self.assertAlmostEqual(ok["balance_inr"], 45230.50)
        self.assertNotIn("1234567890", ok["message_kn"])

        bad = lookup_balance("123")
        self.assertFalse(bad["found"])


if __name__ == "__main__":
    unittest.main()
