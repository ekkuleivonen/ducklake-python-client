"""Implementation for listing DuckLake views."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.schema import ViewListing


def list_views(
    client: Any,
    *,
    schema_name: str | None = None,
) -> list[ViewListing]:
    """List views in the attached DuckLake catalog."""

    if schema_name == "":
        raise DuckLakeConfigError("schema name must not be empty")

    params = {
        "catalog": client.alias,
        "schema": schema_name,
    }
    return [_view_listing(row) for row in _rows(client, _template(), params)]


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


def _rows(client: Any, query: str, parameters: dict[str, object]) -> list[dict[str, Any]]:
    try:
        cursor = client.execute(query, parameters)
        names = [str(column[0]) for column in cursor.description or []]
        return [dict(zip(names, row, strict=False)) for row in cursor.fetchall()]
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake list_views query failed") from exc


def _template() -> str:
    return (
        files("ducklake_client.methods.list_views")
        .joinpath("template.sql")
        .read_text(encoding="utf-8")
    )
