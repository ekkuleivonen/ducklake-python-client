"""Shared module base classes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import duckdb


class DuckLakeClientProtocol(Protocol):
    alias: str

    @property
    def connection(self) -> duckdb.DuckDBPyConnection: ...


class DuckLakeModule:
    """Base for public DuckLake feature modules."""

    def __init__(self, client: DuckLakeClientProtocol) -> None:
        self._client = client

    @property
    def alias(self) -> str:
        return self._client.alias

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._client.connection
