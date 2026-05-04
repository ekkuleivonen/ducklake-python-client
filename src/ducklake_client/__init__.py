"""Lightweight Python helpers for DuckLake connections."""

from ducklake_client.config import (
    CatalogConfig,
    DiskStorage,
    DuckDBCatalog,
    DuckDBConfig,
    PostgresCatalog,
    S3Storage,
    SqliteCatalog,
    StorageConfig,
)
from ducklake_client.exceptions import (
    DuckLakeConfigError,
    DuckLakeConnectionError,
    DuckLakeError,
    DuckLakeQueryError,
)
from ducklake_client.client import DuckLake
from ducklake_client.schema import (
    ColumnDataType,
    ColumnDef,
    DuckLakeTableMetadata,
    TableInfo,
    TableInfoColumn,
    TablePartitionSpec,
    TableSnapshotInfo,
    TableSortSpec,
)
from ducklake_client.transaction import Transaction

__all__ = [
    "CatalogConfig",
    "ColumnDataType",
    "ColumnDef",
    "DuckDBCatalog",
    "DuckDBConfig",
    "DuckLake",
    "DuckLakeConfigError",
    "DuckLakeConnectionError",
    "DuckLakeError",
    "DuckLakeQueryError",
    "DuckLakeTableMetadata",
    "DiskStorage",
    "PostgresCatalog",
    "S3Storage",
    "SqliteCatalog",
    "StorageConfig",
    "TableInfo",
    "TableInfoColumn",
    "TablePartitionSpec",
    "TableSnapshotInfo",
    "TableSortSpec",
    "Transaction",
]
