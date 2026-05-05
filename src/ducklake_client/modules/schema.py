"""Public schema helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ducklake_client.modules.base import DuckLakeModule
from ducklake_client.operations.schema_create import schema_create

if TYPE_CHECKING:
    import duckdb


class SchemaModule(DuckLakeModule):
    """DuckLake schema operations."""

    def create(
        self,
        name: str,
        *,
        if_not_exists: bool = True,
    ) -> duckdb.DuckDBPyConnection:
        return schema_create(self, name, if_not_exists=if_not_exists)
