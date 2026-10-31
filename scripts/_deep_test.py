"""Deep test — router, bank_info, keywords, balance, pipeline, transcripts."""
import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('BANK_TTS_ENGINE', 'mms')

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

# ── 1. bank_info.json ────────────────────────────────────────────────────────
print('\n── 1. bank_info.json ──')
with open('data/bank_info.json', encoding='utf-8') as f:
    bi = json.load(f)

chk('check_balance_note no longer says unavailable',
    'not available' not in bi['check_balance_note'].lower(),
    bi['check_balance_note'][:70])
chk('check_balance_note_kn mentions account number',
    'ಖಾತೆ' in bi.get('check_balance_note_kn', ''),
    bi.get('check_balance_note_kn', '')[:60])
chk('form_submitted_kn has thank you (ಧನ್ಯವಾದ)',
    'ಧನ್ಯವಾದ' in bi.get('form_submitted_kn', ''),
    bi.get('form_submitted_kn', '')[:70])
chk('form_submitted_en mentions branch',
    'branch' in bi.get('form_submitted_en', '').lower())
chk('all 8 interest_rates_kn keys present',
    len(bi.get('interest_rates_kn', {})) == 8,
    str(list(bi.get('interest_rates_kn', {}).keys())))
chk('interest_rates_all_kn is non-empty Kannada',
    len(bi.get('interest_rates_all_kn', '')) > 50)
all_procs = ['atm_block', 'pin_change', 'cheque_book', 'mobile_update',
             'name_change', 'internet_banking', 'mini_statement',
             'branch_locator', 'nominee_update', 'general']
for proc in all_procs:
    chk(f'account_procedures.{proc}_kn exists',
        f'{proc}_kn' in bi['account_procedures'],
        bi['account_procedures'].get(f'{proc}_kn', 'MISSING')[:50])

# ── 2. Decision Router — all 7 intents ───────────────────────────────────────
print('\n── 2. Decision Router (all intents) ──')
from backend.decision_router.router import route, ALL_INTENTS, INFORMATIONAL_INTENTS, TRANSACTIONAL_INTENTS

for intent in sorted(ALL_INTENTS):
    r = route(intent, 'test query', 'ಪರೀಕ್ಷೆ')
    chk(f'{intent}: response_text not empty', bool(r.get('response_text')))
    chk(f'{intent}: response_text_kn not empty', bool(r.get('response_text_kn')),
        r.get('response_text_kn', '')[:50])
    if intent in TRANSACTIONAL_INTENTS:
        chk(f'{intent}: route=transactional', r['route'] == 'transactional')
        chk(f'{intent}: required_fields present', bool(r.get('required_fields')))
    else:
        chk(f'{intent}: route=informational', r['route'] == 'informational')

# ── 3. Interest rate specific product detection ───────────────────────────────
print('\n── 3. Interest Rate — Specific Product Detection ──')
rate_cases = [
    ('what is fixed deposit rate',    'fixed deposit', True),
    ('1 year fd rate',                '1 year',        True),
    ('3 year fd rate',                '3 year',        True),
    ('5 year fd rate',                '5 year',        True),
    ('home loan interest rate',       'home loan',     True),
    ('personal loan rate',            'personal loan', True),
    ('education loan rate',           'education loan',True),
    ('car loan rate',                 'car loan',      True),
    ('savings account interest',      'savings',       True),
    ('',                              'savings',       True),  # full list
    ('',                              'home loan',     True),  # full list has all
]
for query, kw, should in rate_cases:
    r = route('interest_rate_query', query)
    en = r['response_text'].lower()
    kn = r.get('response_text_kn', '')
    chk(f'rate [{query[:30] or "all"}] — en has "{kw}"', (kw in en) == should, en[:70])
    chk(f'rate [{query[:30] or "all"}] — kn not empty', bool(kn), kn[:50])

# specific query shorter than full list
r_fd = route('interest_rate_query', 'what is fixed deposit rate')
r_all = route('interest_rate_query', '')
chk('specific FD response shorter than full list',
    len(r_fd['response_text']) < len(r_all['response_text']),
    f'fd={len(r_fd["response_text"])} all={len(r_all["response_text"])}')

# ── 4. account_info_query — English + Kannada keyword matching ───────────────
print('\n── 4. account_info_query — Keyword Matching ──')
info_cases = [
    # (en_query, kn_query, expected_kw_in_en_response, expected_kw_in_kn_response)
    ('block atm card',       '',               '1800',    'ಕರೆ'),
    ('',                     'ಎಟಿಎಂ ಬ್ಲಾಕ್',  '1800',    'ಕರೆ'),
    ('pin change',           '',               'pin',     'ಪಿನ್'),
    ('',                     'ಪಿನ್ ಬದಲಾವಣೆ', 'pin',     'ಪಿನ್'),
    ('cheque book request',  '',               'cheque',  'ಚೆಕ್'),
    ('',                     'ಚೆಕ್ ಪುಸ್ತಕ',   'cheque',  'ಚೆಕ್'),
    ('mobile update',        '',               'mobile',  'ಮೊಬೈಲ್'),
    ('internet banking',     '',               'internet','ಇಂಟರ್ನೆಟ್'),
    ('mini statement',       '',               'atm',     'ATM'),
    ('nearest branch',       '',               'branch',  'ಶಾಖೆ'),
    ('',                     'ಹತ್ತಿರದ ಶಾಖೆ',  'branch',  'ಶಾಖೆ'),
    ('nominee update',       '',               'nominee', 'ನಾಮಿನಿ'),
    ('name change',          '',               'name',    'ಹೆಸರನ್ನು'),  # accusative form used in Kannada
    ('something unknown xyz','',               'branch',  'ಶಾಖೆ'),  # general fallback
]
for en_q, kn_q, en_kw, kn_kw in info_cases:
    r = route('account_info_query', en_q, kn_q)
    en_resp = r['response_text'].lower()
    kn_resp = r.get('response_text_kn', '')
    label = (en_q or kn_q)[:25]
    chk(f'account_info [{label}] en has "{en_kw}"',
        en_kw.lower() in en_resp, en_resp[:70])
    chk(f'account_info [{label}] kn has "{kn_kw}"',
        kn_kw in kn_resp, kn_resp[:60])

# ── 5. Keywords module ────────────────────────────────────────────────────────
print('\n── 5. Keywords Module ──')
from backend.decision_router.keywords import match_account_procedure

kw_tests = [
    # English
    ('block atm',        'atm_block'),
    ('atm card block',   'atm_block'),
    ('lost card',        'atm_block'),
    ('pin change',       'pin_change'),
    ('forgot pin',       'pin_change'),
    ('cheque book',      'cheque_book'),
    ('mobile update',    'mobile_update'),
    ('change mobile',    'mobile_update'),
    ('name change',      'name_change'),
    ('internet banking', 'internet_banking'),
    ('net banking',      'internet_banking'),
    ('mini statement',   'mini_statement'),
    ('last transactions','mini_statement'),
    ('nearest branch',   'branch_locator'),
    ('nominee update',   'nominee_update'),
    # Kannada script
    ('ಎಟಿಎಂ ಬ್ಲಾಕ್',     'atm_block'),
    ('ಕಾರ್ಡ್ ಬ್ಲಾಕ್',    'atm_block'),
    ('ಪಿನ್ ಬದಲಾವಣೆ',    'pin_change'),
    ('ಪಿನ್ ಮರೆತಿದೆ',     'pin_change'),
    ('ಚೆಕ್ ಪುಸ್ತಕ',      'cheque_book'),
    ('ಚೆಕ್ ಬುಕ್',         'cheque_book'),
    ('ಮೊಬೈಲ್ ನವೀಕರಣ',   'mobile_update'),
    ('ಹೆಸರು ಬದಲಾವಣೆ',   'name_change'),
    ('ಇಂಟರ್ನೆಟ್ ಬ್ಯಾಂಕಿಂಗ್','internet_banking'),
    ('ನೆಟ್ ಬ್ಯಾಂಕಿಂಗ್',   'internet_banking'),
    ('ಮಿನಿ ಸ್ಟೇಟ್\u200cಮೆಂಟ್','mini_statement'),
    ('ಹತ್ತಿರದ ಶಾಖೆ',     'branch_locator'),
    ('ನಾಮಿನಿ',           'nominee_update'),
    # Unknown / empty
    ('hello world',      None),
    ('',                 None),
    ('xyz abc def',      None),
]
for query, expected in kw_tests:
    result = match_account_procedure(query)
    chk(f'keyword "{query[:25]}"', result == expected,
        f'got={result} expected={expected}')

# ── 6. Balance Lookup ────────────────────────────────────────────────────────
print('\n── 6. Balance Lookup ──')
from backend.balance_lookup import lookup_balance

r = lookup_balance('1234567890')
chk('found demo account 1234567890', r['found'] is True)
chk('balance_inr == 45230.50', r['balance_inr'] == 45230.50, str(r['balance_inr']))
chk('message_en has balance', '45,230' in r['message_en'])
chk('message_kn has Kannada', 'ಶಿಲ್ಕು' in r['message_kn'], r['message_kn'][:60])
chk('message_kn has account digits as words', 'ಒಂದು' in r['message_kn'])

r2 = lookup_balance('9999999999')
chk('not found returns found=False', r2['found'] is False)
chk('not found message_kn present', bool(r2.get('message_kn')))
chk('not found message_kn has Kannada', 'ಖಾತೆ' in r2.get('message_kn',''))

r3 = lookup_balance('123')
chk('short number rejected', r3['found'] is False)
chk('short number message_kn present', bool(r3.get('message_kn')))

r4 = lookup_balance('')
chk('empty string returns found=False', r4['found'] is False)

# ── 7. transcripts.json ──────────────────────────────────────────────────────
print('\n── 7. transcripts.json ──')
with open('data/stt_test_audio/transcripts.json', encoding='utf-8') as f:
    tr = json.load(f)

chk('_note key explains missing clips', '_note' in tr and '005' in tr['_note'])
chk('clips 005 008 009 010 absent',
    all(f'clip_0{n}.wav' not in tr for n in ['05','08','09','10']))
chk('11 expected clips present',
    all(c in tr for c in ['clip_001.wav','clip_002.wav','clip_003.wav',
                          'clip_004.wav','clip_006.wav','clip_007.wav',
                          'clip_011.wav','clip_012.wav','clip_013.wav',
                          'clip_014.wav','clip_015.wav']))
chk('all present clips have Kannada transcripts',
    all('ಕ' in v or 'ಖ' in v or 'ಸ' in v or 'ಹ' in v or 'ನ' in v or 'ಠ' in v or 'ಎ' in v or 'ಇ' in v or 'ಪ' in v or 'ಚ' in v
        for k, v in tr.items() if k != '_note'))

# ── 8. train.py static checks ────────────────────────────────────────────────
print('\n── 8. train.py ──')
with open('backend/nlu/train.py', encoding='utf-8') as f:
    train_src = f.read()

chk('docstring says 301 samples', '301' in train_src)
chk('docstring does NOT say 294', '294' not in train_src)
chk('overwrite warning message present', 'Existing checkpoint' in train_src)
chk('overwrite warning checks model.safetensors', 'model.safetensors' in train_src)
chk('syntax valid', __import__('ast').parse(train_src) is not None)

# ── 9. playAudio.ts ──────────────────────────────────────────────────────────
print('\n── 9. playAudio.ts ──')
with open('frontend/src/utils/playAudio.ts', encoding='utf-8') as f:
    ts_src = f.read()

chk('1200ms silence gap present', '1200' in ts_src)
chk('old 800ms value removed', 'setTimeout(resolve, 800)' not in ts_src)
chk('comment mentions CPU machines', 'CPU' in ts_src or 'cpu' in ts_src.lower())

# ── 10. README.md ────────────────────────────────────────────────────────────
print('\n── 10. README.md ──')
with open('README.md', encoding='utf-8') as f:
    readme = f.read()

chk('correct model folder whisper-kannada-medium-ct2', 'whisper-kannada-medium-ct2' in readme)
chk('old wrong folder whisper-medium-vaani-ct2 removed',
    'whisper-medium-vaani-ct2' not in readme)
chk('correct HF model vasista22/whisper-kannada-medium', 'vasista22/whisper-kannada-medium' in readme)
chk('old wrong HF model ARTPARK-IISc removed',
    'ARTPARK-IISc/whisper-medium-vaani-kannada' not in readme)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f'\n{"="*55}')
if failed == 0:
    print(f'  ALL PASS — {passed} tests passed')
else:
    print(f'  {failed} FAILURE(S) — {passed} passed, {failed} failed')
print(f'{"="*55}')
sys.exit(1 if failed else 0)
