import unittest

import duckdb

from ducklake_client import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.operations.table_append import table_append


class Context:
    alias = "lake"

    def __init__(self) -> None:
        self.connection = duckdb.connect()
        self.connection.execute("ATTACH ':memory:' AS lake")
        self.connection.execute(
            "CREATE TABLE lake.main.events "
            "(id INTEGER, name VARCHAR, source VARCHAR DEFAULT 'api')"
        )


class TableAppendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context()

    def tearDown(self) -> None:
        self.context.connection.close()

    def test_appends_mapping_records_by_name(self) -> None:
        table_append(
            self.context,
            "events",
            [{"name": "one", "id": 1}, {"id": 2, "name": "two"}],
        )

        rows = self.context.connection.execute(
            "SELECT id, name, source FROM lake.main.events ORDER BY id"
        ).fetchall()
        self.assertEqual(rows, [(1, "one", "api"), (2, "two", "api")])

    def test_empty_records_are_a_noop(self) -> None:
        table_append(self.context, "events", [])
        count = self.context.connection.execute(
            "SELECT count(*) FROM lake.main.events"
        ).fetchone()
        self.assertEqual(count, (0,))

    def test_appends_same_connection_relation_by_name(self) -> None:
        relation = self.context.connection.sql(
            "SELECT 'relation' AS name, 3 AS id"
        )
        table_append(self.context, "events", relation)

        row = self.context.connection.execute(
            "SELECT id, name, source FROM lake.main.events"
        ).fetchone()
        self.assertEqual(row, (3, "relation", "api"))

    def test_rejects_inconsistent_record_columns(self) -> None:
        with self.assertRaises(DuckLakeConfigError):
            table_append(self.context, "events", [{"id": 1}, {"name": "two"}])

    def test_wraps_native_write_errors(self) -> None:
        with self.assertRaises(DuckLakeQueryError) as raised:
            table_append(self.context, "missing", [{"id": 1}])

        self.assertIsInstance(raised.exception.__cause__, duckdb.Error)


if __name__ == "__main__":
    unittest.main()
