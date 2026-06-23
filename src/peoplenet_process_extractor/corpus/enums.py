from enum import Enum


class Classification(str, Enum):
    STRUCTURED_LN4 = "structured_ln4"
    UNSTRUCTURED_LN4 = "unstructured_ln4"
    METADATA_JSON = "metadata_json"
    OTHER_SUPPORTED = "other_supported"
    IGNORED = "ignored"
