"""
Validation for reference-extraction-v1 models and artifacts.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .models import (
    FORMAT,
    GENERATOR_NAME,
    SCHEMA_VERSION,
    VALID_ARG_KINDS,
    VALID_ERROR_CODES,
    VALID_FILE_STATUSES,
    VALID_KINDS,
    VALID_STATUSES,
    ReferenceExtraction,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REF_ID_RE = re.compile(r"^ref:[0-9a-f]{64}:\d+:\d+$")

_SUMMARY_FIELDS = (
    "files_total", "files_processed", "files_with_calls", "calls_total",
    "observed", "partially_parsed", "ambiguous", "malformed", "unsupported", "file_errors",
)


def validate_extraction_model(extraction: ReferenceExtraction) -> list[str]:
    """
    Validate the in-memory model.

    Returns a list of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Format and version
    if extraction.format != FORMAT:
        errors.append(f"Invalid format: expected '{FORMAT}', got '{extraction.format}'.")
    if extraction.schema_version != SCHEMA_VERSION:
        errors.append(
            f"Invalid schema_version: expected {SCHEMA_VERSION}, got {extraction.schema_version}."
        )

    # Generator
    if not extraction.generator.name:
        errors.append("generator.name must not be empty.")
    if not extraction.generator.version:
        errors.append("generator.version must not be empty.")

    # created_at
    if not extraction.created_at:
        errors.append("created_at must not be empty.")

    # source_manifest
    if not _SHA256_RE.match(extraction.source_manifest.sha256 or ""):
        errors.append(f"source_manifest.sha256 is not a valid hex string: '{extraction.source_manifest.sha256}'.")
    if extraction.source_manifest.size_bytes < 0:
        errors.append(f"source_manifest.size_bytes is negative: {extraction.source_manifest.size_bytes}.")

    # source_index
    if not _SHA256_RE.match(extraction.source_index.sha256 or ""):
        errors.append(f"source_index.sha256 is not a valid hex string: '{extraction.source_index.sha256}'.")
    if extraction.source_index.size_bytes < 0:
        errors.append(f"source_index.size_bytes is negative: {extraction.source_index.size_bytes}.")

    # Files sorted by path
    paths = [f.path for f in extraction.files]
    if paths != sorted(paths):
        errors.append("files must be sorted by path.")

    # File-level checks
    seen_ref_ids: set[str] = set()
    actual_calls_total = 0
    actual_observed = 0
    actual_partially_parsed = 0
    actual_ambiguous = 0
    actual_malformed = 0
    actual_unsupported = 0
    actual_files_processed = 0
    actual_file_errors = 0
    actual_files_with_calls = 0

    for fi, file_result in enumerate(extraction.files):
        if file_result.status not in VALID_FILE_STATUSES:
            errors.append(f"files[{fi}].status invalid: '{file_result.status}'.")

        if file_result.status == "processed":
            actual_files_processed += 1
            if file_result.references:
                actual_files_with_calls += 1
        elif file_result.status == "error":
            actual_file_errors += 1

        # Check file errors
        for ei, ferr in enumerate(file_result.errors):
            if ferr.code not in VALID_ERROR_CODES:
                errors.append(f"files[{fi}].errors[{ei}].code invalid: '{ferr.code}'.")

        # Check references
        for ri, ref in enumerate(file_result.references):
            if ref.kind not in VALID_KINDS:
                errors.append(f"files[{fi}].references[{ri}].kind invalid: '{ref.kind}'.")
            if ref.status not in VALID_STATUSES:
                errors.append(f"files[{fi}].references[{ri}].status invalid: '{ref.status}'.")

            # Offsets
            if ref.start_offset < 0:
                errors.append(f"files[{fi}].references[{ri}].start_offset negative: {ref.start_offset}.")
            if ref.end_offset < 0:
                errors.append(f"files[{fi}].references[{ri}].end_offset negative: {ref.end_offset}.")
            if ref.start_offset >= ref.end_offset:
                errors.append(
                    f"files[{fi}].references[{ri}]: start_offset ({ref.start_offset}) >= end_offset ({ref.end_offset})."
                )

            # Reference ID uniqueness
            if ref.id in seen_ref_ids:
                errors.append(f"Duplicate reference id: '{ref.id}'.")
            seen_ref_ids.add(ref.id)

            # ID formula check
            expected_id = f"ref:{ref.source_file_sha256}:{ref.start_offset}:{ref.end_offset}"
            if ref.id != expected_id:
                errors.append(
                    f"files[{fi}].references[{ri}].id mismatch: "
                    f"expected '{expected_id}', got '{ref.id}'."
                )

            # Count by status
            actual_calls_total += 1
            if ref.status == "observed":
                actual_observed += 1
            elif ref.status == "partially_parsed":
                actual_partially_parsed += 1
            elif ref.status == "ambiguous":
                actual_ambiguous += 1
            elif ref.status == "malformed":
                actual_malformed += 1
            elif ref.status == "unsupported":
                actual_unsupported += 1

            # Argument kinds
            for ai, arg in enumerate(ref.arguments):
                if arg.kind not in VALID_ARG_KINDS:
                    errors.append(
                        f"files[{fi}].references[{ri}].arguments[{ai}].kind invalid: '{arg.kind}'."
                    )

    # Summary counter checks
    s = extraction.summary
    if s.files_total != len(extraction.files):
        errors.append(
            f"summary.files_total={s.files_total} but len(files)={len(extraction.files)}."
        )
    if s.files_processed != actual_files_processed:
        errors.append(
            f"summary.files_processed={s.files_processed} but actual={actual_files_processed}."
        )
    if s.files_with_calls != actual_files_with_calls:
        errors.append(
            f"summary.files_with_calls={s.files_with_calls} but actual={actual_files_with_calls}."
        )
    if s.calls_total != actual_calls_total:
        errors.append(f"summary.calls_total={s.calls_total} but actual={actual_calls_total}.")
    if s.observed != actual_observed:
        errors.append(f"summary.observed={s.observed} but actual={actual_observed}.")
    if s.partially_parsed != actual_partially_parsed:
        errors.append(f"summary.partially_parsed={s.partially_parsed} but actual={actual_partially_parsed}.")
    if s.ambiguous != actual_ambiguous:
        errors.append(f"summary.ambiguous={s.ambiguous} but actual={actual_ambiguous}.")
    if s.malformed != actual_malformed:
        errors.append(f"summary.malformed={s.malformed} but actual={actual_malformed}.")
    if s.unsupported != actual_unsupported:
        errors.append(f"summary.unsupported={s.unsupported} but actual={actual_unsupported}.")
    if s.file_errors != actual_file_errors:
        errors.append(f"summary.file_errors={s.file_errors} but actual={actual_file_errors}.")

    return errors


def _parse_utc_created_at(value: str) -> datetime | None:
    """
    Parse an ISO-8601 UTC timestamp string.

    Returns the datetime on success, None if invalid or non-UTC.
    Accepts both '+00:00' and 'Z' suffixes (Python 3.11+ fromisoformat handles Z).
    """
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        return None
    return dt


def verify_extraction(
    corpus_root: Path,
    manifest_path: Path,
    index_path: Path,
    extraction_path: Path,
) -> tuple[int, list[str]]:
    """
    Full physical verification of the reference extraction artifact against its sources.

    Re-extracts all files in memory and compares every deterministic field
    (root, file-level, reference-level, argument-level) against the stored artifact.

    Returns (exit_code, messages).
    """
    messages: list[str] = []

    # --- Load artifact ---
    if not extraction_path.exists():
        messages.append(f"Error: extraction file not found: '{extraction_path}'.")
        return 1, messages

    try:
        extraction_text = extraction_path.read_text(encoding="utf-8")
    except OSError as exc:
        messages.append(f"Error reading extraction: {exc}")
        return 1, messages

    from .serialization import DeserializationError as RefDeserError, deserialize_extraction
    try:
        extraction = deserialize_extraction(extraction_text)
    except (ValueError, RefDeserError) as exc:
        messages.append(f"Error: extraction is not valid: {exc}")
        return 1, messages

    if extraction.format != FORMAT:
        messages.append(f"Error: unsupported format '{extraction.format}'.")
        return 1, messages
    if extraction.schema_version != SCHEMA_VERSION:
        messages.append(f"Error: unsupported schema_version {extraction.schema_version}.")
        return 1, messages

    # --- Validate created_at is a parseable UTC ISO-8601 timestamp ---
    stored_created_at_dt = _parse_utc_created_at(extraction.created_at)
    if stored_created_at_dt is None:
        messages.append(
            f"Error: created_at must be a UTC ISO-8601 timestamp "
            f"(e.g. 2026-06-24T12:00:00+00:00 or 2026-06-24T12:00:00Z), "
            f"got: '{extraction.created_at}'."
        )
        return 1, messages

    # --- Manifest provenance ---
    if not manifest_path.exists():
        messages.append(f"Error: manifest not found: '{manifest_path}'.")
        return 1, messages

    from ..manifest.hashing import compute_file_hash_and_size
    try:
        manifest_sha256, manifest_size = compute_file_hash_and_size(manifest_path)
    except OSError as exc:
        messages.append(f"Error hashing manifest: {exc}")
        return 1, messages

    if extraction.source_manifest.sha256 != manifest_sha256:
        messages.append(
            f"Error: source_manifest.sha256 mismatch: "
            f"stored={extraction.source_manifest.sha256}, actual={manifest_sha256}."
        )
        return 1, messages

    if extraction.source_manifest.size_bytes != manifest_size:
        messages.append(
            f"Error: source_manifest.size_bytes mismatch: "
            f"stored={extraction.source_manifest.size_bytes}, actual={manifest_size}."
        )
        return 1, messages

    # --- Index provenance ---
    if not index_path.exists():
        messages.append(f"Error: index not found: '{index_path}'.")
        return 1, messages

    try:
        index_sha256, index_size = compute_file_hash_and_size(index_path)
    except OSError as exc:
        messages.append(f"Error hashing index: {exc}")
        return 1, messages

    if extraction.source_index.sha256 != index_sha256:
        messages.append(
            f"Error: source_index.sha256 mismatch: "
            f"stored={extraction.source_index.sha256}, actual={index_sha256}."
        )
        return 1, messages

    if extraction.source_index.size_bytes != index_size:
        messages.append(
            f"Error: source_index.size_bytes mismatch: "
            f"stored={extraction.source_index.size_bytes}, actual={index_size}."
        )
        return 1, messages

    # --- Load manifest and verify corpus ---
    from ..corpus.serialization import DeserializationError, deserialize_manifest
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest, val_errors = deserialize_manifest(manifest_text)
    except (DeserializationError, OSError) as exc:
        messages.append(f"Error loading manifest: {exc}")
        return 1, messages

    if val_errors:
        messages.append("Error: manifest failed validation.")
        return 1, messages

    from ..corpus.service import verify_corpus
    verify_code, _diff, verify_msgs = verify_corpus(corpus_root, manifest_path)
    if verify_code != 0:
        messages.append("Error: corpus does not match manifest.")
        for m in verify_msgs:
            messages.append(f"  {m}")
        return 1, messages

    # --- Full structural validation of the index ---
    from ..index.validation import validate_index
    index_val_errors = validate_index(
        db_path=index_path,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
    )
    if index_val_errors:
        for err in index_val_errors:
            messages.append(f"Error: index validation: {err}")
        return 1, messages

    # --- Get structured files from index and build complete re-extraction ---
    # Lazy imports avoid circular dependency (extraction.py imports validate_extraction_model).
    from .extraction import _build_summary, _get_index_info, _process_file, _GENERATOR_VERSION
    try:
        _idx_sha256, _idx_size, structured_files_list = _get_index_info(index_path)
    except Exception as exc:
        messages.append(f"Error reading index: {exc}")
        return 1, messages

    # Re-extract ALL structured files upfront (including potential error files).
    re_extracted_files: dict[str, object] = {}
    for file_id, rel_path, expected_sha256, expected_size in structured_files_list:
        re_extracted_files[rel_path] = _process_file(
            corpus_root, file_id, rel_path, expected_sha256, expected_size
        )

    # --- Coverage check ---
    extraction_paths = {f.path for f in extraction.files}

    missing = set(re_extracted_files.keys()) - extraction_paths
    for p in sorted(missing):
        messages.append(f"Error: structured_ln4 file not in extraction: '{p}'.")

    extra = extraction_paths - set(re_extracted_files.keys())
    for p in sorted(extra):
        messages.append(f"Error: extraction file not in index: '{p}'.")

    if missing or extra:
        return 1, messages

    if len(extraction_paths) != len(extraction.files):
        messages.append("Error: duplicate paths in extraction files.")
        return 1, messages

    # --- Compare generator fields ---
    if extraction.generator.name != GENERATOR_NAME:
        messages.append(
            f"Error: generator.name mismatch: "
            f"stored={extraction.generator.name!r}, expected={GENERATOR_NAME!r}."
        )
    if extraction.generator.version != _GENERATOR_VERSION:
        messages.append(
            f"Error: generator.version mismatch: "
            f"stored={extraction.generator.version!r}, expected={_GENERATOR_VERSION!r}."
        )

    # --- Compare summary against re-extracted result ---
    expected_summary = _build_summary(list(re_extracted_files.values()))
    for field in _SUMMARY_FIELDS:
        sv = getattr(extraction.summary, field)
        ev = getattr(expected_summary, field)
        if sv != ev:
            messages.append(
                f"Error: summary.{field} mismatch: stored={sv}, re-extracted={ev}."
            )

    # --- Compare each file: ALL fields including source_file_id and errors ---
    for stored_file in extraction.files:
        rel_path = stored_file.path
        if rel_path not in re_extracted_files:
            continue  # already reported as extra

        re_file = re_extracted_files[rel_path]
        ctx = f"files['{rel_path}']"

        # All file-level deterministic fields (including source_file_id, now also errors)
        for field in ("source_file_id", "source_file_sha256", "encoding", "line_ending", "status"):
            sv = getattr(stored_file, field)
            rv = getattr(re_file, field)
            if sv != rv:
                messages.append(
                    f"Error: {ctx}.{field} mismatch: stored={sv!r}, re-extracted={rv!r}."
                )

        # Errors list: compare count first, then field-by-field
        if stored_file.errors != re_file.errors:
            if len(stored_file.errors) != len(re_file.errors):
                messages.append(
                    f"Error: {ctx}.errors count mismatch: "
                    f"stored={len(stored_file.errors)}, re-extracted={len(re_file.errors)}."
                )
            else:
                for i, (se, re_e) in enumerate(zip(stored_file.errors, re_file.errors)):
                    for field in ("code", "message", "evidence"):
                        sv = getattr(se, field)
                        rv = getattr(re_e, field)
                        if sv != rv:
                            messages.append(
                                f"Error: {ctx}.errors[{i}].{field} mismatch: "
                                f"stored={sv!r}, re-extracted={rv!r}."
                            )

        # Reference comparison only when both are processed
        both_processed = (
            stored_file.status == "processed" and re_file.status == "processed"
        )
        if not both_processed:
            if len(stored_file.references) != len(re_file.references):
                messages.append(
                    f"Error: {ctx} reference count mismatch: "
                    f"stored={len(stored_file.references)}, re-extracted={len(re_file.references)}."
                )
            continue

        # Reference count: detects removed or added references
        if len(stored_file.references) != len(re_file.references):
            messages.append(
                f"Error: {ctx} reference count mismatch: "
                f"stored={len(stored_file.references)}, re-extracted={len(re_file.references)}."
            )
            continue

        # Per-reference field comparison
        for i, (stored_ref, re_ref) in enumerate(
            zip(stored_file.references, re_file.references)
        ):
            ref_ctx = f"{ctx}.references[{i}]"

            for field in (
                "id", "kind", "function_name", "status", "source_file_id", "path",
                "source_file_sha256", "start_offset", "end_offset",
                "line_start", "column_start", "line_end", "column_end",
                "raw_expression", "raw_arguments", "parser_rule",
            ):
                sv = getattr(stored_ref, field)
                rv = getattr(re_ref, field)
                if sv != rv:
                    messages.append(
                        f"Error: {ref_ctx}.{field} mismatch: "
                        f"stored={sv!r}, re-extracted={rv!r}."
                    )

            if stored_ref.diagnostics != re_ref.diagnostics:
                messages.append(
                    f"Error: {ref_ctx}.diagnostics mismatch: "
                    f"stored={stored_ref.diagnostics!r}, re-extracted={re_ref.diagnostics!r}."
                )

            # Per-argument comparison
            if len(stored_ref.arguments) != len(re_ref.arguments):
                messages.append(
                    f"Error: {ref_ctx} argument count mismatch: "
                    f"stored={len(stored_ref.arguments)}, re-extracted={len(re_ref.arguments)}."
                )
            else:
                for j, (stored_arg, re_arg) in enumerate(
                    zip(stored_ref.arguments, re_ref.arguments)
                ):
                    arg_ctx = f"{ref_ctx}.arguments[{j}]"
                    for field in ("position", "raw", "kind", "literal_value", "status"):
                        sv = getattr(stored_arg, field)
                        rv = getattr(re_arg, field)
                        if sv != rv:
                            messages.append(
                                f"Error: {arg_ctx}.{field} mismatch: "
                                f"stored={sv!r}, re-extracted={rv!r}."
                            )

    # --- Final model consistency check ---
    model_errors = validate_extraction_model(extraction)
    if model_errors:
        for err in model_errors:
            messages.append(f"Error: {err}")
        return 1, messages

    if messages:
        return 1, messages

    n_files = len([f for f in extraction.files if f.status == "processed"])
    n_refs = extraction.summary.calls_total
    messages.append("Reference extraction is valid.")
    messages.append(f"  {n_files} files verified, {n_refs} references checked.")
    return 0, messages
