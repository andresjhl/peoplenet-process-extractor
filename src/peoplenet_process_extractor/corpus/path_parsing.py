from .models import Ln4Structure

# Expected path depth for a fully structured PeopleNet LN4 file (number of parts):
# <source_root> / NODE STRUCTURE / <meta4object> / ITEM / <item_type> / <item_name> / RULES / <rule_file>.ln4
_STRUCTURED_DEPTH = 8
_NODE_STRUCTURE = "NODE STRUCTURE"
_ITEM = "ITEM"
_RULES = "RULES"


def normalize_path(path: str) -> str:
    """Normalize OS path separators to forward slashes."""
    return path.replace("\\", "/")


def parse_rule_filename(filename: str) -> tuple[str | None, str | None, list[str]]:
    """
    Parse a rule filename of the form <name>#<rule_id>#<rule_date>.ln4.

    Returns (rule_id, rule_date, warnings).  rule_id and rule_date are None
    when the format does not match; a warning is added in that case.
    """
    warnings: list[str] = []
    stem = filename
    if stem.lower().endswith(".ln4"):
        stem = stem[:-4]

    parts = stem.split("#")
    if len(parts) == 3:
        # Normal: <name>#<rule_id>#<rule_date>
        return parts[1], parts[2], warnings
    if len(parts) == 1:
        warnings.append(
            f"Rule file '{filename}' has no '#' separators; rule_id and rule_date unavailable."
        )
    else:
        warnings.append(
            f"Rule file '{filename}' has unexpected '#' count ({len(parts) - 1}); "
            "rule_id and rule_date unavailable."
        )
    return None, None, warnings


def parse_peoplenet_path(
    rel_path: str,
) -> tuple[str | None, Ln4Structure | None, list[str]]:
    """
    Parse a corpus-relative path (using '/' separators) to extract PeopleNet structure.

    Returns (source_root, structure, warnings):
    - source_root: first path component, or None if the file is at the corpus root.
    - structure: Ln4Structure if the path matches the full structured pattern, else None.
    - warnings: non-fatal issues found during parsing.

    The recognized pattern is exactly 8 path components:
        <source_root>/NODE STRUCTURE/<meta4object>/ITEM/<item_type>/<item_name>/RULES/<rule_file>.ln4
    """
    warnings: list[str] = []
    parts = normalize_path(rel_path).split("/")

    if len(parts) < 2:
        # File sits at the corpus root — no source root, no structure.
        return None, None, warnings

    source_root = parts[0]

    if len(parts) != _STRUCTURED_DEPTH:
        return source_root, None, warnings

    if parts[1] != _NODE_STRUCTURE:
        return source_root, None, warnings

    meta4object = parts[2]

    if parts[3] != _ITEM:
        return source_root, None, warnings

    item_type = parts[4]
    item_name = parts[5]

    if parts[6] != _RULES:
        return source_root, None, warnings

    rule_file = parts[7]
    rule_id, rule_date, rule_warnings = parse_rule_filename(rule_file)
    warnings.extend(rule_warnings)

    structure = Ln4Structure(
        meta4object=meta4object,
        item_type=item_type,
        item_name=item_name,
        rule_id=rule_id,
        rule_date=rule_date,
    )
    return source_root, structure, warnings
