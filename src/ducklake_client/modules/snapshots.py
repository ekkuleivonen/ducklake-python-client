"""Catalog snapshot helpers."""

from __future__ import annotations

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeQueryError
from ducklake_client.modules.base import DuckLakeModule


class SnapshotsModule(DuckLakeModule):
    """Helpers backed by DuckLake's ``snapshots()`` catalog table function."""

    def latest(self) -> int | None:
        """Latest catalog ``snapshot_id``, or ``None`` when no snapshots exist."""

        sql = f"SELECT max(snapshot_id) AS m FROM {quote_identifier(self.alias)}.snapshots()"
        try:
            row = self.connection.execute(sql).fetchone()
        except Exception as exc:
            raise DuckLakeQueryError("DuckLake snapshots.latest query failed") from exc
        if row is None:
            return None
        value = row[0]
        return None if value is None else int(value)
