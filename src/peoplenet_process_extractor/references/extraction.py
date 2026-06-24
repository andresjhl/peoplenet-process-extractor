"""
High-level extraction service for reference-extraction-v1.

Pipeline:
1. Validate input paths.
2. Load and verify corpus manifest.
3. Hash manifest and index files.
4. Open index SQLite, verify it was built from this manifest.
5. Get all structured_ln4 files from index.
6. For each file: read bytes, hash-check, decode, scan for Call() expressions.
7. Build ReferenceExtraction model.
8. Validate model.
9. Serialize and write atomically.
10. Verify the written artifact.

Individual file errors are recorded as FileError records — they don't abort the run.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from importlib.metadata import version as _pkg_version
    _GENERATOR_VERSION = _pkg_version("peoplenet-process-extractor")
except Exception:
    _GENERATOR_VERSION = "unknown"

from ..corpus.serialization import DeserializationError, deserialize_manifest
from ..corpus.service import verify_corpus
from ..index.validation import validate_index
from ..manifest.hashing import compute_file_hash_and_size
from .models import (
    FORMAT,
    GENERATOR_NAME,
    SCHEMA_VERSION,
    Argument,
    ExtractionSummary,
    FileError,
    FileResult,
    Generator,
    Reference,
    ReferenceExtraction,
    SourceRef,
)
from .scanner import ScanCall, _classify_argument, _split_arguments, scan_text
from .serialization import deserialize_extraction, serialize_extraction
from .validation import validate_extraction_model


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_encoding(raw: bytes) -> str:
    """Detect encoding name from raw bytes."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-bom"
    return "utf-8"


def _detect_line_ending(text: str) -> str:
    """Detect dominant line ending in decoded text."""
    has_crlf = "\r\n" in text
    has_lf = "\n" in text.replace("\r\n", "")
    if has_crlf and has_lf:
        return "mixed"
    if has_crlf:
        return "crlf"
    if has_lf:
        return "lf"
    return "none"


def _get_index_info(
    index_path: Path,
) -> tuple[str, int, list[tuple[int, str, str, int]]]:
    """
    Read index metadata and structured_ln4 file list from SQLite.

    Returns (manifest_sha256, manifest_size, structured_files_list)
    where structured_files_list items are (id, path, sha256, size_bytes).
    """
    con = sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT corpus_manifest_sha256, corpus_manifest_size_bytes FROM index_metadata WHERE id = 1"
        ).fetchone()
        if row is None:
            raise ValueError("index_metadata row not found in index.")
        manifest_sha256, manifest_size = row

        files_rows = con.execute(
            "SELECT id, path, sha256, size_bytes FROM source_files WHERE classification = 'structured_ln4' ORDER BY path"
        ).fetchall()
    finally:
        con.close()

    structured_files = [(r[0], r[1], r[2], r[3]) for r in files_rows]
    return manifest_sha256, manifest_size, structured_files


def _build_arguments(raw_arguments: str) -> list[Argument]:
    """Parse raw_arguments into a list of Argument objects."""
    raw_parts = _split_arguments(raw_arguments)
    args: list[Argument] = []
    for pos, raw in enumerate(raw_parts):
        kind, literal_value = _classify_argument(raw)
        args.append(Argument(
            position=pos,
            raw=raw,
            kind=kind,
            literal_value=literal_value,
            status="parsed",
        ))
    return args


def _scan_call_to_reference(
    call: ScanCall,
    source_file_id: int,
    path: str,
    source_file_sha256: str,
) -> Reference:
    """Convert a ScanCall to a Reference model."""
    ref_id = f"ref:{source_file_sha256}:{call.start_offset}:{call.end_offset}"

    if call.status == "malformed":
        arguments = []
        # Try to parse args even for malformed calls
        try:
            arguments = _build_arguments(call.raw_arguments)
        except Exception:
            pass
        return Reference(
            id=ref_id,
            kind="call",
            function_name="Call",
            status="malformed",
            source_file_id=source_file_id,
            path=path,
            source_file_sha256=source_file_sha256,
            start_offset=call.start_offset,
            end_offset=call.end_offset,
            line_start=call.line_start,
            column_start=call.column_start,
            line_end=call.line_end,
            column_end=call.column_end,
            raw_expression=call.raw_expression,
            raw_arguments=call.raw_arguments,
            arguments=arguments,
            parser_rule="ln4_call_v1",
            diagnostics=list(call.diagnostics),
        )

    # Observed (properly closed)
    arguments = _build_arguments(call.raw_arguments)

    return Reference(
        id=ref_id,
        kind="call",
        function_name="Call",
        status="observed",
        source_file_id=source_file_id,
        path=path,
        source_file_sha256=source_file_sha256,
        start_offset=call.start_offset,
        end_offset=call.end_offset,
        line_start=call.line_start,
        column_start=call.column_start,
        line_end=call.line_end,
        column_end=call.column_end,
        raw_expression=call.raw_expression,
        raw_arguments=call.raw_arguments,
        arguments=arguments,
        parser_rule="ln4_call_v1",
        diagnostics=[],
    )


def _process_file(
    corpus_root: Path,
    file_id: int,
    rel_path: str,
    expected_sha256: str,
    expected_size: int,
) -> FileResult:
    """Process a single structured_ln4 file. Returns FileResult with errors or references."""
    abs_path = corpus_root / rel_path.replace("/", os.sep)

    # Read bytes
    try:
        raw = abs_path.read_bytes()
    except OSError as exc:
        return FileResult(
            path=rel_path,
            source_file_id=file_id,
            source_file_sha256=None,
            encoding=None,
            line_ending=None,
            status="error",
            errors=[FileError(
                code="file_not_found",
                message=f"Cannot read file: {exc}",
                evidence=str(abs_path),
            )],
        )

    # Hash check
    actual_sha256 = _hash_bytes(raw)
    if actual_sha256 != expected_sha256:
        return FileResult(
            path=rel_path,
            source_file_id=file_id,
            source_file_sha256=actual_sha256,
            encoding=None,
            line_ending=None,
            status="error",
            errors=[FileError(
                code="hash_mismatch",
                message=f"SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}",
                evidence=rel_path,
            )],
        )

    # Detect encoding
    encoding_name = _detect_encoding(raw)

    # Decode
    try:
        text = raw.decode("utf-8-sig")  # handles both utf-8 and utf-8-bom
    except UnicodeDecodeError as exc:
        return FileResult(
            path=rel_path,
            source_file_id=file_id,
            source_file_sha256=actual_sha256,
            encoding=encoding_name,
            line_ending=None,
            status="error",
            errors=[FileError(
                code="decode_error",
                message=f"Cannot decode as UTF-8: {exc}",
                evidence=rel_path,
            )],
        )

    # Detect line endings
    line_ending = _detect_line_ending(text)

    # Scan for calls
    try:
        scan_calls = scan_text(text)
    except Exception as exc:
        return FileResult(
            path=rel_path,
            source_file_id=file_id,
            source_file_sha256=actual_sha256,
            encoding=encoding_name,
            line_ending=line_ending,
            status="error",
            errors=[FileError(
                code="parser_failure",
                message=f"Scanner failed: {exc}",
                evidence=rel_path,
            )],
        )

    # Build references
    references = [
        _scan_call_to_reference(call, file_id, rel_path, actual_sha256)
        for call in scan_calls
    ]

    return FileResult(
        path=rel_path,
        source_file_id=file_id,
        source_file_sha256=actual_sha256,
        encoding=encoding_name,
        line_ending=line_ending,
        status="processed",
        errors=[],
        references=references,
    )


def _build_summary(files: list[FileResult]) -> ExtractionSummary:
    """Build ExtractionSummary from file results."""
    files_total = len(files)
    files_processed = sum(1 for f in files if f.status == "processed")
    file_errors = sum(1 for f in files if f.status == "error")
    files_with_calls = sum(1 for f in files if f.status == "processed" and f.references)

    all_refs = [r for f in files for r in f.references]
    calls_total = len(all_refs)

    observed = sum(1 for r in all_refs if r.status == "observed")
    partially_parsed = sum(1 for r in all_refs if r.status == "partially_parsed")
    ambiguous = sum(1 for r in all_refs if r.status == "ambiguous")
    malformed = sum(1 for r in all_refs if r.status == "malformed")
    unsupported = sum(1 for r in all_refs if r.status == "unsupported")

    return ExtractionSummary(
        files_total=files_total,
        files_processed=files_processed,
        files_with_calls=files_with_calls,
        calls_total=calls_total,
        observed=observed,
        partially_parsed=partially_parsed,
        ambiguous=ambiguous,
        malformed=malformed,
        unsupported=unsupported,
        file_errors=file_errors,
    )


def extract_references(
    corpus_root: Path,
    manifest_path: Path,
    index_path: Path,
    output_path: Path,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """
    Extract Call() references from all structured_ln4 files in the corpus.

    Returns (exit_code, messages). exit_code 0 = success.
    """
    messages: list[str] = []

    # Validate input paths
    if not corpus_root.exists() or not corpus_root.is_dir():
        messages.append(f"Error: corpus root '{corpus_root}' is not a directory.")
        return 1, messages

    if not manifest_path.exists():
        messages.append(f"Error: manifest not found: '{manifest_path}'.")
        return 1, messages

    if not index_path.exists():
        messages.append(f"Error: index not found: '{index_path}'.")
        return 1, messages

    if output_path.exists() and not force:
        messages.append(
            f"Error: output already exists: '{output_path}'. Use --force to overwrite."
        )
        return 1, messages

    # Load manifest
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        messages.append(f"Error reading manifest: {exc}")
        return 1, messages

    try:
        manifest, val_errors = deserialize_manifest(manifest_text)
    except DeserializationError as exc:
        messages.append(f"Error: manifest is not valid: {exc}")
        return 1, messages

    if val_errors:
        for err in val_errors:
            messages.append(f"Validation error [{err.code}]: {err.message}")
        messages.append("Error: manifest failed validation.")
        return 1, messages

    # Verify corpus
    verify_code, _diff, verify_msgs = verify_corpus(corpus_root, manifest_path)
    if verify_code != 0:
        messages.append("Error: corpus does not match manifest.")
        for m in verify_msgs:
            messages.append(f"  {m}")
        return 1, messages

    # Hash manifest file
    try:
        manifest_sha256, manifest_size = compute_file_hash_and_size(manifest_path)
    except OSError as exc:
        messages.append(f"Error hashing manifest: {exc}")
        return 1, messages

    # Hash index file
    try:
        index_sha256, index_size = compute_file_hash_and_size(index_path)
    except OSError as exc:
        messages.append(f"Error hashing index: {exc}")
        return 1, messages

    # Full structural validation of the index (integrity, schema, counters, manifest correspondence)
    index_val_errors = validate_index(
        db_path=index_path,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
    )
    if index_val_errors:
        for err in index_val_errors:
            messages.append(f"Error: index validation failed: {err}")
        return 1, messages

    # Get structured_ln4 files from the (now-validated) index
    try:
        _idx_manifest_sha256, _idx_manifest_size, structured_files = _get_index_info(index_path)
    except Exception as exc:
        messages.append(f"Error reading index: {exc}")
        return 1, messages

    # Process each structured_ln4 file
    file_results: list[FileResult] = []
    for file_id, rel_path, expected_sha256, expected_size in structured_files:
        result = _process_file(corpus_root, file_id, rel_path, expected_sha256, expected_size)
        file_results.append(result)

    # Sort files by path (should already be sorted from index, but ensure)
    file_results.sort(key=lambda f: f.path)

    # Sort references within each file by start_offset, end_offset
    for fr in file_results:
        fr.references.sort(key=lambda r: (r.start_offset, r.end_offset))

    # Build summary
    summary = _build_summary(file_results)

    # Timestamp
    ts = now or datetime.now(timezone.utc)
    created_at = ts.isoformat()

    # Build extraction model
    extraction = ReferenceExtraction(
        format=FORMAT,
        schema_version=SCHEMA_VERSION,
        generator=Generator(name=GENERATOR_NAME, version=_GENERATOR_VERSION),
        created_at=created_at,
        source_manifest=SourceRef(sha256=manifest_sha256, size_bytes=manifest_size),
        source_index=SourceRef(sha256=index_sha256, size_bytes=index_size),
        summary=summary,
        files=file_results,
    )

    # Validate model
    val_errors = validate_extraction_model(extraction)
    if val_errors:
        for err in val_errors:
            messages.append(f"Error: model validation failed: {err}")
        return 1, messages

    # Serialize
    try:
        text = serialize_extraction(extraction)
    except Exception as exc:
        messages.append(f"Error serializing extraction: {exc}")
        return 1, messages

    # Write atomically
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        fd, tmp_str = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=".reference-extraction-",
            suffix=".tmp",
        )
        os.close(fd)
        tmp_path = Path(tmp_str)
        tmp_path.write_bytes(text.encode("utf-8"))

        # Verify temp file
        verify_text = tmp_path.read_text(encoding="utf-8")
        verify_extraction_obj = deserialize_extraction(verify_text)
        verify_errors = validate_extraction_model(verify_extraction_obj)
        if verify_errors:
            for err in verify_errors:
                messages.append(f"Error: temp file validation failed: {err}")
            return 1, messages

        # Publish
        os.replace(tmp_path, output_path)
        tmp_path = None

    except Exception as exc:
        messages.append(f"Error writing extraction: {exc}")
        return 1, messages
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    n_refs = summary.calls_total
    n_files = summary.files_processed
    messages.append(f"Reference extraction written to '{output_path}'.")
    messages.append(f"  {n_files} files processed, {n_refs} calls extracted.")
    return 0, messages
