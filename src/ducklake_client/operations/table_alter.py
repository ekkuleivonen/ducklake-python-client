"""ALTER TABLE helpers for DuckLake-backed tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.operations.base import OperationContext
from ducklake_client.operations.table_names import qualified_table_name, split_table_name
from ducklake_client.schema import ColumnDef

if TYPE_CHECKING:
    import duckdb


def table_add_column(
    context: OperationContext,
    table_name: str,
    column_name: str,
    column: ColumnDef,
    *,
    schema_name: str = "main",
    default_sql: str | None = None,
) -> duckdb.DuckDBPyConnection:
    """Append a column via ``ALTER TABLE ... ADD COLUMN``."""

    if not column_name:
        raise DuckLakeConfigError("column_name must not be empty")
    if not isinstance(column, ColumnDef):
        raise TypeError(f"column must be a ColumnDef, got {type(column).__name__}")

    schema, table = split_table_name(table_name, schema_name=schema_name)
    qualified = qualified_table_name(context.alias, schema, table)
    fragment = column.sql(column_name)
    suffix = f" DEFAULT {default_sql}" if default_sql else ""
    query = f"ALTER TABLE {qualified} ADD COLUMN {fragment}{suffix}"
    try:
        return context.connection.execute(query)
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake table.add_column failed") from exc


def table_drop_column(
    context: OperationContext,
    table_name: str,
    column_name: str,
    *,
    schema_name: str = "main",
) -> duckdb.DuckDBPyConnection:
    """Remove a column via ``ALTER TABLE ... DROP COLUMN``."""

    schema, table = split_table_name(table_name, schema_name=schema_name)
    qualified = qualified_table_name(context.alias, schema, table)
    query = f"ALTER TABLE {qualified} DROP COLUMN {quote_identifier(column_name)}"
    try:
        return context.connection.execute(query)
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake table.drop_column failed") from exc
