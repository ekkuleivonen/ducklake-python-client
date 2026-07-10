import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ducklake_client import (
    DiskStorage,
    DuckLake,
    DuckLakeConfigError,
    DuckLakeFenceTimeout,
    PostgresCatalog,
    SqliteCatalog,
)
from ducklake_client._fence import catalog_fence


class FenceTests(unittest.TestCase):
    def test_local_catalog_fence_times_out_under_contention(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = SqliteCatalog(Path(directory) / "metadata.sqlite")
            first = DuckLake(catalog=catalog, storage=DiskStorage(directory))
            second = DuckLake(catalog=catalog, storage=DiskStorage(directory))
            entered = threading.Event()
            release = threading.Event()

            def hold_fence() -> None:
                with first.fence("atlas", "elements", "batch-1"):
                    entered.set()
                    release.wait(timeout=2)

            thread = threading.Thread(target=hold_fence)
            thread.start()
            self.assertTrue(entered.wait(timeout=1))
            try:
                with self.assertRaises(DuckLakeFenceTimeout):
                    with second.fence("atlas", "elements", "batch-1", timeout=0.02):
                        self.fail("contended fence should not be entered")
            finally:
                release.set()
                thread.join(timeout=1)
            self.assertFalse(thread.is_alive())

    def test_different_keys_do_not_contend(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = SqliteCatalog(Path(directory) / "metadata.sqlite")
            lake = DuckLake(catalog=catalog, storage=DiskStorage(directory))
            with lake.fence("batch-1"):
                with lake.fence("batch-2", timeout=0):
                    pass

    def test_rejects_invalid_fence_arguments(self) -> None:
        with TemporaryDirectory() as directory:
            lake = DuckLake(
                catalog=SqliteCatalog(Path(directory) / "metadata.sqlite"),
                storage=DiskStorage(directory),
            )
            with self.assertRaises(DuckLakeConfigError):
                with lake.fence():
                    pass
            with self.assertRaises(DuckLakeConfigError):
                with lake.fence("key", timeout=-1):
                    pass
            with self.assertRaises(DuckLakeConfigError):
                with lake.fence(object()):  # type: ignore[arg-type]
                    pass

    @patch("psycopg.connect")
    def test_postgres_uses_advisory_lock(self, connect: object) -> None:
        connection = FakePostgresConnection()
        connect.return_value = connection  # type: ignore[attr-defined]

        with catalog_fence(
            PostgresCatalog("dbname=ducklake"),
            ("atlas", "batch-1"),
            namespace="tests",
            timeout=0,
        ):
            pass

        self.assertEqual(connection.statements[0][0], "SELECT pg_try_advisory_lock(%s)")
        self.assertEqual(connection.statements[-1][0], "SELECT pg_advisory_unlock(%s)")
        self.assertEqual(connection.statements[0][1], connection.statements[-1][1])


class FakeCursor:
    def fetchone(self) -> tuple[bool]:
        return (True,)


class FakePostgresConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[int, ...]]] = []

    def __enter__(self) -> "FakePostgresConnection":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def execute(self, sql: str, parameters: tuple[int, ...]) -> FakeCursor:
        self.statements.append((sql, parameters))
        return FakeCursor()


if __name__ == "__main__":
    unittest.main()
