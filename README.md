# ducklake-client

Lightweight Python helpers for opening DuckLake connections through DuckDB.

## Install

```bash
pip install ducklake-client
```

## Open a DuckLake connection

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
)

try:
    lake.create_schema("main")
    lake.create_table(
        "items",
        id=ColumnDef("INTEGER", nullable=False),
        name=ColumnDef("VARCHAR"),
    )
    rows = lake.sql("SELECT * FROM lake.main.items").fetchall()
finally:
    lake.close()
```

`DuckLake` opens the underlying DuckDB connection lazily on first use. The wrapper installs and loads the DuckDB `ducklake` and `parquet` extensions, attaches the catalog as `lake`, and exposes the raw DuckDB connection through `raw_connection()`.

## Context manager usage

```python
from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.execute("CREATE TABLE IF NOT EXISTS lake.main.events (id INTEGER)")
    lake.execute("INSERT INTO lake.main.events VALUES (?)", [1])
    print(lake.sql("SELECT count(*) FROM lake.main.events").fetchone())
```

## Methods

Client methods live under `ducklake_client.methods`, with each method in its own directory containing `method.py` and `template.sql`.

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.create_schema("main")
    lake.create_table(
        "items",
        id=ColumnDef("INTEGER", nullable=False),
        name=ColumnDef("VARCHAR"),
    )
```

## Transactions

Use `transaction()` to group statements on the same DuckDB connection. The transaction commits when the context exits normally and rolls back if an exception is raised.

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    with lake.transaction() as tx:
        tx.create_schema("main")
        tx.create_table(
            "items",
            id=ColumnDef("INTEGER", nullable=False),
            name=ColumnDef("VARCHAR"),
        )
        tx.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])
```

## Configuration

`DuckLake` requires explicit catalog and storage config objects:

```python
from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
)
```

You can pass DuckDB runtime settings with `DuckDBConfig`:

```python
from ducklake_client import DiskStorage, DuckDBConfig, DuckDBCatalog, DuckLake

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
    duckdb=DuckDBConfig(
        database=":memory:",
        threads=4,
        memory_limit="2GB",
    ),
)
```

Catalogs can be `DuckDBCatalog`, `SqliteCatalog`, or `PostgresCatalog`. Storage can be `DiskStorage` or `S3Storage`.
