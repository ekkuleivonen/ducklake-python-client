# Architecture and internals

`ducklake-client` is small on purpose: configuration objects describe the target environment, a lazy connection manager turns that into a live DuckDB connection, and public modules call focused operation functions.

## Quick path

1. `DuckLake` validates config object types.
2. `ConnectionManager` opens and initializes DuckDB on first use.
3. Public modules delegate to operation functions, which often render SQL from templates.

## High-level flow

```text
DuckLake
  -> ConnectionManager
       -> duckdb.connect(...)
       -> SET runtime settings
       -> install/load extensions
       -> run storage setup statements
       -> ATTACH ducklake catalog AS <alias>
  -> SchemaModule / TableModule / ViewModule / SnapshotsModule
       -> operations/*
            -> SQL templates + typed result objects
```

## Key responsibilities

| Layer | Files | Responsibility |
|------|-------|----------------|
| Public entry point | `client.py` | Exposes `DuckLake`, lifecycle helpers, ad hoc query helpers, and module access |
| Typed config | `config.py` | Defines catalog, storage, and DuckDB configuration objects |
| Connection bootstrap | `_connection.py`, `_attach.py` | Creates the DuckDB connection, loads extensions, builds `ATTACH` SQL |
| Public modules | `modules/*.py` | Small API surface grouped by feature |
| Operations | `operations/*.py` | Implements module behaviors and maps query results to dataclasses |
| Data contracts | `schema.py` | Shared result types such as `ColumnDef`, `TableInfo`, and listings |
| SQL assets | `templates/*.sql` | Reusable SQL snippets used by operations |

## Why the modules are thin

The modules mostly forward to functions in `operations/`. That design keeps:

- the public API easy to scan
- SQL-heavy logic out of the top-level client
- result mapping reusable and testable

## Attach SQL generation

`_attach.py` builds the final `ATTACH` statement from three sources:

1. catalog-provided attach options
2. the storage `DATA_PATH`
3. user-provided `attach_options`

The result is structurally equivalent to:

```sql
ATTACH '<catalog-uri>' AS "lake" (...options...)
```

Identifiers and literals are quoted centrally to reduce SQL formatting mistakes.

## Connection initialization order

`ConnectionManager._connect()` follows a strict order:

1. open DuckDB
2. apply runtime `SET` statements
3. install/load required extensions
4. run storage setup statements
5. attach the DuckLake catalog

That order matters. For example, S3 storage setup may depend on the right extension already being loaded.

## Query helper design

Two styles exist side by side:

- direct DuckDB access via `lake.connection`
- wrapped operations that raise client-specific exceptions and return typed Python objects

Examples:

- `lake.table.list()` returns `list[TableListing]`
- `lake.table.info()` returns a `TableInfo` dataclass
- `lake.sql_dicts()` returns `list[dict[str, Any]]`

## Important behavior to know

### `table.info()` can be heavier than it looks

When enabled, `table.info()` also executes:

- `SUMMARIZE SELECT * FROM <table>` for per-column summary stats
- `SELECT count(*) FROM <table>` for row count

That is useful, but it may be expensive on large tables.

### Snapshot metadata is catalog-wide

The snapshot query used by `table.info(..., include_snapshots=True)` reads from `<alias>.snapshots()` and orders by `snapshot_id`. It does not filter snapshots by table name in the client layer.

## Extension model

Required extensions are collected from:

- the client baseline (`ducklake`, `parquet`)
- selected catalog backend
- selected storage backend
- `DuckDBConfig.extensions`

Duplicates are removed while preserving first-seen order.

## Error boundaries

| Error type | Where it comes from |
|-----------|----------------------|
| `DuckLakeConfigError` | Invalid constructor input, empty names, duplicate settings, invalid column definitions |
| `DuckLakeConnectionError` | Failures during connection bootstrapping or invalid runtime setting names |
| `DuckLakeQueryError` | Query failures routed through wrapper helpers or operations |

## Next step

Read [modules.md](./modules.md) for the public API surface a consumer actually uses.
