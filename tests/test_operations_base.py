import unittest

from ducklake_client import DuckLakeQueryError
from ducklake_client.operations.base import execute


class FailingConnection:
    def execute(self, query: str) -> None:
        raise RuntimeError(f"failed query: {query}")


class Context:
    alias = "lake"
    connection = FailingConnection()


class ExecuteTests(unittest.TestCase):
    def test_wraps_native_query_errors(self) -> None:
        with self.assertRaises(DuckLakeQueryError) as raised:
            execute(Context(), "SELECT broken", operation="table.create")  # type: ignore[arg-type]

        self.assertEqual(str(raised.exception), "DuckLake table.create failed")
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
