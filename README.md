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
    lake.schema.create("main")
    lake.table.create(
        "items",
        id=ColumnDef("INTEGER", nullable=False),
        name=ColumnDef("VARCHAR"),
    )
    rows = lake.connection.sql("SELECT * FROM lake.main.items").fetchall()
finally:
    lake.close()
```

`DuckLake` opens the underlying DuckDB connection lazily on first use. The client installs and loads the DuckDB `ducklake` and `parquet` extensions, attaches the catalog as `lake`, and exposes the native DuckDB connection through `connection`.

## Context manager usage

```python
from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.connection.execute("CREATE TABLE IF NOT EXISTS lake.main.events (id INTEGER)")
    lake.connection.execute("INSERT INTO lake.main.events VALUES (?)", [1])
    print(lake.connection.sql("SELECT count(*) FROM lake.main.events").fetchone())
```

## Modules

DuckLake-specific helpers are grouped into modules. Native DuckDB behavior stays on `lake.connection`.

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
    tables = lake.table.list()
    views = lake.view.list()
    info = lake.table.info("items")
```

## Transactions

Use DuckDB's native transaction methods on `lake.connection`.

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    lake.connection.begin()
    try:
        lake.schema.create("main")
        lake.table.create(
            "items",
            id=ColumnDef("INTEGER", nullable=False),
            name=ColumnDef("VARCHAR"),
        )
        lake.connection.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])
        lake.connection.commit()
    except Exception:
        lake.connection.rollback()
        raise
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
