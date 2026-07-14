"""Public DuckLake client entry point."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cached_property
from typing import TYPE_CHECKING, Any

from ducklake_client._connection import ConnectionManager
from ducklake_client._fence import (
    FenceKey,
    FenceSpec,
    catalog_fence,
    catalog_fence_set,
)
from ducklake_client.config import (
    CatalogConfig,
    CatalogInput,
    DuckDBConfig,
    DuckLakeAttachConfig,
    StorageConfig,
    StorageInput,
)
from ducklake_client.exceptions import DuckLakeQueryError
from ducklake_client.modules.schema import SchemaModule
from ducklake_client.modules.snapshots import SnapshotsModule
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
        attach: DuckLakeAttachConfig | None = None,
        attach_options: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(catalog, CatalogConfig):
            raise TypeError("catalog must be a DuckDBCatalog, PostgresCatalog, or SqliteCatalog")
        if not isinstance(storage, StorageConfig):
            raise TypeError("storage must be a DiskStorage or S3Storage")
        if attach is not None and not isinstance(attach, DuckLakeAttachConfig):
            raise TypeError("attach must be a DuckLakeAttachConfig")

        self.alias = alias
        self.catalog = catalog
        self._manager = ConnectionManager(
            catalog=catalog,
            storage=storage,
            alias=alias,
            duckdb=duckdb or DuckDBConfig(),
            attach=attach,
            attach_options=attach_options,
        )

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._manager.get()

    @cached_property
    def schema(self) -> SchemaModule:
        return SchemaModule(self)

    @cached_property
    def snapshots(self) -> SnapshotsModule:
        return SnapshotsModule(self)

    @cached_property
    def table(self) -> TableModule:
        return TableModule(self)

    @cached_property
    def view(self) -> ViewModule:
        return ViewModule(self)

    def sql_dicts(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        """Run arbitrary SQL with named parameters and return rows as dicts.

        Named parameters use DuckDB's ``$name`` syntax. For no parameters, call
        with only ``sql``.
        """

        connection = self.connection
        try:
            if params:
                connection.execute(sql, params)
            else:
                connection.execute(sql)
            columns = [col[0] for col in (connection.description or [])]
            return [dict(zip(columns, row, strict=False)) for row in connection.fetchall()]
        except DuckLakeQueryError:
            raise
        except Exception as exc:
            raise DuckLakeQueryError("DuckLake sql_dicts failed") from exc

    def sql_scalar(self, sql: str, **params: Any) -> Any:
        """Run SQL with optional ``$name`` parameters and return a single scalar cell."""

        connection = self.connection
        try:
            if params:
                connection.execute(sql, params)
            else:
                connection.execute(sql)
            row = connection.fetchone()
        except DuckLakeQueryError:
            raise
        except Exception as exc:
            raise DuckLakeQueryError("DuckLake sql_scalar failed") from exc
        if row is None:
            raise DuckLakeQueryError("sql_scalar expected one row, got zero rows")
        if len(row) != 1:
            raise DuckLakeQueryError(f"sql_scalar expected exactly one column, got {len(row)}")
        return row[0]

    def sql_one(self, sql: str, **params: Any) -> dict[str, Any]:
        """Run SQL with optional ``$name`` parameters and return exactly one row as a dict."""

        connection = self.connection
        try:
            if params:
                connection.execute(sql, params)
            else:
                connection.execute(sql)
            columns = [col[0] for col in (connection.description or [])]
            row = connection.fetchone()
        except DuckLakeQueryError:
            raise
        except Exception as exc:
            raise DuckLakeQueryError("DuckLake sql_one failed") from exc
        if row is None:
            raise DuckLakeQueryError("sql_one expected one row, got zero rows")
        if connection.fetchone() is not None:
            raise DuckLakeQueryError("sql_one expected one row, got multiple rows")
        return dict(zip(columns, row, strict=False))

    @contextmanager
    def fence(
        self,
        *keys: FenceKey,
        namespace: str = "ducklake-client",
        timeout: float | None = None,
    ) -> Iterator[DuckLake]:
        """Cooperatively exclude other clients using the same catalog and keys."""

        with catalog_fence(
            self.catalog,
            keys,
            namespace=namespace,
            timeout=timeout,
        ):
            yield self

    @contextmanager
    def fence_set(
        self,
        *fences: FenceSpec,
        namespace: str = "ducklake-client",
        timeout: float | None = None,
    ) -> Iterator[DuckLake]:
        """Acquire independent cooperative fences through one backend session."""

        with catalog_fence_set(
            self.catalog,
            fences,
            namespace=namespace,
            timeout=timeout,
        ):
            yield self

    @contextmanager
    def transaction(self) -> Iterator[DuckLake]:
        """Run a block inside a DuckDB transaction on this lake's connection."""

        connection = self.connection
        connection.begin()
        try:
            yield self
        except BaseException:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
        else:
            try:
                connection.commit()
            except Exception:
                try:
                    connection.rollback()
                except Exception:
                    pass
                raise

    def close(self) -> None:
        self._manager.close()

    def __enter__(self) -> DuckLake:
        _ = self.connection
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
