"""Comment on DuckLake tables and columns."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ducklake_client.config import quote_identifier, quote_literal
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, template
from ducklake_client.operations.table_names import qualified_table_name, split_table_name

if TYPE_CHECKING:
    import duckdb


def table_comment(
    context: OperationContext,
    name: str,
    comment: str | None,
    *,
    column_name: str | None = None,
    schema_name: str = "main",
) -> duckdb.DuckDBPyConnection:
    schema, table = split_table_name(name, schema_name=schema_name)
    table_name = qualified_table_name(context.alias, schema, table)
    rendered_comment = _comment_literal(comment)

    if column_name is None:
        query = template("table_comment.sql").format(
            table_name=table_name,
            comment=rendered_comment,
        )
    else:
        if not column_name:
            raise DuckLakeConfigError("column name must not be empty")
        query = template("table_column_comment.sql").format(
            column_name=f"{table_name}.{quote_identifier(column_name)}",
            comment=rendered_comment,
        )
    return context.connection.execute(query)


def _comment_literal(comment: str | None) -> str:
    return "NULL" if comment is None else quote_literal(comment)
