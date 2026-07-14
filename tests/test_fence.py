import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ducklake_client import (
    DiskStorage,
    DuckLake,
    DuckLakeConfigError,
    DuckLakeFenceError,
    DuckLakeFenceTimeout,
    FenceSpec,
    PostgresCatalog,
    SqliteCatalog,
)
from ducklake_client._fence import catalog_fence, catalog_fence_set


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

    def test_fence_sets_contend_on_one_shared_identity(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = SqliteCatalog(Path(directory) / "metadata.sqlite")
            first = DuckLake(catalog=catalog, storage=DiskStorage(directory))
            second = DuckLake(catalog=catalog, storage=DiskStorage(directory))
            entered = threading.Event()
            release = threading.Event()

            def hold_fences() -> None:
                with first.fence_set(
                    FenceSpec.exclusive("crawl", "a"),
                    FenceSpec.exclusive("content", "shared"),
                ):
                    entered.set()
                    release.wait(timeout=2)

            thread = threading.Thread(target=hold_fences)
            thread.start()
            self.assertTrue(entered.wait(timeout=1))
            try:
                with self.assertRaises(DuckLakeFenceTimeout):
                    with second.fence_set(
                        FenceSpec.exclusive("crawl", "b"),
                        FenceSpec.exclusive("content", "shared"),
                        timeout=0.02,
                    ):
                        self.fail("overlapping fence sets should contend")
            finally:
                release.set()
                thread.join(timeout=1)
            self.assertFalse(thread.is_alive())

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
            with self.assertRaises(DuckLakeConfigError):
                with lake.fence_set():
                    pass
            with self.assertRaises(DuckLakeConfigError):
                FenceSpec(("key",), mode="invalid")  # type: ignore[arg-type]

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
        self.assertTrue(connection.closed)

    @patch("psycopg.connect")
    def test_postgres_fence_set_uses_one_connection_for_every_lock(
        self, connect: object
    ) -> None:
        connection = FakePostgresConnection()
        connect.return_value = connection  # type: ignore[attr-defined]

        with catalog_fence_set(
            PostgresCatalog("dbname=ducklake"),
            (
                FenceSpec.exclusive("content", "second"),
                FenceSpec.shared("maintenance"),
                FenceSpec.exclusive("content", "first"),
            ),
            namespace="tests",
            timeout=0,
        ):
            pass

        connect.assert_called_once_with(  # type: ignore[attr-defined]
            "dbname=ducklake", autocommit=True
        )
        acquisitions = [
            statement
            for statement in connection.statements
            if "pg_try_advisory_lock" in statement[0]
        ]
        releases = [
            statement
            for statement in connection.statements
            if "pg_advisory_unlock" in statement[0]
        ]
        self.assertEqual(len(acquisitions), 3)
        self.assertEqual(len(releases), 3)
        self.assertTrue(any("_shared" in sql for sql, _params in acquisitions))
        self.assertEqual(
            [params for _sql, params in acquisitions],
            [params for _sql, params in reversed(releases)],
        )
        self.assertTrue(connection.closed)

    @patch("psycopg.connect")
    def test_postgres_fence_set_releases_partial_acquisition(
        self, connect: object
    ) -> None:
        connection = FakePostgresConnection(try_results=[True, False])
        connect.return_value = connection  # type: ignore[attr-defined]

        with self.assertRaises(DuckLakeFenceTimeout):
            with catalog_fence_set(
                PostgresCatalog("dbname=ducklake"),
                (
                    FenceSpec.exclusive("first"),
                    FenceSpec.exclusive("second"),
                ),
                namespace="tests",
                timeout=0,
            ):
                pass

        releases = [
            statement
            for statement in connection.statements
            if "pg_advisory_unlock" in statement[0]
        ]
        self.assertEqual(len(releases), 1)
        self.assertTrue(connection.closed)

    @patch("psycopg.connect")
    def test_postgres_fence_set_deduplicates_and_upgrades_identity(
        self, connect: object
    ) -> None:
        connection = FakePostgresConnection()
        connect.return_value = connection  # type: ignore[attr-defined]

        with catalog_fence_set(
            PostgresCatalog("dbname=ducklake"),
            (
                FenceSpec.shared("same"),
                FenceSpec.exclusive("same"),
                FenceSpec.shared("same"),
            ),
            namespace="tests",
            timeout=0,
        ):
            pass

        acquisitions = [
            sql for sql, _params in connection.statements if "pg_try" in sql
        ]
        self.assertEqual(acquisitions, ["SELECT pg_try_advisory_lock(%s)"])

    @patch("psycopg.connect")
    def test_postgres_preserves_body_exception_identity(self, connect: object) -> None:
        connection = FakePostgresConnection()
        connect.return_value = connection  # type: ignore[attr-defined]
        error = DomainError("ingestion failed")

        with self.assertRaises(DomainError) as raised:
            with catalog_fence(
                PostgresCatalog("dbname=ducklake"),
                ("batch-1",),
                namespace="tests",
                timeout=0,
            ):
                raise error

        self.assertIs(raised.exception, error)
        self.assertTrue(connection.closed)

    @patch("psycopg.connect")
    def test_postgres_wraps_release_failure(self, connect: object) -> None:
        connection = FakePostgresConnection(fail_unlock=True)
        connect.return_value = connection  # type: ignore[attr-defined]

        with self.assertRaises(DuckLakeFenceError) as raised:
            with catalog_fence(
                PostgresCatalog("dbname=ducklake"),
                ("batch-1",),
                namespace="tests",
                timeout=0,
            ):
                pass

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)

    @patch("psycopg.connect")
    def test_release_failure_does_not_mask_body_exception(self, connect: object) -> None:
        connection = FakePostgresConnection(fail_unlock=True)
        connect.return_value = connection  # type: ignore[attr-defined]
        error = DomainError("ingestion failed")

        with self.assertRaises(DomainError) as raised:
            with catalog_fence(
                PostgresCatalog("dbname=ducklake"),
                ("batch-1",),
                namespace="tests",
                timeout=0,
            ):
                raise error

        self.assertIs(raised.exception, error)
        self.assertTrue(any("release also failed" in note for note in error.__notes__))


class FakeCursor:
    def __init__(self, result: bool = True) -> None:
        self.result = result

    def fetchone(self) -> tuple[bool]:
        return (self.result,)


class FakePostgresConnection:
    def __init__(
        self,
        *,
        fail_unlock: bool = False,
        try_results: list[bool] | None = None,
    ) -> None:
        self.statements: list[tuple[str, tuple[int, ...]]] = []
        self.fail_unlock = fail_unlock
        self.try_results = list(try_results or [])
        self.closed = False

    def execute(self, sql: str, parameters: tuple[int, ...]) -> FakeCursor:
        self.statements.append((sql, parameters))
        if self.fail_unlock and "pg_advisory_unlock" in sql:
            raise RuntimeError("unlock failed")
        if "pg_try_advisory_lock" in sql and self.try_results:
            return FakeCursor(self.try_results.pop(0))
        return FakeCursor()

    def close(self) -> None:
        self.closed = True


class DomainError(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
