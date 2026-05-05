"""Shared helpers for DuckLake operations."""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any, Protocol

from ducklake_client.exceptions import DuckLakeQueryError

if TYPE_CHECKING:
    import duckdb


class OperationContext(Protocol):
    """Minimal context an operation needs from a DuckLake module."""

    @property
    def alias(self) -> str: ...

    @property
    def connection(self) -> duckdb.DuckDBPyConnection: ...


def template(name: str) -> str:
    return files("ducklake_client.templates").joinpath(name).read_text(encoding="utf-8")


def rows(
    context: OperationContext,
    query: str,
    parameters: dict[str, object] | None = None,
    *,
    operation: str,
) -> list[dict[str, Any]]:
    try:
        cursor = (
            context.connection.execute(query, parameters)
            if parameters is not None
            else context.connection.execute(query)
        )
        names = [str(column[0]) for column in cursor.description or []]
        return [dict(zip(names, row, strict=False)) for row in cursor.fetchall()]
    except Exception as exc:
        raise DuckLakeQueryError(f"DuckLake {operation} query failed") from exc


def optional_rows(
    context: OperationContext,
    query: str,
    parameters: dict[str, object] | None = None,
    *,
    operation: str,
) -> list[dict[str, Any]]:
    try:
        return rows(context, query, parameters, operation=operation)
    except DuckLakeQueryError:
        return []
