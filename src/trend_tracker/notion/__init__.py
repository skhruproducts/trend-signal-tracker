"""Notion template as code: the tracker's five linked databases, defined in schema.json."""

from .builder import BuiltDatabase, build
from .client import FakeClient, NotionClient, NotionError
from .schema import DEFAULT_SCHEMA, SchemaError, check, glossary, load_schema, validate

__all__ = [
    "BuiltDatabase", "DEFAULT_SCHEMA", "FakeClient", "NotionClient", "NotionError", "SchemaError",
    "build", "check", "glossary", "load_schema", "validate",
]
