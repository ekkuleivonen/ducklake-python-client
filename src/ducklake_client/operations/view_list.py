"""List DuckLake views."""

from __future__ import annotations

from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, rows, template
from ducklake_client.schema import ViewListing


def view_list(
    context: OperationContext,
    *,
    schema_name: str | None = None,
) -> list[ViewListing]:
    if schema_name == "":
        raise DuckLakeConfigError("schema name must not be empty")

    parameters = {
        "catalog": context.alias,
        "schema": schema_name,
    }
    return [
        _view_listing(row)
        for row in rows(
            context,
            template("view_list.sql"),
            parameters,
            operation="view.list",
        )
    ]


def _view_listing(row: dict[str, Any]) -> ViewListing:
    catalog = str(row["table_catalog"])
    schema = str(row["table_schema"])
    view = str(row["table_name"])
    return ViewListing(
        catalog_name=catalog,
        schema_name=schema,
        view_name=view,
        qualified_name=".".join(quote_identifier(part) for part in (catalog, schema, view)),
        table_type=str(row["table_type"]),
    )
