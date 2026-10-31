"""Test last-4-digits account lookup feature."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
os.environ.setdefault('HF_HUB_OFFLINE', '1')

passed = 0
failed = 0

def chk(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
        print(f'  [PASS] {name}' + (f'  {detail}' if detail else ''))
    else:
        failed += 1
        print(f'  [FAIL] {name}' + (f'  {detail}' if detail else ''))

# ── 1. customers.py get_account_by_last4 ──────────────────────────────────────
print('\n── customers.py: get_account_by_last4 ──')
from backend.db.customers import get_account_by_last4

# Demo account 1234567890 ends in 7890
r1 = get_account_by_last4('7890')
chk('last4 7890 finds 1234567890', len(r1) == 1 and r1[0]['account_number'] == '1234567890',
    str([r['account_number'] for r in r1]))
chk('last4 result has balance_inr', r1[0]['balance_inr'] == 45230.50 if r1 else False,
    str(r1[0].get('balance_inr')) if r1 else 'no result')
chk('last4 result has holder_name', bool(r1[0].get('holder_name')) if r1 else False)

# Unknown last4
r2 = get_account_by_last4('0000')
chk('last4 0000 returns empty list', r2 == [])

# Invalid input
r3 = get_account_by_last4('123')    # too short
chk('last4 3 digits returns empty', r3 == [])
r4 = get_account_by_last4('12345')  # too long
chk('last4 5 digits returns empty', r4 == [])
r5 = get_account_by_last4('')
chk('last4 empty returns empty', r5 == [])

# ── 2. balance_lookup.py ──────────────────────────────────────────────────────
print('\n── balance_lookup.py ──')
from backend.balance_lookup import lookup_balance

# Last 4 digits — happy path
b1 = lookup_balance('7890')
chk('lookup last4 7890 found=True', b1['found'] is True, str(b1.get('balance_inr')))
chk('lookup last4 returns correct account', b1.get('account_number') == '1234567890')
chk('lookup last4 balance correct', b1.get('balance_inr') == 45230.50)
chk('lookup last4 message_kn has Kannada balance', 'ಶಿಲ್ಕು' in b1.get('message_kn', ''))
chk('lookup last4 message_en has balance', '45,230' in b1.get('message_en', ''))

# Last 4 digits — not found
b2 = lookup_balance('0000')
chk('lookup last4 0000 found=False', b2['found'] is False)
chk('lookup last4 not found message_kn present', bool(b2.get('message_kn')))
chk('lookup last4 not found message_kn is Kannada', 'ಖಾತೆ' in b2.get('message_kn', ''))

# Full 10-digit still works
b3 = lookup_balance('1234567890')
chk('lookup full 10-digit still works', b3['found'] is True)
chk('lookup full 10-digit balance correct', b3.get('balance_inr') == 45230.50)

# Wrong length (not 4, 6, or 10)
b4 = lookup_balance('12345')
chk('lookup 5 digits returns found=False', b4['found'] is False)
chk('lookup 5 digits message mentions last 4', 'ನಾಲ್ಕು' in b4.get('message_kn', ''))

# Empty
b5 = lookup_balance('')
chk('lookup empty returns found=False', b5['found'] is False)

# ── 3. bank_info.json prompts updated ─────────────────────────────────────────
print('\n── bank_info.json prompts ──')
import json
with open('data/bank_info.json', encoding='utf-8') as f:
    bi = json.load(f)

chk('check_balance_note mentions last 4',
    'last 4' in bi.get('check_balance_note', '').lower() or
    '4' in bi.get('check_balance_note', ''),
    bi.get('check_balance_note', ''))
chk('check_balance_note_kn mentions ನಾಲ್ಕು',
    'ನಾಲ್ಕು' in bi.get('check_balance_note_kn', ''),
    bi.get('check_balance_note_kn', ''))

# ── 4. forms.json balance_inquiry prompt updated ──────────────────────────────
print('\n── forms.json balance_inquiry ──')
with open('data/forms.json', encoding='utf-8') as f:
    fd = json.load(f)

balance_form = next((f for f in fd['forms'] if f['id'] == 'balance_inquiry'), None)
chk('balance_inquiry form exists', balance_form is not None)
if balance_form:
    field = balance_form['fields'][0]
    chk('field prompt_kn mentions ನಾಲ್ಕು (4)',
        'ನಾಲ್ಕು' in field.get('prompt_kn', ''),
        field.get('prompt_kn', ''))
    chk('field label_kn mentions last 4',
        'ನಾಲ್ಕು' in field.get('label_kn', '') or '4' in field.get('label_kn', ''),
        field.get('label_kn', ''))

# ── 5. router check_balance response updated ──────────────────────────────────
print('\n── router check_balance response ──')
from backend.decision_router.router import route

r = route('check_balance')
chk('router check_balance en mentions last 4',
    'last 4' in r['response_text'].lower(),
    r['response_text'])
chk('router check_balance kn mentions ನಾಲ್ಕು',
    'ನಾಲ್ಕು' in r.get('response_text_kn', ''),
    r.get('response_text_kn', ''))

# ── 6. validation.py accepts 4 digits ─────────────────────────────────────────
print('\n── validation.py accepts 4/6/10 digits ──')
from backend.forms.validation import validate_captured_value

chk('4 digits accepted for account_number',
    validate_captured_value('7890', field_type='digits', field_id='account_number') is None)
chk('6 digits accepted for account_number',
    validate_captured_value('567890', field_type='digits', field_id='account_number') is None)
chk('10 digits accepted for account_number',
    validate_captured_value('1234567890', field_type='digits', field_id='account_number') is None)
chk('5 digits rejected for account_number',
    validate_captured_value('12345', field_type='digits', field_id='account_number') is not None)
chk('3 digits rejected for account_number',
    validate_captured_value('123', field_type='digits', field_id='account_number') is not None)
chk('ACCOUNT_RETRY_KN mentions last 4',
    'ನಾಲ್ಕು' in (validate_captured_value('12345', field_type='digits', field_id='account_number') or ''))

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*55}')
if failed == 0:
    print(f'  ALL PASS — {passed} tests passed')
else:
    print(f'  {failed} FAILURE(S) — {passed} passed, {failed} failed')
print(f'{"="*55}')
sys.exit(1 if failed else 0)
