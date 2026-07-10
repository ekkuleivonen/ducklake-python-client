import unittest
from datetime import datetime

import duckdb

from ducklake_client import DuckDBCatalog, DuckLake, DuckLakeQueryError, DiskStorage


class FailingConnection:
    def execute(self, sql: str, params: dict[str, object] | None = None) -> None:
        raise RuntimeError(f"failed query: {sql}")


class StubManager:
    def get(self) -> FailingConnection:
        return FailingConnection()


class ConnectionManager:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def get(self) -> duckdb.DuckDBPyConnection:
        return self.connection


class SqlDictsTests(unittest.TestCase):
    def test_wraps_native_query_errors(self) -> None:
        lake = DuckLake(
            catalog=DuckDBCatalog("metadata.ducklake"),
            storage=DiskStorage("data"),
        )
        lake._manager = StubManager()  # type: ignore[assignment]

        with self.assertRaises(DuckLakeQueryError) as raised:
            lake.sql_dicts("SELECT broken")

        self.assertEqual(str(raised.exception), "DuckLake sql_dicts failed")
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)

    def test_materializes_timestamptz(self) -> None:
        lake = DuckLake(
            catalog=DuckDBCatalog("metadata.ducklake"),
            storage=DiskStorage("data"),
        )
        connection = duckdb.connect()
        lake._manager = ConnectionManager(connection)  # type: ignore[assignment]
        try:
            rows = lake.sql_dicts(
                "SELECT TIMESTAMPTZ '2026-01-01 12:00:00+09:00' AS ts"
            )
        finally:
            connection.close()

        self.assertIsInstance(rows[0]["ts"], datetime)
        self.assertIsNotNone(rows[0]["ts"].tzinfo)


if __name__ == "__main__":
    unittest.main()
