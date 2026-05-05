"""List DuckLake tables."""

from __future__ import annotations

from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, rows, template
from ducklake_client.schema import TableListing


def table_list(
    context: OperationContext,
    *,
    schema_name: str | None = None,
) -> list[TableListing]:
    if schema_name == "":
        raise DuckLakeConfigError("schema name must not be empty")

    parameters = {
        "catalog": context.alias,
        "schema": schema_name,
    }
    return [
        _table_listing(row)
        for row in rows(
            context,
            template("table_list.sql"),
            parameters,
            operation="table.list",
        )
    ]


def _table_listing(row: dict[str, Any]) -> TableListing:
    catalog = str(row["table_catalog"])
    schema = str(row["table_schema"])
    table = str(row["table_name"])
    return TableListing(
        catalog_name=catalog,
        schema_name=schema,
        table_name=table,
        qualified_name=".".join(quote_identifier(part) for part in (catalog, schema, table)),
        table_type=str(row["table_type"]),
    )
