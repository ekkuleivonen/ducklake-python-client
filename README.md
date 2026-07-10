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

Nested and parameterized column types can be composed without writing native SQL:

```python
from ducklake_client import ColumnDef, ListType, MapType, StructType

lake.table.create(
    "elements",
    attributes=ColumnDef(MapType("VARCHAR", "VARCHAR")),
    tags=ColumnDef(ListType("VARCHAR")),
    location=ColumnDef(StructType({"latitude": "DOUBLE", "longitude": "DOUBLE"})),
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

Common DuckLake `ATTACH` settings have a typed configuration object:

```python
from ducklake_client import (
    DiskStorage,
    DuckDBCatalog,
    DuckLake,
    DuckLakeAttachConfig,
)

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=DiskStorage("data"),
    attach=DuckLakeAttachConfig(
        data_inlining_row_limit=50,
        automatic_migration=False,
    ),
)
```

`data_inlining_row_limit=0` disables data inlining for the connection. Typed
options also cover `create_if_not_exists`, `encrypted`, and
`override_data_path`. Less common or extension-version-specific parameters can
still be passed through `attach_options`; when both forms specify the same key,
`attach_options` takes precedence.

Catalogs can be `DuckDBCatalog`, `SqliteCatalog`, or `PostgresCatalog`. Storage can be `DiskStorage` or `S3Storage`.

### Bootstrap behavior

`schema.create`, `table.create`, and `table.create_from_csv` are idempotent by
default: each uses `IF NOT EXISTS`. Pass `if_not_exists=False` when an existing
object should be reported as an error. An idempotent create does not reconcile
or migrate the definition of an object that already exists.

### S3 storage

Configure S3 and S3-compatible storage through `S3Storage`; native secret SQL is
not required:

```python
import os

from ducklake_client import DuckDBCatalog, DuckLake, S3Storage

lake = DuckLake(
    catalog=DuckDBCatalog("metadata.ducklake"),
    storage=S3Storage(
        bucket="atlas-data",
        prefix="ducklake",
        region="eu-west-1",
        key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        session_token=os.environ.get("AWS_SESSION_TOKEN"),
    ),
)
```

`endpoint`, `url_style`, and `use_ssl` support S3-compatible services. When no
secret options are supplied, the client does not create a DuckDB secret; access
then depends on credentials already available in the DuckDB environment.

For a local MinIO server, provide the endpoint without embedding credentials and
use path-style URLs:

```python
from ducklake_client import ColumnDef, DuckDBCatalog, DuckLake, S3Storage

with DuckLake(
    # The catalog is durable because this is a file, not ":memory:".
    catalog=DuckDBCatalog("state/atlas.ducklake"),
    storage=S3Storage(
        bucket="atlas-data",
        prefix="ducklake",
        endpoint="http://localhost:9000",
        key_id="minioadmin",
        secret_access_key="minioadmin",
        url_style="path",
        use_ssl=False,
    ),
) as lake:
    lake.schema.create("main")
    lake.table.create(
        "events",
        id=ColumnDef("BIGINT", nullable=False),
        payload=ColumnDef("JSON"),
    )
```

The S3 settings have these roles:

- `endpoint` selects an S3-compatible service such as MinIO. A URL is accepted;
  the client passes its host and optional port to DuckDB.
- `url_style="path"` produces bucket paths suitable for typical local MinIO
  setups. Use the service's required style in other environments.
- `use_ssl` controls HTTPS independently of the endpoint spelling.
- `key_id`, `secret_access_key`, and `session_token` create a temporary DuckDB
  secret managed by this client. If they and all other secret options are absent,
  no secret is created; configure credentials in DuckDB or its environment before
  accessing private objects.

S3 stores DuckLake data files, not the DuckLake catalog itself. Catalog durability
is configured separately: `DuckDBCatalog` and `SqliteCatalog` persist metadata at
their filesystem paths, while `PostgresCatalog` persists it in PostgreSQL. Keep
the catalog on durable storage and back it up independently of the S3 bucket. A
catalog path inside an ephemeral container will be lost even when its data files
remain in S3.

### Exceptions

The package exception hierarchy is public API:

- `DuckLakeError` is the base package exception.
- `DuckLakeConfigError` reports invalid client configuration or helper input.
- `DuckLakeConnectionError` reports connection initialization failures.
- `DuckLakeQueryError` reports failures from client and module query helpers.

The original exception is retained as `__cause__`. Operations performed directly
through `lake.connection` remain native DuckDB operations and raise DuckDB's own
exceptions.
