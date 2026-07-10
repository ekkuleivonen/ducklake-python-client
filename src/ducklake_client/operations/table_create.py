"""Create DuckLake tables."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ducklake_client.config import quote_literal
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, execute, template
from ducklake_client.operations.table_names import qualified_table_name, split_table_name
from ducklake_client.schema import ColumnDef

if TYPE_CHECKING:
    import duckdb


def table_create(
    context: OperationContext,
    table_name: str,
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
        table_name=_qualified_name(context.alias, schema_name, table_name),
        columns=",\n    ".join(column.sql(column_name) for column_name, column in columns.items()),
    )
    return execute(context, query, operation="table.create")


def table_create_from_csv(
    context: OperationContext,
    name: str,
    source: str | Path,
    *,
    schema_name: str = "main",
    if_not_exists: bool = True,
) -> duckdb.DuckDBPyConnection:
    if not str(source):
        raise DuckLakeConfigError("CSV source must not be empty")

    query = template("table_create_from_csv.sql").format(
        if_not_exists="IF NOT EXISTS " if if_not_exists else "",
        table_name=_qualified_name(context.alias, schema_name, name),
        source=quote_literal(source),
    )
    return execute(context, query, operation="table.create_from_csv")


def _qualified_name(alias: str, schema_name: str, name: str) -> str:
    schema, table = split_table_name(name, schema_name=schema_name)
    return qualified_table_name(alias, schema, table)
