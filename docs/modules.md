# Public modules and common APIs

The public API is intentionally split into a few feature modules. Use these when you want typed helpers; drop down to `lake.connection` when you need raw DuckDB power.

## Quick path

1. Use `lake.schema` for schema creation.
2. Use `lake.table` for create/list/info/comment/alter flows.
3. Use `lake.view` for view discovery.
4. Use `lake.snapshots` for simple snapshot access.

## Module map

| API | What it does | Returns |
|-----|---------------|---------|
| `lake.schema.create(name, if_not_exists=True)` | Creates a schema under the attached alias | DuckDB connection/cursor result |
| `lake.table.create(...)` | Creates a table from `ColumnDef` values | DuckDB connection/cursor result |
| `lake.table.create_from_csv(...)` | Creates a table from a CSV source | DuckDB connection/cursor result |
| `lake.table.add_column(...)` | Adds a column with optional raw `DEFAULT` SQL | DuckDB connection/cursor result |
| `lake.table.drop_column(...)` | Drops a column | DuckDB connection/cursor result |
| `lake.table.comment(...)` | Sets table or column comments | DuckDB connection/cursor result |
| `lake.table.list(schema_name=None)` | Lists base tables in the attached catalog | `list[TableListing]` |
| `lake.table.info(...)` | Returns merged schema, summary, and metadata | `TableInfo` |
| `lake.view.list(schema_name=None)` | Lists views in the attached catalog | `list[ViewListing]` |
| `lake.snapshots.latest()` | Returns the latest snapshot id or `None` | `int | None` |

## Ad hoc query helpers on `DuckLake`

These live on the top-level client instead of a module.

| API | Purpose |
|-----|---------|
| `lake.connection` | Native DuckDB connection |
| `lake.sql_dicts(sql, **params)` | Query and return rows as dictionaries |
| `lake.sql_one(sql, **params)` | Return exactly one row as a dictionary |
| `lake.sql_scalar(sql, **params)` | Return exactly one scalar value |
| `lake.transaction()` | Context manager for begin/commit/rollback |
| `lake.close()` | Close the underlying connection |

## Naming rules and defaults

### Table names

Most table helpers accept either:

- `"table_name"` with `schema_name="main"` or another schema argument
- `"schema.table"` when you want to inline the schema name

Do **not** pass both `"schema.table"` and a non-default `schema_name`; the client treats that as invalid input.

### Column definitions

`lake.table.create(...)` and `lake.table.add_column(...)` expect `ColumnDef` objects.

```python
from ducklake_client import ColumnDef

ColumnDef("INTEGER", nullable=False)
ColumnDef("VARCHAR")
```

The accepted `data_type` values are a fixed literal set defined in `schema.py`.

## Result types you will see often

| Type | Meaning |
|------|---------|
| `ColumnDef` | Input contract for table columns |
| `TableListing` | One listed base table |
| `ViewListing` | One listed view |
| `TableInfo` | Consolidated table metadata |
| `TableInfoColumn` | One column inside `TableInfo.columns` |
| `TableSnapshotInfo` | One snapshot row |

## Choosing helpers vs native SQL

Use module helpers when you want:

- input validation
- typed return values
- stable high-level actions such as create/list/info/comment

Use `lake.connection` when you want:

- custom DDL or DML
- bulk inserts
- SQL features the wrapper does not expose
- direct control over DuckDB cursors and result handling

## Checklist

- [ ] I know which APIs return typed Python dataclasses.
- [ ] I know that some helper methods return the DuckDB execution result directly.
- [ ] I know when direct `lake.connection` access is the simpler choice.

## Next step

Go back to [README.md](./README.md) to choose the next doc based on your task.
