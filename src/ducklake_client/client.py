"""Public DuckLake client entry point."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ducklake_client._connection import ConnectionManager
from ducklake_client._params import QueryParameters, normalize_parameters
from ducklake_client.config import (
    CatalogConfig,
    CatalogInput,
    DuckDBConfig,
    StorageConfig,
    StorageInput,
    quote_literal,
)
from ducklake_client.transaction import Transaction

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
        if not isinstance(catalog, CatalogConfig):
            raise TypeError("catalog must be a DuckDBCatalog, PostgresCatalog, or SqliteCatalog")
        if not isinstance(storage, StorageConfig):
            raise TypeError("storage must be a DiskStorage or S3Storage")

        self.alias = alias
        self._manager = ConnectionManager(
            catalog=catalog,
            storage=storage,
            alias=alias,
            duckdb=duckdb or DuckDBConfig(),
            attach_options=attach_options,
        )

    def sql(self, query: str, *parameters: object, **named_parameters: object) -> Any:
        return self.execute(query, normalize_parameters(parameters, named_parameters))

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
