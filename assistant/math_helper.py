"""Safe evaluation of simple math expressions (no code execution)."""
from __future__ import annotations

import re
from typing import Optional


def safe_calculate(expression: str) -> Optional[float]:
    """
    Evaluate a simple math expression. Supports + - * / % and numbers.
    Handles "X percent of Y" -> X/100 * Y.
    Returns None if invalid.
    """
    s = expression.strip().lower()
    # "15 percent of 80" -> 0.15 * 80
    m = re.match(r"^(.+?)\s*percent\s+of\s+(.+)$", s)
    if m:
        try:
            a = _eval_simple(m.group(1).strip())
            b = _eval_simple(m.group(2).strip())
            if a is not None and b is not None:
                return (a / 100.0) * b
        except Exception:
            pass
        return None
    return _eval_simple(s)


def _eval_simple(s: str) -> Optional[float]:
    """Only allow numbers and + - * / ( ) . and spaces."""
    s = s.replace(" ", "")
    if not re.match(r"^[\d+\-*/().%\s]+$", s):
        return None
    try:
        # Replace % with * 0.01 for "50%" style
        s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1 * 0.01)", s)
        return float(eval(s))
    except Exception:
        return None
