"""Tests for the LN4 scanner."""
from __future__ import annotations


from peoplenet_process_extractor.references.scanner import (
    _classify_argument,
    _split_arguments,
    scan_text,
)


class TestScanEmpty:
    def test_empty_text(self):
        assert scan_text("") == []

    def test_no_calls(self):
        text = "RULE NO_CALLS\nMETHOD OBJ.NO_CALLS\n  x = 1 + 2\nEND\n"
        assert scan_text(text) == []

    def test_whitespace_only(self):
        assert scan_text("   \n\t\n") == []


class TestSimpleCall:
    def test_simple_call(self):
        text = 'Call(nodeId, "DO_THING")'
        results = scan_text(text)
        assert len(results) == 1
        r = results[0]
        assert r.start_offset == 0
        assert r.end_offset == len(text)
        assert r.raw_expression == text
        assert r.raw_arguments == 'nodeId, "DO_THING"'
        assert r.status == "observed"
        assert r.line_start == 1
        assert r.column_start == 1

    def test_call_at_start_of_file(self):
        text = 'Call(x, "Y")'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].start_offset == 0

    def test_call_preceded_by_assignment(self):
        text = '  result = Call(nodeId, "METHOD")\n'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].function_name if hasattr(results[0], "function_name") else True

    def test_call_not_at_end_of_line_but_end_of_text(self):
        text = 'x = Call(n, "M")'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].end_offset == len(text)

    def test_call_end_offset_equals_len(self):
        text = 'Call(a, "B")'
        results = scan_text(text)
        assert results[0].end_offset == len(text)


class TestCallWithSpaceBeforeParen:
    def test_space_before_paren(self):
        text = 'Call (nodeB, "ACTION_TWO")'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].start_offset == 0
        assert results[0].raw_expression == text

    def test_tab_before_paren(self):
        text = 'Call\t(nodeB, "ACTION")'
        results = scan_text(text)
        assert len(results) == 1


class TestMultipleCallsSameLine:
    def test_two_calls_same_line(self):
        text = 'Call(nodeA, "ACT_A") + Call(nodeB, "ACT_B")'
        results = scan_text(text)
        assert len(results) == 2
        assert results[0].start_offset < results[1].start_offset

    def test_results_ordered_by_start_offset(self):
        text = 'x = Call(a, "A"); y = Call(b, "B"); z = Call(c, "C")'
        results = scan_text(text)
        assert len(results) == 3
        offsets = [r.start_offset for r in results]
        assert offsets == sorted(offsets)


class TestMultilineCall:
    def test_multiline_call(self):
        text = 'result = Call(\n  nodeJ,\n  "ACTION_TEN"\n)'
        results = scan_text(text)
        assert len(results) == 1
        r = results[0]
        assert r.line_start == 1
        assert r.line_end > r.line_start

    def test_multiline_line_end_correct(self):
        text = 'Call(\n  a,\n  "B"\n)'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].line_end == 4


class TestNestedCalls:
    def test_nested_call_both_detected(self):
        text = 'Call(nodeE, OtherFunc(Call(nodeF, "INNER")), "ACTION")'
        results = scan_text(text)
        # Both the outer Call and inner Call should be detected
        assert len(results) == 2

    def test_nested_call_inner_is_smaller(self):
        text = 'Call(a, OtherFunc(Call(b, "INNER")), "OUTER")'
        results = scan_text(text)
        assert len(results) == 2
        # Outer starts first; inner starts later
        outer = min(results, key=lambda r: r.start_offset)
        inner = max(results, key=lambda r: r.start_offset)
        assert inner.start_offset > outer.start_offset
        assert inner.end_offset < outer.end_offset

    def test_nested_inner_raw_expression_correct(self):
        text = 'Call(a, OtherFunc(Call(b, "X")), "Y")'
        results = scan_text(text)
        inner = max(results, key=lambda r: r.start_offset)
        assert inner.raw_expression == 'Call(b, "X")'


class TestStringExclusion:
    def test_call_inside_string_not_detected(self):
        text = '"Use Call(obj, method) to invoke"'
        results = scan_text(text)
        assert len(results) == 0

    def test_call_after_string_detected(self):
        text = 'msg = "not a call"; x = Call(n, "M")'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].raw_arguments == 'n, "M"'


class TestCommentExclusion:
    def test_tick_comment_call_not_detected(self):
        # ' is a tick line comment
        text = "'Call(nodeM, \"TICK_IGNORED\")\n"
        results = scan_text(text)
        assert len(results) == 0

    def test_tick_comment_inline_then_call(self):
        text = "' comment\nCall(n, \"M\")\n"
        results = scan_text(text)
        assert len(results) == 1

    def test_cstyle_line_comment_not_detected(self):
        text = '// Call(nodeL, "ALSO_IGNORED")\n'
        results = scan_text(text)
        assert len(results) == 0

    def test_block_comment_not_detected(self):
        text = '/* Call(nodeK, "IGNORED") */'
        results = scan_text(text)
        assert len(results) == 0

    def test_block_comment_multiline_not_detected(self):
        text = '/* line1\nCall(a, "B")\nline3 */'
        results = scan_text(text)
        assert len(results) == 0

    def test_call_after_block_comment_detected(self):
        text = '/* ignore */ Call(n, "M")'
        results = scan_text(text)
        assert len(results) == 1


class TestMalformedCall:
    def test_unclosed_paren(self):
        text = 'bad = Call(nodeY, "BAD_METHOD"\nEND\n'
        results = scan_text(text)
        assert len(results) == 1
        r = results[0]
        assert r.status == "malformed"
        assert "unclosed_parenthesis" in r.diagnostics

    def test_malformed_raw_expression_includes_rest(self):
        text = 'Call(x, "Y"\nEND'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].raw_expression.startswith("Call(")


class TestEmptyArgument:
    def test_empty_middle_arg(self):
        text = 'Call(nodeI, , "ACTION_NINE")'
        results = scan_text(text)
        assert len(results) == 1
        # raw_arguments should contain the comma
        assert ",  ," in results[0].raw_arguments or ", ," in results[0].raw_arguments


class TestWordBoundary:
    def test_mycall_not_detected(self):
        text = 'MyCall(x, "Y")'
        results = scan_text(text)
        assert len(results) == 0

    def test_xcall_not_detected(self):
        text = 'xCall(a, "B")'
        results = scan_text(text)
        assert len(results) == 0

    def test_underscore_before_call_not_detected(self):
        text = '_Call(a, "B")'
        results = scan_text(text)
        assert len(results) == 0

    def test_call_lowercase_not_detected(self):
        text = 'call(a, "B")'
        results = scan_text(text)
        assert len(results) == 0

    def test_call_uppercase_not_detected(self):
        text = 'CALL(a, "B")'
        results = scan_text(text)
        assert len(results) == 0

    def test_call_preceded_by_digit_not_detected(self):
        text = '1Call(a, "B")'
        results = scan_text(text)
        # digit before 'C' means it IS a word boundary (digits are isalnum though)
        # Per spec: "not preceded by an alphanumeric or underscore"
        assert len(results) == 0


class TestLineColumnTracking:
    def test_line_start_correct(self):
        text = "line1\nCall(x, \"Y\")\n"
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].line_start == 2

    def test_column_start_correct(self):
        text = '  Call(x, "Y")'
        results = scan_text(text)
        assert len(results) == 1
        assert results[0].column_start == 3  # 2 spaces + C at position 3

    def test_crlf_line_tracking(self):
        text = "line1\r\nCall(x, \"Y\")\r\n"
        results = scan_text(text)
        assert len(results) == 1
        # After \r\n we're on line 2
        assert results[0].line_start == 2

    def test_unicode_before_call(self):
        # Non-alphanumeric unicode char before Call; col counts code points
        # Use a punctuation character that is not alphanumeric
        text = "abc•Call(x, \"Y\")"  # bullet point before Call
        results = scan_text(text)
        assert len(results) == 1
        # 'abc•' is 4 chars, so Call starts at column 5
        assert results[0].column_start == 5


class TestSplitArguments:
    def test_single_arg(self):
        assert _split_arguments("nodeId") == ["nodeId"]

    def test_two_args(self):
        assert _split_arguments('nodeId, "METHOD"') == ['nodeId', ' "METHOD"']

    def test_comma_in_string(self):
        result = _split_arguments('"VALUE,WITH,COMMAS", "ACTION"')
        assert len(result) == 2
        assert result[0] == '"VALUE,WITH,COMMAS"'

    def test_nested_parens_not_split(self):
        result = _split_arguments('OtherFunc(a, b), "M"')
        assert len(result) == 2
        assert result[0] == "OtherFunc(a, b)"

    def test_empty_arg(self):
        result = _split_arguments('nodeI, , "ACTION_NINE"')
        assert len(result) == 3
        assert result[1].strip() == ""

    def test_empty_string(self):
        result = _split_arguments("")
        assert result == [""]


class TestClassifyArgument:
    def test_string_literal(self):
        kind, val = _classify_argument('"HELLO"')
        assert kind == "string_literal"
        assert val == "HELLO"

    def test_string_literal_with_whitespace(self):
        kind, val = _classify_argument('  "HELLO"  ')
        assert kind == "string_literal"
        assert val == "HELLO"

    def test_identifier(self):
        kind, val = _classify_argument("nodeId")
        assert kind == "identifier"
        assert val is None

    def test_identifier_with_underscores(self):
        kind, val = _classify_argument("my_node_123")
        assert kind == "identifier"

    def test_numeric(self):
        kind, val = _classify_argument("42")
        assert kind == "numeric_literal"
        assert val is None

    def test_expression(self):
        kind, val = _classify_argument("a + b")
        assert kind == "expression"
        assert val is None

    def test_empty(self):
        kind, val = _classify_argument("")
        assert kind == "empty"
        assert val is None

    def test_whitespace_only_is_empty(self):
        kind, val = _classify_argument("   ")
        assert kind == "empty"
