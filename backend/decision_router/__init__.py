"""
backend/decision_router/__init__.py

Public API for the Decision Router module.

Quick-start
-----------
    from backend.decision_router import route

    result = route("interest_rate_query")
    print(result["route"])          # "informational"
    print(result["response_text"])  # "Here are our current interest rates. ..."

    result = route("open_account")
    print(result["route"])            # "transactional"
    print(result["required_fields"])  # ["full_name", "date_of_birth", ...]
    print(result["response_text"])    # "To open a new bank account, I will need ..."
"""

from backend.decision_router.exceptions import RouterError
from backend.decision_router.router import (
    ALL_INTENTS,
    INFORMATIONAL_INTENTS,
    REQUIRED_FIELDS,
    TRANSACTIONAL_INTENTS,
    route,
)

__all__ = [
    "route",
    "RouterError",
    "INFORMATIONAL_INTENTS",
    "TRANSACTIONAL_INTENTS",
    "ALL_INTENTS",
    "REQUIRED_FIELDS",
]
