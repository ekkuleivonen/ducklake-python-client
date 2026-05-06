"""Lightweight Python helpers for DuckLake connections."""

from ducklake_client.client import DuckLake
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
from ducklake_client.modules import SchemaModule, SnapshotsModule, TableModule, ViewModule
from ducklake_client.schema import (
    ColumnDataType,
    ColumnDef,
    DuckLakeTableMetadata,
    TableColumnSummary,
    TableInfo,
    TableInfoColumn,
    TableListing,
    TablePartitionSpec,
    TableSnapshotInfo,
    TableSortSpec,
    ViewListing,
)

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
    "SchemaModule",
    "SnapshotsModule",
    "SqliteCatalog",
    "StorageConfig",
    "TableColumnSummary",
    "TableInfo",
    "TableInfoColumn",
    "TableListing",
    "TableModule",
    "TablePartitionSpec",
    "TableSnapshotInfo",
    "TableSortSpec",
    "ViewModule",
    "ViewListing",
]
