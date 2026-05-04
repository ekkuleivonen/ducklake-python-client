"""Public DuckLake client entry point."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeAlias

from ducklake_client._connection import ConnectionManager
from ducklake_client.config import (
    CatalogInput,
    DuckDBConfig,
    StorageInput,
    parse_catalog,
    parse_storage,
    quote_literal,
)
from ducklake_client.exceptions import DuckLakeQueryError

QueryParameters: TypeAlias = Mapping[str, object] | Sequence[object] | None

_EXTENSION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DuckLake:
    """A lazy DuckLake connection wrapper."""

    def __init__(
        self,
        *,
        catalog: CatalogInput,
        storage: StorageInput,
        alias: str = "lake",
        duckdb: DuckDBConfig | None = None,
        attach_options: Mapping[str, object] | None = None,
    ) -> None:
        self.alias = alias
        self._manager = ConnectionManager(
            catalog=parse_catalog(catalog),
            storage=parse_storage(storage),
            alias=alias,
            duckdb=duckdb or DuckDBConfig(),
            attach_options=attach_options,
        )

    def sql(self, query: str, *parameters: object, **named_parameters: object) -> Any:
        return self.execute(query, _normalize_parameters(parameters, named_parameters))

    def execute(self, query: str, parameters: QueryParameters = None) -> Any:
        if parameters is None:
            return self.raw_connection().execute(query)
        return self.raw_connection().execute(query, parameters)

    def transaction(self) -> Transaction:
        return Transaction(self)

    def raw_connection(self) -> Any:
        return self._manager.get()

    def close(self) -> None:
        self._manager.close()

    def load_extension(
        self,
        name: str | None = None,
        *,
        path: str | Path | None = None,
        install: bool = True,
    ) -> None:
        """Install and/or load a DuckDB extension into this lake's connection."""

        if (name is None) == (path is None):
            raise ValueError("provide exactly one of `name` or `path`")
        connection = self.raw_connection()
        if path is not None:
            connection.execute(f"LOAD {quote_literal(str(Path(path)))}")
            return
        assert name is not None
        if not _EXTENSION_NAME.fullmatch(name):
            raise ValueError(f"invalid DuckDB extension name: {name!r}")
        if install:
            connection.execute(f"INSTALL {name}")
        connection.execute(f"LOAD {name}")

    def __enter__(self) -> DuckLake:
        self.raw_connection()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw_connection(), name)


class Transaction:
    """A context-managed DuckDB transaction on a DuckLake connection."""

    def __init__(self, lake: DuckLake) -> None:
        self._lake = lake
        self._connection: Any | None = None

    def __enter__(self) -> Transaction:
        if self._connection is not None:
            raise RuntimeError("transaction is already active")
        self._connection = self._lake.raw_connection()
        self._connection.execute("BEGIN TRANSACTION")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        if exc_type is None:
            try:
                connection.execute("COMMIT")
            except Exception as commit_exc:
                try:
                    connection.execute("ROLLBACK")
                except Exception:
                    pass
                raise DuckLakeQueryError("DuckLake transaction commit failed") from commit_exc
        else:
            try:
                connection.execute("ROLLBACK")
            except Exception:
                pass

    def sql(self, query: str, *parameters: object, **named_parameters: object) -> Any:
        return self.execute(query, _normalize_parameters(parameters, named_parameters))

    def execute(self, query: str, parameters: QueryParameters = None) -> Any:
        if parameters is None:
            return self.raw_connection().execute(query)
        return self.raw_connection().execute(query, parameters)

    def raw_connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError("transaction is not active")
        return self._connection


def _normalize_parameters(
    positional: tuple[object, ...],
    named: Mapping[str, object],
) -> QueryParameters:
    if positional and named:
        raise TypeError("pass either positional parameters or named parameters, not both")
    if named:
        return dict(named)
    if not positional:
        return None
    if len(positional) == 1 and isinstance(positional[0], Mapping):
        return dict(positional[0])
    return list(positional)
