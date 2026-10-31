"""Test form routing fix — informational queries should not open forms."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

from backend.forms.form_menu import match_form_from_speech

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

print('\n-- Informational queries should NOT open forms --')
no_match_cases = [
    ('block atm card',       'block atm card'),
    ('atm card block maadi', ''),
    ('atm card khali maadi', 'how to block atm card'),
    ('loan interest rate',   'what is loan interest rate'),
    ('fd rate eshtu',        'what is fixed deposit rate'),
    ('pin change madabeku',  'how to change pin'),
    ('how to transfer money','how to do money transfer'),
    ('debit card block karo','block debit card'),
    ('sala eshtu',           'what is the loan rate'),
    ('nearest branch',       'nearest branch'),
]
for kn, en in no_match_cases:
    r = match_form_from_speech(kn, en)
    chk(f'no form for "{en or kn}"', r is None, f'got={r}')

print('\n-- Transactional requests SHOULD open forms --')
match_cases = [
    ('cash withdrawal madabeku', 'cash withdrawal',         'cash_withdrawal'),
    ('hinpade madabeku',         'withdraw money',          'cash_withdrawal'),
    ('cash deposit madabeku',    'deposit money',           'cash_deposit'),
    ('khate tere madabeku',      'open account',            'open_account'),
    ('loan application madabeku','apply for loan',          'apply_loan'),
    ('sala arji',                'loan application',        'apply_loan'),
    ('cheque book beku',         'cheque book request',     'cheque_book_request'),
    ('hosa atm card beku',       'new atm card apply',      'atm_debit_card'),
    ('mobile update madabeku',   'mobile update',           'mobile_update'),
    ('check stop madabeku',      'stop cheque payment',     'stop_cheque'),
    ('rtgs madabeku',            'rtgs transfer',           'rtgs_neft'),
]
for kn, en, expected in match_cases:
    r = match_form_from_speech(kn, en)
    chk(f'form for "{en}"', r == expected, f'got={r} expected={expected}')

print('\n-- Edge cases (acceptable routing) --')
edge_cases = [
    ('cheque book eshtu dina', 'how many days for cheque book', 'cheque_book_request'),
]
for kn, en, expected in edge_cases:
    r = match_form_from_speech(kn, en)
    chk(f'edge "{en}"', r == expected, f'got={r} (acceptable — contains exact keyword)')
if failed == 0:
    print(f'  ALL PASS -- {passed} tests passed')
else:
    print(f'  {failed} FAILURE(S) -- {passed} passed, {failed} failed')
print(f'{"="*55}')
sys.exit(1 if failed else 0)
