"""Transaction context manager for DuckLake connections."""

from __future__ import annotations

from typing import Any

from ducklake_client._params import QueryParameters, normalize_parameters
from ducklake_client.exceptions import DuckLakeQueryError


class Transaction:
    """A context-managed DuckDB transaction on a DuckLake connection."""

    def __init__(self, lake: Any) -> None:
        self._lake = lake
        self._connection: Any | None = None

    def __enter__(self) -> Transaction:
        if self._connection is not None:
            raise RuntimeError("transaction is already active")
        self._connection = self._lake.raw_connection()
        self._connection.execute("BEGIN TRANSACTION")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        if exc_type is None:
            try:
                connection.execute("COMMIT")
            except Exception as commit_exc:
                try:
                    connection.execute("ROLLBACK")
                except Exception:
                    pass
                raise DuckLakeQueryError("DuckLake transaction commit failed") from commit_exc
        else:
            try:
                connection.execute("ROLLBACK")
            except Exception:
                pass

    def sql(self, query: str, *parameters: object, **named_parameters: object) -> Any:
        return self.execute(query, normalize_parameters(parameters, named_parameters))

    def execute(self, query: str, parameters: QueryParameters = None) -> Any:
        if parameters is None:
            return self.raw_connection().execute(query)
        return self.raw_connection().execute(query, parameters)

    def raw_connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError("transaction is not active")
        return self._connection
