"""Test date extraction fix."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from datetime import datetime
from backend.forms.extract import _extract_date

tests = [
    # Exact failing inputs from logs
    ('twenty one six two thousand five',     '21/06/2005'),
    ('Twenty one six two thousand five.',    '21/06/2005'),
    ('twenty one six two thousand five',     '21/06/2005'),
    # Already-digit formats — must still work
    ('21/06/2005',                          '21/06/2005'),
    ('21-06-2005',                          '21/06/2005'),
    # Other common word patterns
    ('twenty five twelve nineteen ninety five', '25/12/1995'),
    ('fifteen eight two thousand ten',      '15/08/2010'),
    ('one one two thousand',                '01/01/2000'),
    ('seven three nineteen eighty',         '07/03/1980'),
    # Edge cases
    ('today',   datetime.now().strftime('%d/%m/%Y')),
]

passed = 0
failed = 0
for inp, expected in tests:
    result = _extract_date(inp)
    ok = result == expected
    if ok: passed += 1
    else: failed += 1
    print(f'  [{"PASS" if ok else "FAIL"}] "{inp[:50]}" -> {result}  (expected {expected})')

print(f'\n{"ALL PASS" if failed == 0 else f"{failed} FAILED"} — {passed} passed')
sys.exit(1 if failed else 0)
