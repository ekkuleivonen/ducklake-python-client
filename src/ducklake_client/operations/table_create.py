"""Create DuckLake tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, template
from ducklake_client.schema import ColumnDef

if TYPE_CHECKING:
    import duckdb


def table_create(
    context: OperationContext,
    name: str,
    *,
    schema_name: str = "main",
    if_not_exists: bool = True,
    **columns: ColumnDef,
) -> duckdb.DuckDBPyConnection:
    if not columns:
        raise DuckLakeConfigError("table.create requires at least one column")
    for column_name, column in columns.items():
        if not isinstance(column, ColumnDef):
            raise TypeError(f"column {column_name!r} must be a ColumnDef")

    query = template("table_create.sql").format(
        if_not_exists="IF NOT EXISTS " if if_not_exists else "",
        table_name=_qualified_table_name(context.alias, schema_name, name),
        columns=",\n    ".join(column.sql(column_name) for column_name, column in columns.items()),
    )
    return context.connection.execute(query)


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
