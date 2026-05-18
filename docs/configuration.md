# Configuration model

`DuckLake` needs two explicit configuration objects: one for the DuckLake catalog and one for the data storage. DuckDB runtime behavior is configured separately.

## Quick path

1. Pick a catalog class: `DuckDBCatalog`, `SqliteCatalog`, or `PostgresCatalog`.
2. Pick a storage class: `DiskStorage` or `S3Storage`.
3. Optionally pass `DuckDBConfig`, a custom `alias`, or extra `attach_options`.

## Constructor shape

```python
DuckLake(
    catalog=...,          # required
    storage=...,          # required
    alias="lake",        # optional
    duckdb=DuckDBConfig(),
    attach_options=None,
)
```

## Configuration overview

| Area | Main types | What they control |
|------|------------|-------------------|
| Catalog | `DuckDBCatalog`, `SqliteCatalog`, `PostgresCatalog` | Where DuckLake metadata lives |
| Storage | `DiskStorage`, `S3Storage` | Where DuckLake data files live |
| DuckDB runtime | `DuckDBConfig` | Database path, config dict, extensions, and runtime settings |
| Attach behavior | `alias`, `attach_options` | The attached database name and extra `ATTACH` options |

## Catalog options

### `DuckDBCatalog(path)`

- Attach URI shape: `ducklake:<path>`
- Best for local DuckDB-backed metadata files

### `SqliteCatalog(path)`

- Attach URI shape: `ducklake:sqlite:<path>`
- Automatically adds SQLite-specific attach options:
  - `META_JOURNAL_MODE = 'WAL'`
  - `META_BUSY_TIMEOUT = 5000`
- Requires the DuckDB `sqlite` extension

### `PostgresCatalog(dsn)`

- Attach URI shape: `ducklake:postgres:<dsn>`
- Requires the DuckDB `postgres` extension

## Storage options

### `DiskStorage(path)`

- Data path is the local directory path as-is
- No extra setup SQL is needed

### `S3Storage(...)`

Builds a `s3://bucket/prefix` data path and can also create a DuckDB secret before attach.

Supported fields include:

- `bucket`
- `prefix`
- `endpoint`
- `region`
- `key_id`
- `secret_access_key`
- `session_token`
- `url_style`
- `use_ssl`
- `extra_secret_options`

If any S3 credential or endpoint options are provided, the client emits:

```sql
CREATE OR REPLACE SECRET <alias>_storage (...)
```

before attaching the catalog.

## DuckDB runtime settings

Use `DuckDBConfig` to control the local DuckDB process.

```python
from ducklake_client import DiskStorage, DuckDBCatalog, DuckDBConfig, DuckLake

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
    duckdb=DuckDBConfig(
        database=":memory:",
        threads=4,
        memory_limit="2GB",
        temp_directory=".tmp/duckdb",
    ),
)
```

### Important `DuckDBConfig` fields

| Field | Meaning |
|------|---------|
| `database` | DuckDB database file or `:memory:` |
| `config` | Passed directly to `duckdb.connect(..., config=...)` |
| `extensions` | Extra DuckDB extensions to load in addition to required ones |
| `settings` | Generic runtime `SET` values |
| `install_extensions` | Controls whether required extensions are installed before loading |
| `threads`, `memory_limit`, `max_temp_directory_size`, `temp_directory`, `s3_uploader_max_filesize` | Convenience fields that become runtime settings |

### Validation rule worth knowing

If a setting is provided twice—once in `settings` and once through a dedicated field like `threads`—the client raises `DuckLakeConfigError`.

## Alias and attach options

### `alias`

The alias becomes the attached DuckLake database name inside DuckDB.

```python
lake = DuckLake(..., alias="warehouse")
```

You would then query relations like:

```sql
SELECT * FROM warehouse.main.items
```

### `attach_options`

These are merged into the generated `ATTACH` statement after built-in options.

- Built-in catalog options are added first.
- `DATA_PATH` from the storage config is always set.
- User `attach_options` are applied last, so they can override earlier values.

## Required extensions

The client deduplicates extensions from all sources and loads them in one pass.

Always included:

- `ducklake`
- `parquet`

Conditionally included:

- catalog-specific extensions such as `sqlite` or `postgres`
- storage-specific extensions such as `httpfs`
- anything added in `DuckDBConfig.extensions`

## Checklist

- [ ] I know which catalog backend I am using.
- [ ] I know which storage backend I am using.
- [ ] I know whether my runtime settings belong in `config`, `settings`, or a dedicated `DuckDBConfig` field.

## Next step

Read [architecture.md](./architecture.md) if you want to understand how these config objects are turned into a live connection.
