"""Cooperative fencing across DuckLake catalog backends."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

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
FenceMode: TypeAlias = Literal["exclusive", "shared"]


@dataclass(frozen=True, slots=True)
class FenceSpec:
    """One independently contended identity in a cooperative fence set."""

    keys: tuple[FenceKey, ...]
    mode: FenceMode = "exclusive"

    def __post_init__(self) -> None:
        if not self.keys:
            raise DuckLakeConfigError("fence requires at least one key")
        if self.mode not in ("exclusive", "shared"):
            raise DuckLakeConfigError(f"unsupported fence mode: {self.mode!r}")
        for key in self.keys:
            _encode_key(key)

    @classmethod
    def exclusive(cls, *keys: FenceKey) -> FenceSpec:
        return cls(keys=keys, mode="exclusive")

    @classmethod
    def shared(cls, *keys: FenceKey) -> FenceSpec:
        return cls(keys=keys, mode="shared")


@dataclass(frozen=True, slots=True)
class _FenceIdentity:
    value: bytes
    mode: FenceMode

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

    with catalog_fence_set(
        catalog,
        (FenceSpec(keys),),
        namespace=namespace,
        timeout=timeout,
    ):
        yield


@contextmanager
def catalog_fence_set(
    catalog: CatalogConfig,
    fences: tuple[FenceSpec, ...],
    *,
    namespace: str,
    timeout: float | None,
) -> Iterator[None]:
    """Acquire independently contended fences through one backend session."""

    identities = _fence_identities(fences, namespace=namespace)
    _validate_timeout(timeout)

    if isinstance(catalog, PostgresCatalog):
        with _postgres_fence_set(catalog, identities, timeout=timeout):
            yield
        return
    if isinstance(catalog, DuckDBCatalog | SqliteCatalog):
        with _local_catalog_fence_set(catalog, identities, timeout=timeout):
            yield
        return
    raise DuckLakeConfigError(f"unsupported fence catalog: {type(catalog).__name__}")


def _fence_identities(
    fences: tuple[FenceSpec, ...], *, namespace: str
) -> tuple[_FenceIdentity, ...]:
    if not fences:
        raise DuckLakeConfigError("fence set requires at least one fence")
    by_identity: dict[bytes, FenceMode] = {}
    for fence in fences:
        identity = _fence_identity(fence.keys, namespace=namespace)
        current = by_identity.get(identity)
        if current is None or fence.mode == "exclusive":
            by_identity[identity] = fence.mode
    return tuple(
        _FenceIdentity(value=identity, mode=mode)
        for identity, mode in sorted(by_identity.items())
    )


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
def _postgres_fence_set(
    catalog: PostgresCatalog,
    identities: tuple[_FenceIdentity, ...],
    *,
    timeout: float | None,
) -> Iterator[None]:
    connection = None
    acquired: list[tuple[int, FenceMode]] = []
    try:
        import psycopg

        connection = psycopg.connect(catalog.dsn, autocommit=True)
        deadline = None if timeout is None else time.monotonic() + timeout
        locks = _postgres_locks(identities)
        for lock_key, mode in locks:
            _acquire_postgres_fence(
                connection,
                lock_key,
                mode=mode,
                deadline=deadline,
            )
            acquired.append((lock_key, mode))
    except DuckLakeFenceTimeout:
        _release_postgres_fences_quietly(connection, acquired)
        _close_quietly(connection)
        raise
    except Exception as exc:
        _release_postgres_fences_quietly(connection, acquired)
        _close_quietly(connection)
        raise DuckLakeFenceError("PostgreSQL fence acquisition failed") from exc

    try:
        yield
    except BaseException as body_error:
        try:
            _release_postgres_fences(connection, acquired)
        except Exception as release_error:
            body_error.add_note(
                f"PostgreSQL fence release also failed: {release_error!r}"
            )
        raise
    else:
        try:
            _release_postgres_fences(connection, acquired)
        except Exception as exc:
            raise DuckLakeFenceError("PostgreSQL fence release failed") from exc


def _postgres_locks(
    identities: tuple[_FenceIdentity, ...],
) -> tuple[tuple[int, FenceMode], ...]:
    by_key: dict[int, FenceMode] = {}
    for identity in identities:
        key = int.from_bytes(identity.value[:8], "big", signed=True)
        current = by_key.get(key)
        if current is None or identity.mode == "exclusive":
            by_key[key] = identity.mode
    return tuple(sorted(by_key.items()))


def _acquire_postgres_fence(
    connection: object,
    lock_key: int,
    *,
    mode: FenceMode,
    deadline: float | None,
) -> None:
    suffix = "_shared" if mode == "shared" else ""
    if deadline is None:
        connection.execute(f"SELECT pg_advisory_lock{suffix}(%s)", (lock_key,))
        return

    while True:
        row = connection.execute(
            f"SELECT pg_try_advisory_lock{suffix}(%s)", (lock_key,)
        ).fetchone()
        if row and bool(row[0]):
            return
        if time.monotonic() >= deadline:
            raise DuckLakeFenceTimeout("timed out waiting for PostgreSQL fence")
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _release_postgres_fences(
    connection: object, acquired: list[tuple[int, FenceMode]]
) -> None:
    release_errors: list[Exception] = []
    try:
        for lock_key, mode in reversed(acquired):
            suffix = "_shared" if mode == "shared" else ""
            try:
                connection.execute(
                    f"SELECT pg_advisory_unlock{suffix}(%s)", (lock_key,)
                )
            except Exception as exc:
                release_errors.append(exc)
    finally:
        try:
            connection.close()
        except Exception as exc:
            release_errors.append(exc)
    if release_errors:
        error = release_errors[0]
        for extra in release_errors[1:]:
            error.add_note(f"additional PostgreSQL fence release failure: {extra!r}")
        raise error


def _release_postgres_fences_quietly(
    connection: object | None, acquired: list[tuple[int, FenceMode]]
) -> None:
    if connection is None:
        return
    for lock_key, mode in reversed(acquired):
        suffix = "_shared" if mode == "shared" else ""
        try:
            connection.execute(f"SELECT pg_advisory_unlock{suffix}(%s)", (lock_key,))
        except Exception:
            pass


def _close_quietly(connection: object | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except Exception:
        pass


@contextmanager
def _local_catalog_fence_set(
    catalog: DuckDBCatalog | SqliteCatalog,
    identities: tuple[_FenceIdentity, ...],
    *,
    timeout: float | None,
) -> Iterator[None]:
    catalog_path = str(catalog.path)
    deadline = None if timeout is None else time.monotonic() + timeout
    acquired_locks: list[threading.Lock] = []
    handles: list[object] = []
    try:
        for identity in identities:
            registry_key = (
                f"{type(catalog).__name__}:{_canonical_path(catalog_path)}:"
                f"{identity.value.hex()}"
            )
            local_lock = _process_lock(registry_key)
            if not _acquire_process_lock(local_lock, deadline):
                raise DuckLakeFenceTimeout("timed out waiting for local catalog fence")
            acquired_locks.append(local_lock)

            lock_path = _lock_path(catalog_path, identity.value)
            if lock_path is not None:
                handle = None
                try:
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    handle = lock_path.open("a+b")
                    _acquire_file_lock(handle, deadline)
                    handles.append(handle)
                except DuckLakeFenceTimeout:
                    if handle is not None:
                        handle.close()
                    raise
                except Exception as exc:
                    if handle is not None:
                        handle.close()
                    raise DuckLakeFenceError("local catalog fence failed") from exc
        yield
    finally:
        for handle in reversed(handles):
            _release_file_lock(handle)
            handle.close()
        for local_lock in reversed(acquired_locks):
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
