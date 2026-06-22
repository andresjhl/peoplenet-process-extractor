import pytest

from peoplenet_process_extractor.scenario.parsing import parse_entry_method


def test_no_arguments():
    method, args = parse_entry_method("MY_METHOD()")
    assert method == "MY_METHOD"
    assert args == []


def test_single_string():
    method, args = parse_entry_method('GLB_M_PC_EXE("STEP_SAVE")')
    assert method == "GLB_M_PC_EXE"
    assert args == ["STEP_SAVE"]


def test_multiple_literals():
    method, args = parse_entry_method('FOO("BAR", "BAZ")')
    assert method == "FOO"
    assert args == ["BAR", "BAZ"]


def test_integer_argument():
    method, args = parse_entry_method("MY_METHOD(42)")
    assert method == "MY_METHOD"
    assert args == [42]


def test_float_argument():
    method, args = parse_entry_method("MY_METHOD(3.14)")
    assert method == "MY_METHOD"
    assert args == [3.14]


def test_boolean_arguments():
    method, args = parse_entry_method("MY_METHOD(true, false)")
    assert method == "MY_METHOD"
    assert args == [True, False]


def test_null_argument():
    method, args = parse_entry_method("MY_METHOD(null)")
    assert method == "MY_METHOD"
    assert args == [None]


def test_mixed_literals():
    method, args = parse_entry_method('MY_METHOD("STR", 10, true, null)')
    assert method == "MY_METHOD"
    assert args == ["STR", 10, True, None]


def test_unsupported_format_no_parens():
    with pytest.raises(ValueError, match="Unsupported entry method format"):
        parse_entry_method("JUST_A_NAME")


def test_unsupported_format_expression():
    with pytest.raises(ValueError, match="Unsupported argument literal"):
        parse_entry_method("MY_METHOD(SOME_VAR)")


def test_empty_string():
    with pytest.raises(ValueError, match="empty"):
        parse_entry_method("")


def test_whitespace_only():
    with pytest.raises(ValueError, match="empty"):
        parse_entry_method("   ")


def test_escaped_quote_rejected():
    # METHOD("A\"B") contains a backslash inside the string literal.
    # Escape sequences are not supported; this must raise, not silently mangle the value.
    with pytest.raises(ValueError, match="not supported"):
        parse_entry_method('MY_METHOD("A\\"B")')


def test_backslash_in_single_quoted_string_rejected():
    with pytest.raises(ValueError, match="not supported"):
        parse_entry_method("MY_METHOD('path\\\\to\\\\file')")
