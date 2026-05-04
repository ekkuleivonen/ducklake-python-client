"""Implementation for listing DuckLake tables."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.schema import TableListing


def list_tables(
    client: Any,
    *,
    schema_name: str | None = None,
) -> list[TableListing]:
    """List base tables in the attached DuckLake catalog."""

    if schema_name == "":
        raise DuckLakeConfigError("schema name must not be empty")

    params = {
        "catalog": client.alias,
        "schema": schema_name,
    }
    return [_table_listing(row) for row in _rows(client, _template(), params)]


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


def _rows(client: Any, query: str, parameters: dict[str, object]) -> list[dict[str, Any]]:
    try:
        cursor = client.execute(query, parameters)
        names = [str(column[0]) for column in cursor.description or []]
        return [dict(zip(names, row, strict=False)) for row in cursor.fetchall()]
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake list_tables query failed") from exc


def _template() -> str:
    return (
        files("ducklake_client.methods.list_tables")
        .joinpath("template.sql")
        .read_text(encoding="utf-8")
    )
