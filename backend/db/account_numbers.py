"""Account numbers with a check digit.

A new account number is 10 digits: a fixed leading 7, eight random digits, and a final
check digit worked out from the first nine (the Luhn rule used on bank cards). If speech
recognition mishears a digit, or two digits swap, the check no longer adds up — so the kiosk
can say "that account number is not valid, please say it again" instead of opening the wrong
customer. Demo accounts such as 1234567890 predate this and are not required to pass.
"""

from __future__ import annotations

import re
import secrets

PREFIX = "7"
LENGTH = 10


def luhn_check_digit(payload: str) -> str:
    """Digit that makes ``payload + digit`` pass the Luhn test."""
    total = 0
    for i, ch in enumerate(reversed(payload)):
        d = int(ch)
        if i % 2 == 0:  # every second digit, starting next to the check digit
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def is_valid(number: str) -> bool:
    """True when ``number`` is 10 digits and its check digit is right."""
    digits = re.sub(r"\D", "", number or "")
    return len(digits) == LENGTH and luhn_check_digit(digits[:-1]) == digits[-1]


def new_account_number() -> str:
    body = PREFIX + "".join(str(secrets.randbelow(10)) for _ in range(LENGTH - 2))
    return body + luhn_check_digit(body)
