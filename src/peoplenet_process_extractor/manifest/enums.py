from enum import Enum


class RunStatus(str, Enum):
    PREPARED = "prepared"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceKind(str, Enum):
    SCENARIO = "scenario"
    FRONTEND_CALL = "frontend_call"
    DATABASE_TRACE = "database_trace"
    QUERY_RESULTS = "query_results"
    LN4_SOURCE = "ln4_source"
    MANUAL_INPUT = "manual_input"
    CONFIGURATION = "configuration"
    OTHER = "other"


class ArtifactKind(str, Enum):
    SCENARIO = "scenario"
    MIGRATION_REPORT = "migration_report"
    CLEAN_TRACE = "clean_trace"
    WRITES_TRACE = "writes_trace"
    INTERMEDIATE_MODEL = "intermediate_model"
    VALIDATION_REPORT = "validation_report"
    MARKDOWN = "markdown"
    OTHER = "other"


class ArtifactStatus(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    FAILED = "failed"
    MISSING = "missing"


class EventType(str, Enum):
    PREPARED = "prepared"
    STARTED = "started"
    ARTIFACT_GENERATED = "artifact_generated"
    WARNING = "warning"
    ERROR = "error"
    FINISHED = "finished"
