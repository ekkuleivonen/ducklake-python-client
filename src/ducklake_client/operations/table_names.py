"""Shared table-name handling for table operations."""

from __future__ import annotations

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError


def split_table_name(name: str, *, schema_name: str) -> tuple[str, str]:
    if not name:
        raise DuckLakeConfigError("table name must not be empty")
    if not schema_name:
        raise DuckLakeConfigError("schema name must not be empty")

    parts = name.split(".")
    if len(parts) == 1:
        return schema_name, parts[0]
    if len(parts) == 2:
        if schema_name != "main":
            raise DuckLakeConfigError("pass either 'schema.table' or schema_name=, not both")
        schema, table = parts
        if schema and table:
            return schema, table
    raise DuckLakeConfigError(f"invalid table name: {name!r}")


def qualified_table_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(quote_identifier(part) for part in (catalog, schema, table))
