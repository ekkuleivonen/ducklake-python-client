"""Public view helpers."""

from __future__ import annotations

from ducklake_client.modules.base import DuckLakeModule
from ducklake_client.operations.view_list import view_list
from ducklake_client.schema import ViewListing


class ViewModule(DuckLakeModule):
    """DuckLake view operations."""

    def list(
        self,
        *,
        schema_name: str | None = None,
    ) -> list[ViewListing]:
        return view_list(self, schema_name=schema_name)
