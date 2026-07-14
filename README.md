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

Append a microbatch from mapping records without constructing native SQL:

```python
lake.table.append(
    "elements",
    [
        {"id": 1, "attributes": {"color": "green"}},
        {"id": 2, "attributes": {"color": "blue"}},
    ],
)
```

`table.append` matches columns by name and also accepts Arrow `Table`,
`RecordBatch`, and `RecordBatchReader` objects. A `DuckDBPyRelation` created from
the same `lake.connection` is accepted directly:

```python
batch = lake.connection.sql("SELECT id, attributes FROM staging_elements")
lake.table.append("elements", batch)
```

Empty record batches are a no-op. Each non-empty append is issued as one insert
statement. Arrow support does not require importing PyArrow in
`ducklake-client`; the provided object must implement an Arrow C data interface.

### Fenced and idempotent appends

DuckLake tables do not enforce unique or primary-key constraints. `table.append`
therefore provides at-least-once writes by itself. Use a cooperative fence plus a
transaction when a retried microbatch must not be appended twice:

```python
batch_id = "atlas-elements-2026-07-11T00:00:00Z"

with lake.fence("atlas", "elements", batch_id, timeout=30):
    with lake.transaction():
        already_ingested = lake.sql_scalar(
            """
            SELECT EXISTS (
                SELECT 1
                FROM lake.main.ingestion_batches
                WHERE batch_id = $batch_id
            )
            """,
            batch_id=batch_id,
        )
        if not already_ingested:
            lake.table.append("elements", records)
            lake.table.append("ingestion_batches", [{"batch_id": batch_id}])
```

Create the marker table once during bootstrap. The fence serializes cooperating
writers for the same keys; the transaction makes the marker and data append
commit or roll back together. Every writer for that idempotency domain must use
the same fence namespace and keys.

When one mutation overlaps several independent identities, acquire them as one
fence set. Unlike passing several keys to `fence()`, each `FenceSpec` remains an
independent contention domain. The backend acquires the complete set in a stable
order through one session and one overall timeout:

```python
from ducklake_client import FenceSpec

with lake.fence_set(
    FenceSpec.shared("maintenance"),
    FenceSpec.exclusive("crawl", crawl_id),
    FenceSpec.exclusive("content", document_id),
    namespace="atlas",
    timeout=30,
):
    with lake.transaction():
        # Resolve authoritative state and commit while every identity is fenced.
        ...
```

Fence sets deduplicate identities and upgrade a duplicated shared identity to
exclusive. PostgreSQL uses one advisory-lock session for the whole set. Local
catalogs conservatively serialize shared fences as exclusive file/process locks.

Fence guarantees depend on the catalog:

- `PostgresCatalog` uses PostgreSQL session advisory locks and supports remote,
  cross-process writers. The lock is released if its connection closes or the
  process exits.
- File-backed `DuckDBCatalog` and `SqliteCatalog` use advisory sidecar file locks
  plus process-local locks. They coordinate processes that share a filesystem
  with working advisory-lock semantics and all use this client.
- In-memory DuckDB catalogs and platforms without advisory file locking fall
  back to process-local exclusion only.

Fencing is cooperative rather than a DuckLake uniqueness constraint. It cannot
exclude writers that bypass `lake.fence`, and filesystem locks may not be reliable
on every network filesystem. `DuckLakeFenceTimeout` reports acquisition timeout;
other backend failures raise `DuckLakeFenceError`.

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

The package includes `pytz`, which DuckDB requires when materializing
`TIMESTAMPTZ` values as Python objects.

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
- `DuckLakeFenceError` reports cooperative fencing failures, with
  `DuckLakeFenceTimeout` for acquisition timeouts.
- `DuckLakeQueryError` reports failures from client and module query helpers.

The original exception is retained as `__cause__`. Operations performed directly
through `lake.connection` remain native DuckDB operations and raise DuckDB's own
exceptions.
