"""
Character-level LN4 scanner for Call() expressions.

State machine: NORMAL / IN_STRING / IN_LINE_COMMENT / IN_BLOCK_COMMENT

Key design decisions:
- 'Call' keyword is case-sensitive (exactly 'Call').
- 'Call' must not be preceded by an alphanumeric or underscore (word boundary).
- Inner calls are naturally re-discovered: after recording a Call extent, we advance
  only past the 'Call' keyword (not past the full expression), so the main loop
  re-processes the inner contents.
- String contents, line comments (' or //), and block comments (/* ... */) are skipped.
- Deduplication set guards against any accidental double-recording.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_CALL_KW = "Call"
_CALL_KW_LEN = len(_CALL_KW)

# States
_NORMAL = 0
_IN_STRING = 1
_IN_LINE_COMMENT = 2
_IN_BLOCK_COMMENT = 3

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMERIC_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")


@dataclass
class ScanCall:
    start_offset: int
    end_offset: int
    line_start: int
    column_start: int
    line_end: int
    column_end: int
    raw_expression: str
    raw_arguments: str
    status: str   # "observed" | "malformed"
    diagnostics: list[str] = field(default_factory=list)


def _line_col_of(
    text: str,
    target_offset: int,
    from_offset: int,
    from_line: int,
    from_col: int,
) -> tuple[int, int]:
    """
    Walk text[from_offset:target_offset] counting newlines.
    Returns (line, col) at target_offset.
    '\\n' increments line and resets col to 1.
    '\\r' is treated as a regular character (increments col).
    """
    line = from_line
    col = from_col
    for i in range(from_offset, target_offset):
        ch = text[i]
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return line, col


def _find_call_extent(
    text: str,
    paren_pos: int,
) -> tuple[int, bool, list[str]]:
    """
    Find the matching closing ')' for the '(' at paren_pos.

    Returns (end_pos, is_closed, diagnostics) where:
    - end_pos: position AFTER the closing ')' (exclusive), or len(text) if unclosed
    - is_closed: True if a matching ')' was found
    - diagnostics: list of diagnostic code strings

    Handles nested parens and strings inside the argument list.
    """
    diagnostics: list[str] = []
    i = paren_pos + 1  # start after the opening '('
    depth = 1
    n = len(text)

    while i < n:
        ch = text[i]
        if ch == "(":
            depth += 1
            i += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1, True, diagnostics
            i += 1
        elif ch == '"':
            # Skip string content
            i += 1
            while i < n and text[i] != '"':
                i += 1
            if i < n:
                i += 1  # skip closing '"'
            else:
                diagnostics.append("unterminated_string")
        elif ch == "'" :
            # Line comment: skip to end of line
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "/":
            # C-style line comment: skip to end of line
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            # Block comment
            i += 2
            while i < n:
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    i += 2
                    break
                i += 1
        else:
            i += 1

    diagnostics.append("unclosed_parenthesis")
    return n, False, diagnostics


def _split_arguments(raw: str) -> list[str]:
    """
    Split raw_arguments text on top-level commas.
    Handles nested parens and string literals.
    """
    args: list[str] = []
    current_chars: list[str] = []
    depth = 0
    i = 0
    n = len(raw)

    while i < n:
        ch = raw[i]
        if ch == "(":
            depth += 1
            current_chars.append(ch)
            i += 1
        elif ch == ")":
            depth -= 1
            current_chars.append(ch)
            i += 1
        elif ch == '"':
            current_chars.append(ch)
            i += 1
            while i < n and raw[i] != '"':
                current_chars.append(raw[i])
                i += 1
            if i < n:
                current_chars.append(raw[i])
                i += 1
        elif ch == "," and depth == 0:
            args.append("".join(current_chars))
            current_chars = []
            i += 1
        else:
            current_chars.append(ch)
            i += 1

    args.append("".join(current_chars))
    return args


def _classify_argument(raw: str) -> tuple[str, str | None]:
    """
    Classify an argument string.
    Returns (kind, literal_value) where literal_value is set only for string_literal.
    """
    stripped = raw.strip()
    if not stripped:
        return "empty", None
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        return "string_literal", stripped[1:-1]
    if _NUMERIC_RE.match(stripped):
        return "numeric_literal", None
    if _IDENT_RE.match(stripped):
        return "identifier", None
    return "expression", None


def scan_text(text: str) -> list[ScanCall]:
    """
    Scan text for all Call() expressions.

    Returns a list of ScanCall objects sorted by (start_offset, end_offset).
    """
    results: list[ScanCall] = []
    seen: set[tuple[int, int]] = set()  # (start_offset, end_offset) dedup guard
    n = len(text)
    i = 0
    state = _NORMAL

    # Track position for line/col tracking
    # We'll compute line/col lazily from offsets

    while i < n:
        ch = text[i]

        if state == _NORMAL:
            # Check for line comment: tick '
            if ch == "'":
                state = _IN_LINE_COMMENT
                i += 1
                continue

            # Check for C-style line comment: //
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                state = _IN_LINE_COMMENT
                i += 2
                continue

            # Check for block comment: /*
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                state = _IN_BLOCK_COMMENT
                i += 2
                continue

            # Check for string
            if ch == '"':
                state = _IN_STRING
                i += 1
                continue

            # Check for 'Call' keyword
            if ch == "C" and text[i:i + _CALL_KW_LEN] == _CALL_KW:
                # Check word boundary before: not preceded by [A-Za-z0-9_]
                if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
                    i += 1
                    continue

                # Check word boundary after keyword: must be followed by optional whitespace and '('
                # The Call keyword must be followed by optional whitespace then '('
                j = i + _CALL_KW_LEN
                # Skip optional whitespace
                while j < n and text[j] in (" ", "\t"):
                    j += 1

                if j < n and text[j] == "(":
                    # Found a Call( expression
                    call_start = i
                    paren_pos = j

                    # Find extent
                    end_pos, is_closed, diagnostics = _find_call_extent(text, paren_pos)

                    # Compute positions
                    line_start, col_start = _line_col_of(text, call_start, 0, 1, 1)
                    # end_pos is exclusive (one past closing ')'), so closing ')' is at end_pos - 1
                    if is_closed:
                        close_paren_pos = end_pos - 1
                        line_end, col_end = _line_col_of(text, close_paren_pos, 0, 1, 1)
                    else:
                        # Unclosed: report end position
                        line_end, col_end = _line_col_of(text, end_pos - 1 if end_pos > 0 else 0, 0, 1, 1)

                    raw_expression = text[call_start:end_pos]
                    # raw_arguments: text between the outer parens
                    raw_arguments = text[paren_pos + 1:end_pos - 1] if is_closed else text[paren_pos + 1:end_pos]

                    status = "observed" if is_closed else "malformed"

                    key = (call_start, end_pos)
                    if key not in seen:
                        seen.add(key)
                        results.append(ScanCall(
                            start_offset=call_start,
                            end_offset=end_pos,
                            line_start=line_start,
                            column_start=col_start,
                            line_end=line_end,
                            column_end=col_end,
                            raw_expression=raw_expression,
                            raw_arguments=raw_arguments,
                            status=status,
                            diagnostics=diagnostics,
                        ))

                    # Advance only past 'Call' keyword so inner calls are re-discovered
                    i += _CALL_KW_LEN
                    continue

            i += 1

        elif state == _IN_STRING:
            if ch == '"':
                state = _NORMAL
            i += 1

        elif state == _IN_LINE_COMMENT:
            if ch == "\n":
                state = _NORMAL
            i += 1

        elif state == _IN_BLOCK_COMMENT:
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                state = _NORMAL
                i += 2
            else:
                i += 1

    results.sort(key=lambda c: (c.start_offset, c.end_offset))
    return results
