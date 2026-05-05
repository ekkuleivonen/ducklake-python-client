"""Public table helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ducklake_client.modules.base import DuckLakeModule
from ducklake_client.operations.table_comment import table_comment
from ducklake_client.operations.table_create import table_create, table_create_from_csv
from ducklake_client.operations.table_info import table_info
from ducklake_client.operations.table_list import table_list
from ducklake_client.schema import ColumnDef, TableInfo, TableListing

if TYPE_CHECKING:
    import duckdb


class TableModule(DuckLakeModule):
    """DuckLake table operations."""

    def create(
        self,
        table_name: str,
        *,
        schema_name: str = "main",
        if_not_exists: bool = True,
        **columns: ColumnDef,
    ) -> duckdb.DuckDBPyConnection:
        return table_create(
            self,
            table_name,
            schema_name=schema_name,
            if_not_exists=if_not_exists,
            **columns,
        )

    def create_from_csv(
        self,
        name: str,
        source: str | Path,
        *,
        schema_name: str = "main",
        if_not_exists: bool = True,
    ) -> duckdb.DuckDBPyConnection:
        return table_create_from_csv(
            self,
            name,
            source,
            schema_name=schema_name,
            if_not_exists=if_not_exists,
        )

    def comment(
        self,
        name: str,
        comment: str | None,
        *,
        column_name: str | None = None,
        schema_name: str = "main",
    ) -> duckdb.DuckDBPyConnection:
        return table_comment(
            self,
            name,
            comment,
            column_name=column_name,
            schema_name=schema_name,
        )

    def list(
        self,
        *,
        schema_name: str | None = None,
    ) -> list[TableListing]:
        return table_list(self, schema_name=schema_name)

    def info(
        self,
        name: str,
        *,
        schema_name: str = "main",
        include_row_count: bool = True,
        include_snapshots: bool = True,
    ) -> TableInfo:
        return table_info(
            self,
            name,
            schema_name=schema_name,
            include_row_count=include_row_count,
            include_snapshots=include_snapshots,
        )
