from enum import Enum


class Classification(str, Enum):
    STRUCTURED_LN4 = "structured_ln4"
    UNSTRUCTURED_LN4 = "unstructured_ln4"
    METADATA_JSON = "metadata_json"
    M4O_NODE_JSON = "m4o_node_json"
    M4O_ALIAS_JSON = "m4o_alias_json"
    M4O_MAPPING_JSON = "m4o_mapping_json"
    OTHER_SUPPORTED = "other_supported"
    IGNORED = "ignored"
