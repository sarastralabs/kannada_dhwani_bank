"""Seed production-shaped customer DB from data/demo_accounts.json.

Usage:
  set BANK_CUSTOMER_STORE=sqlite
  py -3.12 scripts/seed_customer_db.py
  py -3.12 scripts/seed_customer_db.py --force
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild customer tables from demo_accounts.json",
    )
    parser.add_argument(
        "--store",
        default=os.environ.get("BANK_CUSTOMER_STORE", "sqlite"),
        help="Customer store mode (default: sqlite)",
    )
    args = parser.parse_args()
    os.environ["BANK_CUSTOMER_STORE"] = args.store

    from backend.db.customers import init_customer_db, seed_from_demo, store_mode

    mode = init_customer_db()
    if mode != "sqlite":
        print(f"Active store={mode}. Seeding only applies to sqlite mode.")
        return 1
    result = seed_from_demo(force=args.force)
    print(f"store={store_mode()} seed={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
