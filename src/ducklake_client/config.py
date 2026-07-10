"""Typed configuration for DuckLake connections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias
from urllib.parse import urlsplit, urlunsplit

from ducklake_client.exceptions import DuckLakeConfigError


class CatalogConfig:
    """Base class for DuckLake catalog configuration."""

    def attach_uri(self) -> str:
        raise NotImplementedError

    def attach_options(self) -> Mapping[str, object]:
        return {}

    def required_extensions(self) -> tuple[str, ...]:
        return ()


class StorageConfig:
    """Base class for DuckLake data storage configuration."""

    def data_path(self) -> str:
        raise NotImplementedError

    def required_extensions(self) -> tuple[str, ...]:
        return ()

    def setup_statements(self, *, secret_name: str) -> tuple[str, ...]:
        return ()


DuckDBConfigValue: TypeAlias = str | bool | int | float | list[str]
DuckDBSettingValue: TypeAlias = str | bool | int | float
DuckDBSettings: TypeAlias = Mapping[str, DuckDBSettingValue]


@dataclass(frozen=True)
class DuckLakeAttachConfig:
    """Typed options applied when attaching a DuckLake catalog."""

    create_if_not_exists: bool | None = None
    data_inlining_row_limit: int | None = None
    encrypted: bool | None = None
    automatic_migration: bool | None = None
    override_data_path: bool | None = None

    def __post_init__(self) -> None:
        limit = self.data_inlining_row_limit
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
            raise DuckLakeConfigError("data_inlining_row_limit must be an integer")
        if limit is not None and limit < 0:
            raise DuckLakeConfigError("data_inlining_row_limit must not be negative")

    def options(self) -> dict[str, object]:
        values = {
            "CREATE_IF_NOT_EXISTS": self.create_if_not_exists,
            "DATA_INLINING_ROW_LIMIT": self.data_inlining_row_limit,
            "ENCRYPTED": self.encrypted,
            "AUTOMATIC_MIGRATION": self.automatic_migration,
            "OVERRIDE_DATA_PATH": self.override_data_path,
        }
        return {name: value for name, value in values.items() if value is not None}


@dataclass(frozen=True)
class DuckDBCatalog(CatalogConfig):
    """A DuckDB-backed DuckLake catalog."""

    path: str | Path

    def __post_init__(self) -> None:
        _require_not_empty("path", self.path)

    def attach_uri(self) -> str:
        return f"ducklake:{self.path}"


@dataclass(frozen=True)
class SqliteCatalog(CatalogConfig):
    """A DuckLake catalog stored in SQLite."""

    path: str | Path

    def __post_init__(self) -> None:
        _require_not_empty("path", self.path)

    def attach_uri(self) -> str:
        return f"ducklake:sqlite:{self.path}"

    def attach_options(self) -> Mapping[str, object]:
        return {
            "META_JOURNAL_MODE": "WAL",
            "META_BUSY_TIMEOUT": 5000,
        }

    def required_extensions(self) -> tuple[str, ...]:
        return ("sqlite",)


@dataclass(frozen=True)
class PostgresCatalog(CatalogConfig):
    """A DuckLake catalog stored in PostgreSQL."""

    dsn: str

    def __post_init__(self) -> None:
        _require_not_empty("dsn", self.dsn)

    def attach_uri(self) -> str:
        return f"ducklake:postgres:{self.dsn}"

    def required_extensions(self) -> tuple[str, ...]:
        return ("postgres",)


@dataclass(frozen=True)
class DiskStorage(StorageConfig):
    """Local filesystem data storage."""

    path: str | Path

    def __post_init__(self) -> None:
        _require_not_empty("path", self.path)

    def data_path(self) -> str:
        return str(self.path)


@dataclass(frozen=True)
class S3Storage(StorageConfig):
    """S3-compatible object storage for DuckLake data files."""

    bucket: str
    prefix: str = ""
    endpoint: str | None = None
    region: str | None = None
    key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    url_style: str | None = None
    use_ssl: bool | None = None
    extra_secret_options: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_not_empty("bucket", self.bucket)

    def data_path(self) -> str:
        suffix = f"/{self.prefix.lstrip('/')}" if self.prefix else ""
        return f"s3://{self.bucket}{suffix}"

    def required_extensions(self) -> tuple[str, ...]:
        return ("httpfs",)

    def setup_statements(self, *, secret_name: str) -> tuple[str, ...]:
        options: dict[str, str | bool] = {}
        if self.key_id:
            options["KEY_ID"] = self.key_id
        if self.secret_access_key:
            options["SECRET"] = self.secret_access_key
        if self.session_token:
            options["SESSION_TOKEN"] = self.session_token
        if self.region:
            options["REGION"] = self.region
        if self.endpoint:
            options["ENDPOINT"] = _endpoint_host(self.endpoint)
        if self.url_style:
            options["URL_STYLE"] = self.url_style
        if self.use_ssl is not None:
            options["USE_SSL"] = self.use_ssl
        for key, value in self.extra_secret_options.items():
            options[key.upper()] = value

        if not options:
            return ()

        rendered = ", ".join(
            ["TYPE s3", *(f"{key} {_format_secret_value(value)}" for key, value in options.items())]
        )
        return (f"CREATE OR REPLACE SECRET {quote_identifier(secret_name)} ({rendered})",)


@dataclass(frozen=True)
class DuckDBConfig:
    """DuckDB connection and runtime settings for a DuckLake client."""

    database: str | Path = ":memory:"
    config: Mapping[str, DuckDBConfigValue] = field(default_factory=dict)
    extensions: tuple[str, ...] = ()
    settings: DuckDBSettings = field(default_factory=dict)
    install_extensions: bool = True
    threads: int | None = None
    memory_limit: str | None = None
    max_temp_directory_size: str | None = None
    temp_directory: str | Path | None = None
    s3_uploader_max_filesize: str | None = None

    def runtime_settings(self) -> dict[str, DuckDBSettingValue]:
        settings = dict(self.settings)
        explicit_settings: dict[str, DuckDBSettingValue] = {}
        if self.threads is not None:
            explicit_settings["threads"] = self.threads
        if self.memory_limit is not None:
            explicit_settings["memory_limit"] = self.memory_limit
        if self.max_temp_directory_size is not None:
            explicit_settings["max_temp_directory_size"] = self.max_temp_directory_size
        if self.temp_directory is not None:
            explicit_settings["temp_directory"] = str(self.temp_directory)
        if self.s3_uploader_max_filesize is not None:
            explicit_settings["s3_uploader_max_filesize"] = self.s3_uploader_max_filesize

        duplicates = set(settings).intersection(explicit_settings)
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise DuckLakeConfigError(f"DuckDB settings specified more than once: {names}")
        settings.update(explicit_settings)
        return settings


CatalogInput: TypeAlias = DuckDBCatalog | PostgresCatalog | SqliteCatalog
StorageInput: TypeAlias = DiskStorage | S3Storage


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _endpoint_host(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if parsed.scheme and parsed.netloc:
        return urlunsplit(("", parsed.netloc, parsed.path, "", "")).removeprefix("//")
    return endpoint


def _format_secret_value(value: str | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return quote_literal(value)


def _require_not_empty(name: str, value: object) -> None:
    if not str(value):
        raise DuckLakeConfigError(f"{name} must not be empty")
