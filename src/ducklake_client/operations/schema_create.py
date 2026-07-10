"""Create DuckLake schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, execute, template

if TYPE_CHECKING:
    import duckdb


def schema_create(
    context: OperationContext,
    name: str,
    *,
    if_not_exists: bool = True,
) -> duckdb.DuckDBPyConnection:
    if not name:
        raise DuckLakeConfigError("schema name must not be empty")
    if "." in name:
        raise DuckLakeConfigError("schema name must not include a catalog prefix")

    query = template("schema_create.sql").format(
        if_not_exists="IF NOT EXISTS " if if_not_exists else "",
        schema_name=".".join(quote_identifier(part) for part in (context.alias, name)),
    )
    return execute(context, query, operation="schema.create")
