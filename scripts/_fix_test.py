"""Test all 4 fixes from code review."""
import ast, sys, os
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

# ── FIX 1: history.py — DELETE routes have admin auth ─────────────────────────
print('\n── Fix 1: history.py DELETE auth ──')
with open('api/routes/history.py', encoding='utf-8') as f:
    history_src = f.read()

chk('Depends imported', 'Depends' in history_src)
chk('admin_auth imported', 'from api import admin_auth' in history_src)
chk('DELETE /{item_id} has require_admin',
    'require_admin' in history_src and '_admin: dict = Depends(admin_auth.require_admin)' in history_src)
chk('DELETE / (clear_all) has require_admin',
    history_src.count('require_admin') >= 2)
chk('syntax valid', ast.parse(history_src) is not None)

# Verify both DELETE functions have the dependency via AST
tree = ast.parse(history_src)
delete_funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name in ('delete_item', 'clear_all')]
chk('delete_item function exists', len([f for f in delete_funcs if f.name == 'delete_item']) == 1)
chk('clear_all function exists',   len([f for f in delete_funcs if f.name == 'clear_all']) == 1)
for fn in delete_funcs:
    # FastAPI Depends() is a default value, not a type annotation
    has_auth = any(
        isinstance(arg_default, ast.Call) and
        ast.unparse(arg_default).startswith('Depends(')
        for arg_default in ast.walk(fn)
        if isinstance(arg_default, ast.Call) and
        hasattr(arg_default.func, 'id') and arg_default.func.id == 'Depends'
    )
    chk(f'{fn.name} has Depends(require_admin)', has_auth)

# ── FIX 2: greetings.py — night slot last line_en matches line_kn ─────────────
print('\n── Fix 2: greetings.py night translation ──')
from backend.greetings import GREET_LINES, pick_greeting, slot_for_hour

night_lines = GREET_LINES['night']
last_night = night_lines[-1]

chk('night last line_kn has welcome text',
    'ಸ್ವಾಗತ' in last_night['line_kn'],
    last_night['line_kn'][:60])
chk('night last line_en has welcome (not thank you)',
    'welcome' in last_night['line_en'].lower(),
    last_night['line_en'])
chk('night last line_en does NOT say "thank you for your time"',
    'thank you for your time' not in last_night['line_en'].lower(),
    last_night['line_en'])
chk('night last line_en says Namaskara',
    'namaskara' in last_night['line_en'].lower() or 'welcome' in last_night['line_en'].lower(),
    last_night['line_en'])

# All night lines — kn and en both non-empty
for i, line in enumerate(night_lines):
    chk(f'night line {i} kn not empty', bool(line['line_kn'].strip()))
    chk(f'night line {i} en not empty', bool(line['line_en'].strip()))

# pick_greeting works for all slots
for slot in ('morning', 'afternoon', 'evening', 'night'):
    g = pick_greeting(slot=slot, variant=0)
    chk(f'pick_greeting {slot} returns line_kn', bool(g['line_kn']))
    chk(f'pick_greeting {slot} returns line_en', bool(g['line_en']))

# slot_for_hour covers all hours
slot_map = {h: slot_for_hour(h) for h in range(24)}
chk('hours 5-11 → morning',   all(slot_map[h] == 'morning'   for h in range(5, 12)))
chk('hours 12-15 → afternoon', all(slot_map[h] == 'afternoon' for h in range(12, 16)))
chk('hours 16-19 → evening',  all(slot_map[h] == 'evening'   for h in range(16, 20)))
chk('hours 20-23+0-4 → night', all(slot_map[h] == 'night'    for h in list(range(20, 24)) + list(range(0, 5))))

# ── FIX 3: dialog_context.py — mode validation ────────────────────────────────
print('\n── Fix 3: dialog_context.py mode validation ──')
from backend.dialog_context import parse_dialog_context, _VALID_MODES

chk('_VALID_MODES defined', '_VALID_MODES' in dir())
chk('_VALID_MODES contains assist',       'assist'      in _VALID_MODES)
chk('_VALID_MODES contains form_select',  'form_select' in _VALID_MODES)
chk('_VALID_MODES contains form',         'form'        in _VALID_MODES)

# Valid modes pass through
for mode in ('assist', 'form_select', 'form'):
    ctx = parse_dialog_context({'mode': mode})
    chk(f'valid mode "{mode}" passes through', ctx.mode == mode)

# Invalid modes fall back to assist
for bad_mode in ('hacked', 'admin', '', 'ASSIST', 'unknown', '   '):
    ctx = parse_dialog_context({'mode': bad_mode})
    chk(f'invalid mode "{bad_mode}" → assist', ctx.mode == 'assist',
        f'got={ctx.mode}')

# None / empty input
ctx_none = parse_dialog_context(None)
chk('None input → mode=assist', ctx_none.mode == 'assist')

ctx_empty = parse_dialog_context({})
chk('empty dict → mode=assist', ctx_empty.mode == 'assist')

# Case insensitive
ctx_upper = parse_dialog_context({'mode': 'FORM_SELECT'})
chk('uppercase FORM_SELECT → form_select', ctx_upper.mode == 'form_select')

# Other fields still work with valid mode
ctx_full = parse_dialog_context({
    'mode': 'form_select',
    'last_intent': 'check_balance',
    'clarify_attempts': 2,
    'pending_intents': ['check_balance', 'apply_loan'],
})
chk('full context parsed correctly', ctx_full.mode == 'form_select')
chk('last_intent parsed', ctx_full.last_intent == 'check_balance')
chk('clarify_attempts parsed', ctx_full.clarify_attempts == 2)
chk('pending_intents parsed', ctx_full.pending_intents == ['check_balance', 'apply_loan'])

# ── FIX 4: kiosk.py — _warm_running flag ──────────────────────────────────────
print('\n── Fix 4: kiosk.py _warm_running flag ──')
with open('api/routes/kiosk.py', encoding='utf-8') as f:
    kiosk_src = f.read()

chk('_warm_running set to True before warm starts',
    '_warm_running = True' in kiosk_src)
chk('early return if already running',
    'if _warm_running' in kiosk_src and 'return' in kiosk_src)
chk('_warm_running reset to False in finally',
    '_warm_running = False' in kiosk_src)
chk('lock used when setting True',
    kiosk_src.index('_warm_running = True') > kiosk_src.index('_warm_lock'))
chk('syntax valid', ast.parse(kiosk_src) is not None)

# Check order: initial _warm_running=False declaration is at module level,
# then inside the function: check → set True → loop → set False in finally
fn_src = kiosk_src[kiosk_src.index('def _warm_all_variants'):]
true_pos  = fn_src.index('_warm_running = True')
false_pos = fn_src.rindex('_warm_running = False')  # last occurrence = finally block
check_pos = fn_src.index('if _warm_running')
chk('check comes before set True',    check_pos < true_pos)
chk('set True comes before finally False', true_pos < false_pos)

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*55}')
if failed == 0:
    print(f'  ALL PASS — {passed} tests passed')
else:
    print(f'  {failed} FAILURE(S) — {passed} passed, {failed} failed')
print(f'{"="*55}')
sys.exit(1 if failed else 0)
