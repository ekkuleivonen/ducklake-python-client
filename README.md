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
    lake.table.create_from_csv(
        "nl_train_stations",
        "https://blobs.duckdb.org/nl_stations.csv",
    )
    lake.table.comment("nl_train_stations", "Dutch railway stations")
    lake.table.comment(
        "nl_train_stations",
        "Full station name",
        column_name="name_long",
    )
    tables = lake.table.list()
    views = lake.view.list()
    # Metadata-only by default: this does not scan the table data.
    info = lake.table.info("nl_train_stations")

    # Summary statistics and an exact row count both scan table data.
    detailed_info = lake.table.info(
        "nl_train_stations",
        include_summary=True,
        include_row_count=True,
    )
```

## Ad hoc SQL as dict rows

For quick queries with named parameters (DuckDB ``$param`` syntax), use ``sql_dicts``:

```python
from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    rows = lake.sql_dicts("SELECT $n AS v", n=41)
```

## Transactions

Use `transaction()` to automatically begin, commit, or roll back a block on the native DuckDB connection.

```python
from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake

with DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
) as lake:
    with lake.transaction():
        lake.schema.create("main")
        lake.table.create(
            "items",
            id=ColumnDef("INTEGER", nullable=False),
            name=ColumnDef("VARCHAR"),
        )
        lake.connection.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])
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
