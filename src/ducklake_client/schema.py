"""Reusable schema types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, get_args

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
