"""Implementation for creating DuckLake schemas."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError


def create_schema(
    client: Any,
    *,
    name: str,
    if_not_exists: bool = True,
) -> Any:
    """Create a schema in the attached DuckLake catalog."""

    if not name:
        raise DuckLakeConfigError("schema name must not be empty")
    if "." in name:
        raise DuckLakeConfigError("schema name must not include a catalog prefix")

    sql = _template().format(
        if_not_exists="IF NOT EXISTS " if if_not_exists else "",
        schema_name=".".join(quote_identifier(part) for part in (client.alias, name)),
    )
    return client.execute(sql)


def _template() -> str:
    return (
        files("ducklake_client.methods.create_schema")
        .joinpath("template.sql")
        .read_text(encoding="utf-8")
    )
