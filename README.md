# ducklake-client

Lightweight Python helpers for opening DuckLake connections through DuckDB.

## Install

```bash
pip install ducklake-client
```

## Open a DuckLake connection

```python
from ducklake_client import DuckLake

lake = DuckLake(
    catalog="metadata.ducklake",
    storage="data",
)

try:
    lake.execute("CREATE SCHEMA IF NOT EXISTS lake.main")
    lake.execute("CREATE TABLE IF NOT EXISTS lake.main.items (id INTEGER, name VARCHAR)")
    rows = lake.sql("SELECT * FROM lake.main.items").fetchall()
finally:
    lake.close()
```

`DuckLake` opens the underlying DuckDB connection lazily on first use. The wrapper installs and loads the DuckDB `ducklake` and `parquet` extensions, attaches the catalog as `lake`, and exposes the raw DuckDB connection through `raw_connection()`.

## Context manager usage

```python
from ducklake_client import DuckLake

with DuckLake(catalog="metadata.ducklake", storage="data") as lake:
    lake.execute("CREATE TABLE IF NOT EXISTS lake.main.events (id INTEGER)")
    lake.execute("INSERT INTO lake.main.events VALUES (?)", [1])
    print(lake.sql("SELECT count(*) FROM lake.main.events").fetchone())
```

## Transactions

Use `transaction()` to group statements on the same DuckDB connection. The transaction commits when the context exits normally and rolls back if an exception is raised.

```python
from ducklake_client import DuckLake

with DuckLake(catalog="metadata.ducklake", storage="data") as lake:
    with lake.transaction() as tx:
        tx.execute("CREATE TABLE IF NOT EXISTS lake.main.items (id INTEGER, name VARCHAR)")
        tx.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])
```

## Configuration

Local filesystem paths can be passed as plain strings:

```python
lake = DuckLake(catalog="metadata.ducklake", storage="data")
```

You can also use explicit config objects:

```python
from ducklake_client import DuckDBConfig, DuckDBCatalog, DuckLake, FileStorage

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=FileStorage("data"),
    duckdb=DuckDBConfig(
        database=":memory:",
        threads=4,
        memory_limit="2GB",
    ),
)
```

SQLite, Postgres, and S3 configs are available through `SqliteCatalog`, `PostgresCatalog`, and `S3Storage`.
