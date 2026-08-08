"""Dataset ingestion: parsing, validation and persistence."""

from app.services.ingestion.parser import ParsedFile, parse_upload
from app.services.ingestion.service import IngestionService
from app.services.ingestion.spec import ENTITY_SPECS, EntitySpec, get_spec
from app.services.ingestion.validators import ValidationOutcome, validate_frame

__all__ = [
    "ENTITY_SPECS",
    "EntitySpec",
    "IngestionService",
    "ParsedFile",
    "ValidationOutcome",
    "get_spec",
    "parse_upload",
    "validate_frame",
]
