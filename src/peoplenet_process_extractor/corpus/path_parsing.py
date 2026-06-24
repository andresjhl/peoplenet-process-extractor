from .enums import Classification
from .models import Ln4Structure, M4oStructure

# Expected path depth for a fully structured PeopleNet LN4 file (number of parts):
# <source_root> / NODE STRUCTURE / <meta4object> / ITEM / <item_type> / <item_name> / RULES / <rule_file>.ln4
_STRUCTURED_DEPTH = 8
_NODE_STRUCTURE = "NODE STRUCTURE"
_ITEM = "ITEM"
_RULES = "RULES"

# META4OBJECT sub-pattern labels.
_META4OBJECT = "META4OBJECT"
_M4O_NODE = "NODE"
_M4O_ALIAS = "M4O ALIAS RESOLUTION"
_M4O_MAPPING = "MAPPING META4OBJECT"
# Expected depth for M4O file entries (parts count):
# <source_root> / META4OBJECT / <ID_T3> / <PATTERN> / <ID_NODE_or_ID_T3> / <file>.json
_M4O_DEPTH = 6


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


def parse_m4o_path(
    rel_path: str,
) -> tuple[Classification, M4oStructure | None, list[str]]:
    """
    Parse a corpus-relative path for META4OBJECT resource patterns.

    Returns (classification, m4o_structure, warnings):
    - For non-META4OBJECT paths: (OTHER_SUPPORTED, None, []).
    - For valid M4O JSON paths: (M4O_*_JSON, M4oStructure, []).
    - For out-of-scope META4OBJECT paths: (OTHER_SUPPORTED, None, []).
    - For malformed known-pattern paths with .json extension: (OTHER_SUPPORTED, None, [warning]).

    Warnings use stable codes: malformed_m4o_node_path, malformed_m4o_alias_path,
    malformed_m4o_mapping_path.

    Non-.json files under META4OBJECT never receive M4O classifications or warnings —
    they are silently classified as other_supported.
    """
    parts = normalize_path(rel_path).split("/")

    # Must have at least source_root/META4OBJECT/...
    if len(parts) < 2 or parts[1] != _META4OBJECT:
        return Classification.OTHER_SUPPORTED, None, []

    filename = parts[-1]
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    is_json = ext == ".json"

    # Need source_root/META4OBJECT/ID_T3/PATTERN/...
    if len(parts) < 4:
        return Classification.OTHER_SUPPORTED, None, []

    id_t3 = parts[2]
    pattern = parts[3]

    if pattern == _M4O_NODE:
        return _parse_m4o_node(parts, id_t3, is_json, "malformed_m4o_node_path")
    if pattern == _M4O_ALIAS:
        return _parse_m4o_node(parts, id_t3, is_json, "malformed_m4o_alias_path",
                               cls_valid=Classification.M4O_ALIAS_JSON)
    if pattern == _M4O_MAPPING:
        return _parse_m4o_mapping(parts, id_t3, is_json)

    # Unknown sub-pattern — out of scope, no warning.
    return Classification.OTHER_SUPPORTED, None, []


def _parse_m4o_node(
    parts: list[str],
    id_t3: str,
    is_json: bool,
    malformed_code: str,
    cls_valid: Classification = Classification.M4O_NODE_JSON,
) -> tuple[Classification, M4oStructure | None, list[str]]:
    """
    Shared logic for NODE and M4O ALIAS RESOLUTION patterns.

    Expected depth: source_root / META4OBJECT / ID_T3 / PATTERN / ID_NODE / file.json
    """
    if not is_json:
        return Classification.OTHER_SUPPORTED, None, []
    if not id_t3.strip():
        return Classification.OTHER_SUPPORTED, None, [malformed_code]
    if len(parts) != _M4O_DEPTH:
        return Classification.OTHER_SUPPORTED, None, [malformed_code]
    id_node = parts[4]
    if not id_node.strip():
        return Classification.OTHER_SUPPORTED, None, [malformed_code]
    return cls_valid, M4oStructure(id_t3=id_t3, id_node=id_node), []


def _parse_m4o_mapping(
    parts: list[str],
    id_t3: str,
    is_json: bool,
) -> tuple[Classification, M4oStructure | None, list[str]]:
    """
    Logic for MAPPING META4OBJECT pattern.

    Expected depth: source_root / META4OBJECT / ID_T3 / MAPPING META4OBJECT / ID_T3 / file.json
    The inner ID_T3 (parts[4]) must equal the outer ID_T3 (parts[2]).
    """
    if not is_json:
        return Classification.OTHER_SUPPORTED, None, []
    if not id_t3.strip():
        return Classification.OTHER_SUPPORTED, None, ["malformed_m4o_mapping_path"]
    if len(parts) != _M4O_DEPTH:
        return Classification.OTHER_SUPPORTED, None, ["malformed_m4o_mapping_path"]
    id_t3_inner = parts[4]
    if not id_t3_inner.strip():
        return Classification.OTHER_SUPPORTED, None, ["malformed_m4o_mapping_path"]
    if id_t3_inner != id_t3:
        return Classification.OTHER_SUPPORTED, None, ["malformed_m4o_mapping_path"]
    return Classification.M4O_MAPPING_JSON, M4oStructure(id_t3=id_t3, id_node=None), []
