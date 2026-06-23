from enum import Enum


class Source(str, Enum):
    FRONTEND_CALL = "frontend_call"
    SQL_QUERY = "sql_query"
    DATABASE_TRACE = "database_trace"
    SOURCE_CODE = "source_code"
    MANUAL_DERIVATION = "manual_derivation"
    DEFAULT = "default"
    UNKNOWN = "unknown"


class Status(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
