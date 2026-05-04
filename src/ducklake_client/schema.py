"""Reusable schema types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, get_args

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError

ColumnDataType: TypeAlias = Literal[
    "BIGINT",
    "BLOB",
    "BOOLEAN",
    "DATE",
    "DECIMAL",
    "DOUBLE",
    "FLOAT",
    "HUGEINT",
    "INTEGER",
    "INTERVAL",
    "JSON",
    "SMALLINT",
    "TIME",
    "TIMESTAMP",
    "TIMESTAMP_MS",
    "TIMESTAMP_NS",
    "TIMESTAMP_S",
    "TIMESTAMPTZ",
    "TINYINT",
    "UBIGINT",
    "UHUGEINT",
    "UINTEGER",
    "USMALLINT",
    "UTINYINT",
    "UUID",
    "VARCHAR",
]

_COLUMN_DATA_TYPES = frozenset(get_args(ColumnDataType))


@dataclass(frozen=True)
class ColumnDef:
    """Column definition used by table-oriented client methods."""

    data_type: ColumnDataType
    nullable: bool = True

    def __post_init__(self) -> None:
        if self.data_type not in _COLUMN_DATA_TYPES:
            valid_types = ", ".join(sorted(_COLUMN_DATA_TYPES))
            raise DuckLakeConfigError(
                f"invalid column data type: {self.data_type!r}. "
                f"Expected one of: {valid_types}"
            )

    def sql(self, name: str) -> str:
        if not name:
            raise DuckLakeConfigError("column name must not be empty")

        nullability = "" if self.nullable else " NOT NULL"
        return f"{quote_identifier(name)} {self.data_type}{nullability}"


@dataclass(frozen=True)
class TableListing:
    """A table-like relation discovered in the DuckLake catalog."""

    catalog_name: str
    schema_name: str
    table_name: str
    qualified_name: str
    table_type: str


@dataclass(frozen=True)
class ViewListing:
    """A view discovered in the DuckLake catalog."""

    catalog_name: str
    schema_name: str
    view_name: str
    qualified_name: str
    table_type: str


@dataclass(frozen=True)
class TableInfoColumn:
    """Column metadata and summary statistics for a DuckLake table."""

    name: str
    data_type: str
    nullable: bool
    ordinal_position: int
    default: str | None = None
    comment: str | None = None
    min: str | None = None
    max: str | None = None
    null_percentage: str | None = None
    approx_unique: str | None = None
    count: str | None = None
    summary: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class TablePartitionSpec:
    """DuckLake partition metadata for one partition key."""

    partition_id: int | None
    partition_key_index: int | None
    column_id: int | None
    column_name: str | None
    transform: str | None


@dataclass(frozen=True)
class TableSortSpec:
    """DuckLake sort metadata for one sort key."""

    sort_id: int | None
    sort_key_index: int | None
    expression: str | None
    dialect: str | None
    sort_direction: str | None
    null_order: str | None


@dataclass(frozen=True)
class DuckLakeTableMetadata:
    """Raw DuckLake catalog metadata for the table, when queryable."""

    table_id: int | None = None
    table_uuid: str | None = None
    schema_id: int | None = None
    begin_snapshot: int | None = None
    end_snapshot: int | None = None
    path: str | None = None
    path_is_relative: bool | None = None
    record_count: int | None = None
    next_row_id: int | None = None
    file_size_bytes: int | None = None


@dataclass(frozen=True)
class TableSnapshotInfo:
    """DuckLake snapshot metadata."""

    snapshot_id: int
    snapshot_time: Any | None = None
    schema_version: int | None = None
    next_catalog_id: int | None = None
    next_file_id: int | None = None
    changes_made: str | None = None
    author: str | None = None
    commit_message: str | None = None
    commit_extra_info: str | None = None


@dataclass(frozen=True)
class TableInfo:
    """Consolidated metadata for a DuckLake table."""

    catalog_name: str
    schema_name: str
    table_name: str
    qualified_name: str
    table_type: str
    columns: list[TableInfoColumn]
    row_count: int | None = None
    estimated_size: int | None = None
    table_comment: str | None = None
    partition_specs: list[TablePartitionSpec] = field(default_factory=list)
    sort_specs: list[TableSortSpec] = field(default_factory=list)
    ducklake_metadata: DuckLakeTableMetadata | None = None
    snapshots: list[TableSnapshotInfo] = field(default_factory=list)
