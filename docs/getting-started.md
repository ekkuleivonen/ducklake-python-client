# Getting started with ducklake-client

`ducklake-client` is a thin Python wrapper around DuckDB for opening a DuckLake catalog, attaching it as a named database, and exposing a few higher-level helpers for common catalog tasks.

## Quick path

1. Create a `DuckLake` with a catalog config and a storage config.
2. Use it inside `with DuckLake(...) as lake:` or call `lake.close()` yourself.
3. Use `lake.schema`, `lake.table`, `lake.view`, `lake.snapshots`, or the native `lake.connection`.

## Minimal example

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.schema.create("main")
    lake.table.create(
        "items",
        id=ColumnDef("INTEGER", nullable=False),
        name=ColumnDef("VARCHAR"),
    )

    rows = lake.connection.sql("SELECT * FROM lake.main.items").fetchall()
```

## Connection lifecycle

### 1. Construction is cheap

Creating `DuckLake(...)` does **not** open DuckDB immediately. The connection is created on first use of:

- `lake.connection`
- any module call such as `lake.schema.create(...)`
- entering the context manager with `with DuckLake(...) as lake:`

### 2. First use initializes the environment

On first access, the client:

1. Opens a DuckDB connection.
2. Applies DuckDB runtime settings.
3. Installs and loads required extensions.
4. Runs storage setup SQL when needed.
5. Executes `ATTACH ... AS <alias>` for the DuckLake catalog.

After that, all helpers share the same DuckDB connection.

### 3. Close explicitly when you are done

- Preferred: `with DuckLake(...) as lake:`
- Alternative: `lake.close()`

`close()` shuts down the underlying DuckDB connection and resets the lazy manager.

## Common usage flows

### Create schema and table

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.schema.create("main")
    lake.table.create(
        "events",
        id=ColumnDef("INTEGER", nullable=False),
        name=ColumnDef("VARCHAR"),
    )
```

### Load a table from CSV

```python
with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.table.create_from_csv(
        "stations",
        "https://blobs.duckdb.org/nl_stations.csv",
    )
```

### Run ad hoc SQL

Use the native connection when you want full DuckDB behavior:

```python
count = lake.connection.sql("SELECT count(*) FROM lake.main.events").fetchone()[0]
```

Use convenience helpers when you want Python-friendly results:

```python
rows = lake.sql_dicts("SELECT $n AS value", n=41)
one = lake.sql_one("SELECT 42 AS answer")
value = lake.sql_scalar("SELECT count(*) FROM lake.main.events")
```

### Group changes in a transaction

```python
with lake.transaction():
    lake.schema.create("main")
    lake.table.create("items", id=ColumnDef("INTEGER", nullable=False))
```

`transaction()` begins on entry, commits on success, and rolls back on failure.

## What the wrapper does not hide

This library is intentionally small. It does **not** replace DuckDB APIs.

Use `lake.connection` for:

- custom SQL
- inserts and reads
- advanced DuckDB features
- anything not covered by the helper modules

## Practical notes

| Topic | Behavior |
|------|----------|
| Default alias | The attached DuckLake catalog is exposed as `lake` unless you override `alias` |
| Default DuckDB database | `:memory:` |
| Default schema for helpers | `main` for table-oriented helpers |
| Error model | Invalid input raises `DuckLakeConfigError`; connection setup failures raise `DuckLakeConnectionError`; query wrapper failures raise `DuckLakeQueryError` |

## Next step

Read [configuration.md](./configuration.md) before choosing non-default catalog or storage backends.
