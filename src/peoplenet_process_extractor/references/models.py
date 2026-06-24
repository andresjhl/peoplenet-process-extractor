"""
Models and catalogs for reference-extraction-v1.

Position conventions:
- Offsets: 0-based character indices into the decoded text string (text[start:end] == raw_expression).
- Lines: 1-based, counting from the start of the file.
- Columns: 1-based, Unicode code points; '\\n' increments line and resets column to 1.
  '\\r' is counted as a column character (not a line break by itself).
"""
from __future__ import annotations
from dataclasses import dataclass, field

FORMAT = "reference-extraction-v1"
SCHEMA_VERSION = 1
GENERATOR_NAME = "peoplenet-process-extractor"

VALID_STATUSES: frozenset[str] = frozenset({
    "observed", "partially_parsed", "ambiguous", "malformed", "unsupported",
})
VALID_KINDS: frozenset[str] = frozenset({"call"})
VALID_ARG_KINDS: frozenset[str] = frozenset({
    "string_literal", "numeric_literal", "identifier", "expression", "empty",
})
VALID_ENCODING_NAMES: frozenset[str] = frozenset({"utf-8", "utf-8-bom"})
VALID_LINE_ENDINGS: frozenset[str] = frozenset({"lf", "crlf", "mixed", "none"})
VALID_FILE_STATUSES: frozenset[str] = frozenset({"processed", "error"})
VALID_ERROR_CODES: frozenset[str] = frozenset({
    "file_not_found", "hash_mismatch", "decode_error", "unsupported_encoding", "parser_failure",
})
VALID_DIAGNOSTIC_CODES: frozenset[str] = frozenset({
    "unclosed_parenthesis", "unterminated_string", "unexpected_end_of_file",
})


@dataclass
class Argument:
    position: int           # 0-based index in argument list
    raw: str                # literal text from source
    kind: str               # from VALID_ARG_KINDS
    literal_value: str | None   # string_literal: content without quotes; else None
    status: str             # "parsed" | "unparsed"


@dataclass
class FileError:
    code: str               # from VALID_ERROR_CODES
    message: str
    evidence: str | None


@dataclass
class Reference:
    id: str                 # "ref:{sha256}:{start_offset}:{end_offset}"
    kind: str               # "call"
    function_name: str      # "Call"
    status: str             # from VALID_STATUSES
    source_file_id: int
    path: str               # relative path with '/'
    source_file_sha256: str
    start_offset: int       # 0-based, inclusive
    end_offset: int         # 0-based, exclusive; text[start:end] == raw_expression
    line_start: int         # 1-based
    column_start: int       # 1-based
    line_end: int           # 1-based; line of closing ')'
    column_end: int         # 1-based; column of closing ')'
    raw_expression: str     # text[start_offset:end_offset]
    raw_arguments: str      # text between outer parens
    arguments: list[Argument]
    parser_rule: str        # e.g. "ln4_call_v1"
    diagnostics: list[str]  # from VALID_DIAGNOSTIC_CODES


@dataclass
class FileResult:
    path: str
    source_file_id: int
    source_file_sha256: str | None
    encoding: str | None
    line_ending: str | None
    status: str             # from VALID_FILE_STATUSES
    errors: list[FileError] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)


@dataclass
class ExtractionSummary:
    files_total: int
    files_processed: int
    files_with_calls: int
    calls_total: int
    observed: int
    partially_parsed: int
    ambiguous: int
    malformed: int
    unsupported: int
    file_errors: int


@dataclass
class SourceRef:
    sha256: str
    size_bytes: int


@dataclass
class Generator:
    name: str
    version: str


@dataclass
class ReferenceExtraction:
    format: str
    schema_version: int
    generator: Generator
    created_at: str
    source_manifest: SourceRef
    source_index: SourceRef
    summary: ExtractionSummary
    files: list[FileResult]
