import unittest

from ducklake_client import DuckDBCatalog, DuckLake, DuckLakeQueryError, DiskStorage


class FailingConnection:
    def execute(self, sql: str, params: dict[str, object] | None = None) -> None:
        raise RuntimeError(f"failed query: {sql}")


class StubManager:
    def get(self) -> FailingConnection:
        return FailingConnection()


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


if __name__ == "__main__":
    unittest.main()
