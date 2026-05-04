"""Implementation for creating DuckLake tables."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.schema import ColumnDef


def create_table(
    client: Any,
    table_name: str,
    schema_name: str = "main",
    if_not_exists: bool = True,
    **columns: ColumnDef,
) -> Any:
    """Create a table in the attached DuckLake catalog."""

    if not columns:
        raise DuckLakeConfigError("create_table requires at least one column")
    for column_name, column in columns.items():
        if not isinstance(column, ColumnDef):
            raise TypeError(f"column {column_name!r} must be a ColumnDef")

    qualified_table_name = _qualified_table_name(client.alias, schema_name, table_name)
    rendered_columns = ",\n    ".join(
        column.sql(column_name) for column_name, column in columns.items()
    )
    sql = _template().format(
        if_not_exists="IF NOT EXISTS " if if_not_exists else "",
        table_name=qualified_table_name,
        columns=rendered_columns,
    )
    return client.execute(sql)


def _qualified_table_name(alias: str, schema_name: str, name: str) -> str:
    if not name:
        raise DuckLakeConfigError("table name must not be empty")
    if not schema_name:
        raise DuckLakeConfigError("schema name must not be empty")

    parts = name.split(".")
    if len(parts) == 1:
        schema = schema_name
        table = parts[0]
    elif len(parts) == 2:
        schema, table = parts
    else:
        raise DuckLakeConfigError(f"invalid table name: {name!r}")

    if not schema or not table:
        raise DuckLakeConfigError(f"invalid table name: {name!r}")
    return ".".join(quote_identifier(part) for part in (alias, schema, table))


def _template() -> str:
    return (
        files("ducklake_client.methods.create_table")
        .joinpath("template.sql")
        .read_text(encoding="utf-8")
    )
