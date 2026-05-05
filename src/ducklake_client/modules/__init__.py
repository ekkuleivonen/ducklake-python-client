"""Public DuckLake API modules."""

from ducklake_client.modules.schema import SchemaModule
from ducklake_client.modules.table import TableModule
from ducklake_client.modules.view import ViewModule

__all__ = [
    "SchemaModule",
    "TableModule",
    "ViewModule",
]
