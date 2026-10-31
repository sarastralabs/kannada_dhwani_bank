# Decision Router

Routes NLU intent labels to either an informational response (answered from `data/bank_info.json`) or a transactional specification (list of entity fields to collect before form generation).

Pure Python — no ML models, no external dependencies.

---

## Quick Start

```python
from backend.decision_router import route

# Informational
result = route("interest_rate_query")
print(result["route"])          # "informational"
print(result["response_text"])  # "Here are our current interest rates. ..."

# Transactional
result = route("open_account")
print(result["route"])            # "transactional"
print(result["required_fields"])  # ["full_name", "date_of_birth", "address", "account_type"]
print(result["response_text"])    # "To open a new bank account, I will need ..."
```

---

## Intent Categories

| Route | Intents |
|-------|---------|
| `informational` | `check_balance`, `account_info_query`, `interest_rate_query` |
| `transactional` | `open_account`, `apply_loan`, `deposit_money`, `withdraw_money` |

---

## Return Value Schema

Every `route()` call returns a dict containing:

| Key | Always present | Description |
|-----|---------------|-------------|
| `route` | yes | `"informational"` or `"transactional"` |
| `intent` | yes | The input intent string, echoed back |
| `response_text` | yes | Human-readable text suitable for TTS output |
| `required_fields` | transactional only | List of entity field names to collect |

---

## API

### `route(intent: str) -> dict`

| Argument | Description |
|----------|-------------|
| `intent` | One of the 7 known intent labels |

**Raises:** `RouterError` for any unrecognised intent string (including empty string).

---

## Known Limitations

### `account_info_query` always returns the general fallback response

When the NLU classifies a query as `account_info_query`, the router currently returns:

> *"For account-related queries, please visit your nearest branch with a valid photo identity document."*

This is the `"general"` entry from `data/bank_info.json`.

**Why:** `account_info_query` covers many distinct sub-procedures — ATM card block, PIN change, cheque book request, name change, mobile number update, internet banking activation, mini statement, and more. Selecting the correct specific response requires knowing *which* of these the user intended. That disambiguation depends on entity extraction: detecting "ATM" → `atm_block`, "PIN" → `pin_change`, "name" → `name_change`, etc.

Entity extraction is **out of scope for this module** (it would be handled by a future spaCy-based NER module). The general fallback is a deliberate, documented choice — not a bug. The specific procedure texts are already present in `bank_info.json["account_procedures"]` and can be selected once entity extraction is available by extending `_build_account_info_response()` in `router.py` to accept an entity hint.

**Impact on demo:** For the pipeline demonstration, `account_info_query` will always give the general branch-visit response. This is honest and appropriate for a demo scope. State this explicitly if asked in a viva.

---

## `data/bank_info.json` Structure

```
interest_rates/          — rates for savings, FD (1/3/5yr), and all loan types
loan_repayment/info      — EMI explanation text
account_procedures/      — procedure text for: name_change, mobile_update,
                           atm_block, pin_change, cheque_book, internet_banking,
                           mini_statement, branch_locator, nominee_update, general
check_balance_note       — demo placeholder for balance queries
```

All text values are written for TTS readability: no abbreviations, no symbols, rates spelled out ("3 point 5 percent per annum").

---

## Files

```
backend/decision_router/
├── __init__.py      Public API: route(), RouterError, intent set constants
├── router.py        Core routing logic, response builders, REQUIRED_FIELDS map
└── exceptions.py    RouterError definition

data/
└── bank_info.json   Banking content (rates, procedures, placeholder text)
```
