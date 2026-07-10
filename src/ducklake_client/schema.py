"""Reusable schema types."""

from __future__ import annotations

from collections.abc import Mapping
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


class SQLType:
    """Base class for composable DuckDB column types."""

    def sql(self) -> str:
        raise NotImplementedError


ColumnType: TypeAlias = ColumnDataType | SQLType


@dataclass(frozen=True)
class DecimalType(SQLType):
    """A DECIMAL type with explicit precision and scale."""

    precision: int
    scale: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.precision <= 38:
            raise DuckLakeConfigError("DECIMAL precision must be between 1 and 38")
        if not 0 <= self.scale <= self.precision:
            raise DuckLakeConfigError("DECIMAL scale must be between 0 and precision")

    def sql(self) -> str:
        return f"DECIMAL({self.precision}, {self.scale})"


@dataclass(frozen=True)
class ListType(SQLType):
    """A variable-length list of another column type."""

    item_type: ColumnType

    def __post_init__(self) -> None:
        _type_sql(self.item_type)

    def sql(self) -> str:
        return f"{_type_sql(self.item_type)}[]"


@dataclass(frozen=True)
class MapType(SQLType):
    """A map with typed keys and values."""

    key_type: ColumnType
    value_type: ColumnType

    def __post_init__(self) -> None:
        _type_sql(self.key_type)
        _type_sql(self.value_type)

    def sql(self) -> str:
        return f"MAP({_type_sql(self.key_type)}, {_type_sql(self.value_type)})"


@dataclass(frozen=True)
class StructType(SQLType):
    """A struct containing an ordered mapping of named fields."""

    fields: Mapping[str, ColumnType]

    def __post_init__(self) -> None:
        if not self.fields:
            raise DuckLakeConfigError("STRUCT requires at least one field")
        for name, field_type in self.fields.items():
            if not name:
                raise DuckLakeConfigError("STRUCT field names must not be empty")
            _type_sql(field_type)

    def sql(self) -> str:
        fields = ", ".join(
            f"{quote_identifier(name)} {_type_sql(field_type)}"
            for name, field_type in self.fields.items()
        )
        return f"STRUCT({fields})"


@dataclass(frozen=True)
class ColumnDef:
    """Column definition used by table-oriented client methods."""

    data_type: ColumnType
    nullable: bool = True

    def __post_init__(self) -> None:
        _type_sql(self.data_type)

    def sql(self, name: str) -> str:
        if not name:
            raise DuckLakeConfigError("column name must not be empty")

        nullability = "" if self.nullable else " NOT NULL"
        return f"{quote_identifier(name)} {_type_sql(self.data_type)}{nullability}"


def _type_sql(data_type: ColumnType) -> str:
    if isinstance(data_type, SQLType):
        return data_type.sql()
    if data_type not in _COLUMN_DATA_TYPES:
        valid_types = ", ".join(sorted(_COLUMN_DATA_TYPES))
        raise DuckLakeConfigError(
            f"invalid column data type: {data_type!r}. Expected one of: {valid_types}"
        )
    return data_type


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
class TableColumnSummary:
    """DuckDB SUMMARIZE statistics for a single table column."""

    min: str | None = None
    max: str | None = None
    approx_unique: str | None = None
    avg: str | None = None
    std: str | None = None
    q25: str | None = None
    q50: str | None = None
    q75: str | None = None
    count: str | None = None
    null_percentage: str | None = None


@dataclass(frozen=True)
class TableInfoColumn:
    """Column metadata and summary statistics for a DuckLake table."""

    name: str
    data_type: str
    nullable: bool
    ordinal_position: int
    default: str | None = None
    comment: str | None = None
    summary: TableColumnSummary | None = None


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
