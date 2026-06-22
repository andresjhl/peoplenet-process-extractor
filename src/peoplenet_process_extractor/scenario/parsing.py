import re
from typing import Any

_CALL_RE = re.compile(r"^(?P<method>[A-Za-z_][A-Za-z0-9_]*)\((?P<args>.*)\)\s*$", re.DOTALL)


def parse_entry_method(raw: str) -> tuple[str, list[Any]]:
    """Parse 'METHOD(arg1, arg2)' into (method, args).

    Only supports simple literal arguments: strings, integers, floats,
    booleans, null. Raises ValueError for unsupported formats.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Entry method string is empty")

    m = _CALL_RE.match(raw)
    if not m:
        raise ValueError(
            f"Unsupported entry method format: {raw!r}. "
            "Expected: METHOD_NAME(arg1, arg2, ...)"
        )

    method = m.group("method")
    args_str = m.group("args").strip()

    if not args_str:
        return method, []

    return method, _parse_literal_args(args_str)


def _split_args(args_str: str) -> list[str]:
    """Split on commas, respecting quoted strings."""
    parts: list[str] = []
    current: list[str] = []
    in_string = False
    string_char = ""

    for ch in args_str:
        if in_string:
            current.append(ch)
            if ch == string_char:
                in_string = False
        elif ch in ('"', "'"):
            in_string = True
            string_char = ch
            current.append(ch)
        elif ch == ",":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

    if current or not parts:
        parts.append("".join(current).strip())

    return parts


def _parse_literal_args(args_str: str) -> list[Any]:
    return [_parse_literal(p) for p in _split_args(args_str) if p]


def _parse_literal(s: str) -> Any:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        inner = s[1:-1]
        if "\\" in inner:
            raise ValueError(
                f"Escape sequences in string arguments are not supported: {s!r}. "
                "Use simple string literals without backslashes."
            )
        return inner
    if s == "null":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        raise ValueError(f"Unsupported argument literal: {s!r}") from None
