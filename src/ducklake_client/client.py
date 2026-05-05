"""Public DuckLake client entry point."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cached_property
from typing import TYPE_CHECKING

from ducklake_client._connection import ConnectionManager
from ducklake_client.config import (
    CatalogConfig,
    CatalogInput,
    DuckDBConfig,
    StorageConfig,
    StorageInput,
)
from ducklake_client.modules.schema import SchemaModule
from ducklake_client.modules.table import TableModule
from ducklake_client.modules.view import ViewModule

if TYPE_CHECKING:
    import duckdb


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

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._manager.get()

    @cached_property
    def schema(self) -> SchemaModule:
        return SchemaModule(self)

    @cached_property
    def table(self) -> TableModule:
        return TableModule(self)

    @cached_property
    def view(self) -> ViewModule:
        return ViewModule(self)

    def close(self) -> None:
        self._manager.close()

    def __enter__(self) -> DuckLake:
        self.connection
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
