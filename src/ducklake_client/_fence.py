"""Cooperative fencing across DuckLake catalog backends."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias

from ducklake_client.config import (
    CatalogConfig,
    DuckDBCatalog,
    PostgresCatalog,
    SqliteCatalog,
)
from ducklake_client.exceptions import (
    DuckLakeConfigError,
    DuckLakeFenceError,
    DuckLakeFenceTimeout,
)

FenceKey: TypeAlias = str | int | bytes

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def catalog_fence(
    catalog: CatalogConfig,
    keys: tuple[FenceKey, ...],
    *,
    namespace: str,
    timeout: float | None,
) -> Iterator[None]:
    """Acquire the strongest cooperative fence available for a catalog."""

    identity = _fence_identity(keys, namespace=namespace)
    _validate_timeout(timeout)

    if isinstance(catalog, PostgresCatalog):
        with _postgres_fence(catalog, identity, timeout=timeout):
            yield
        return
    if isinstance(catalog, DuckDBCatalog | SqliteCatalog):
        with _local_catalog_fence(catalog, identity, timeout=timeout):
            yield
        return
    raise DuckLakeConfigError(f"unsupported fence catalog: {type(catalog).__name__}")


def _fence_identity(keys: tuple[FenceKey, ...], *, namespace: str) -> bytes:
    if not namespace:
        raise DuckLakeConfigError("fence namespace must not be empty")
    if not keys:
        raise DuckLakeConfigError("fence requires at least one key")

    digest = hashlib.blake2b(digest_size=16, person=b"ducklake-fence")
    digest.update(namespace.encode("utf-8"))
    for key in keys:
        encoded = _encode_key(key)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.digest()


def _encode_key(key: FenceKey) -> bytes:
    if isinstance(key, bool):
        return b"bool:true" if key else b"bool:false"
    if isinstance(key, str):
        return b"str:" + key.encode("utf-8")
    if isinstance(key, int):
        return b"int:" + str(key).encode("ascii")
    if isinstance(key, bytes):
        return b"bytes:" + key
    raise DuckLakeConfigError(
        f"fence keys must be str, int, or bytes, got {type(key).__name__}"
    )


def _validate_timeout(timeout: float | None) -> None:
    if timeout is None:
        return
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        raise DuckLakeConfigError("fence timeout must be a number or None")
    if timeout < 0:
        raise DuckLakeConfigError("fence timeout must not be negative")


@contextmanager
def _postgres_fence(
    catalog: PostgresCatalog,
    identity: bytes,
    *,
    timeout: float | None,
) -> Iterator[None]:
    lock_key = int.from_bytes(identity[:8], "big", signed=True)
    try:
        import psycopg

        with psycopg.connect(catalog.dsn, autocommit=True) as connection:
            if timeout is None:
                connection.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
            else:
                deadline = time.monotonic() + timeout
                while True:
                    row = connection.execute(
                        "SELECT pg_try_advisory_lock(%s)", (lock_key,)
                    ).fetchone()
                    if row and bool(row[0]):
                        break
                    if time.monotonic() >= deadline:
                        raise DuckLakeFenceTimeout("timed out waiting for PostgreSQL fence")
                    time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            try:
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
    except DuckLakeFenceTimeout:
        raise
    except Exception as exc:
        raise DuckLakeFenceError("PostgreSQL fence failed") from exc


@contextmanager
def _local_catalog_fence(
    catalog: DuckDBCatalog | SqliteCatalog,
    identity: bytes,
    *,
    timeout: float | None,
) -> Iterator[None]:
    catalog_path = str(catalog.path)
    lock_path = _lock_path(catalog_path, identity)
    registry_key = f"{type(catalog).__name__}:{_canonical_path(catalog_path)}:{identity.hex()}"
    local_lock = _process_lock(registry_key)
    deadline = None if timeout is None else time.monotonic() + timeout

    if not _acquire_process_lock(local_lock, deadline):
        raise DuckLakeFenceTimeout("timed out waiting for local catalog fence")
    handle = None
    try:
        if lock_path is not None:
            try:
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                handle = lock_path.open("a+b")
                _acquire_file_lock(handle, deadline)
            except DuckLakeFenceTimeout:
                raise
            except Exception as exc:
                raise DuckLakeFenceError("local catalog fence failed") from exc
        yield
    finally:
        if handle is not None:
            _release_file_lock(handle)
            handle.close()
        local_lock.release()


def _process_lock(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def _acquire_process_lock(lock: threading.Lock, deadline: float | None) -> bool:
    if deadline is None:
        lock.acquire()
        return True
    return lock.acquire(timeout=max(0.0, deadline - time.monotonic()))


def _lock_path(catalog_path: str, identity: bytes) -> Path | None:
    if catalog_path == ":memory:":
        return None
    path = Path(catalog_path).expanduser().absolute()
    directory = path.parent / f".{path.name}.ducklake-client-locks"
    return directory / f"{identity.hex()}.lock"


def _canonical_path(catalog_path: str) -> str:
    if catalog_path == ":memory:":
        return f":memory:{os.getpid()}"
    return str(Path(catalog_path).expanduser().absolute())


def _acquire_file_lock(handle: object, deadline: float | None) -> None:
    try:
        import fcntl
    except ImportError:
        return

    if deadline is None:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise DuckLakeFenceTimeout("timed out waiting for catalog file fence")
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _release_file_lock(handle: object) -> None:
    try:
        import fcntl
    except ImportError:
        return
    try:
        fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        pass
