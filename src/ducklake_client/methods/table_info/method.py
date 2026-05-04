"""Implementation for collecting DuckLake table metadata."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.schema import (
    DuckLakeTableMetadata,
    TableInfo,
    TableInfoColumn,
    TablePartitionSpec,
    TableSnapshotInfo,
    TableSortSpec,
)


def table_info(
    client: Any,
    table_name: str,
    *,
    schema_name: str = "main",
    include_row_count: bool = True,
    include_snapshots: bool = True,
) -> TableInfo:
    """Return consolidated metadata and summary statistics for a DuckLake table."""

    schema, table = _split_table_name(table_name, schema_name=schema_name)
    params = {"catalog": client.alias, "schema": schema, "table": table}
    table_record = _require_table(client, params)
    duckdb_table_record = _duckdb_table_record(client, params)
    duckdb_column_comments = _duckdb_column_comments(client, params)
    summary_by_name = _summary_by_column(client, client.alias, schema, table)
    row_count = _row_count(client, client.alias, schema, table) if include_row_count else None

    columns = [
        _column_info(row, duckdb_column_comments.get(str(row["column_name"]), {}), summary_by_name)
        for row in _information_schema_columns(client, params)
    ]

    ducklake_metadata = _ducklake_metadata(client, params)
    return TableInfo(
        catalog_name=str(client.alias),
        schema_name=schema,
        table_name=table,
        qualified_name=_qualified_table_name(client.alias, schema, table),
        table_type=str(table_record["table_type"]),
        columns=columns,
        row_count=row_count,
        estimated_size=_int_or_none(duckdb_table_record.get("estimated_size"))
        if duckdb_table_record
        else None,
        table_comment=_str_or_none(duckdb_table_record.get("comment")) if duckdb_table_record else None,
        partition_specs=_partition_specs(client, params),
        sort_specs=_sort_specs(client, params),
        ducklake_metadata=ducklake_metadata,
        snapshots=_snapshots(client, client.alias) if include_snapshots else [],
    )


def _split_table_name(name: str, *, schema_name: str) -> tuple[str, str]:
    if not name:
        raise DuckLakeConfigError("table name must not be empty")
    if not schema_name:
        raise DuckLakeConfigError("schema name must not be empty")

    parts = name.split(".")
    if len(parts) == 1:
        return schema_name, parts[0]
    if len(parts) == 2:
        if schema_name != "main":
            raise DuckLakeConfigError("pass either 'schema.table' or schema_name=, not both")
        schema, table = parts
        if schema and table:
            return schema, table
    raise DuckLakeConfigError(f"invalid table name: {name!r}")


def _require_table(client: Any, params: dict[str, object]) -> dict[str, Any]:
    rows = _rows(client, _template("table.sql"), params)
    if not rows:
        qualified = f"{params['schema']}.{params['table']}"
        raise DuckLakeConfigError(f"table not found: {qualified}")
    return rows[0]


def _information_schema_columns(client: Any, params: dict[str, object]) -> list[dict[str, Any]]:
    return _rows(client, _template("columns.sql"), params)


def _duckdb_table_record(client: Any, params: dict[str, object]) -> dict[str, Any]:
    rows = _optional_rows(client, _template("duckdb_table.sql"), params)
    return rows[0] if rows else {}


def _duckdb_column_comments(
    client: Any, params: dict[str, object]
) -> dict[str, dict[str, Any]]:
    rows = _optional_rows(client, _template("duckdb_columns.sql"), params)
    return {str(row["column_name"]): row for row in rows if row.get("column_name") is not None}


def _summary_by_column(
    client: Any, catalog: str, schema: str, table: str
) -> dict[str, dict[str, str | None]]:
    rows = _optional_rows(
        client,
        _template("summary.sql").format(table_name=_qualified_table_name(catalog, schema, table)),
        None,
    )
    result: dict[str, dict[str, str | None]] = {}
    for row in rows:
        name = row.get("column_name")
        if name is None:
            continue
        result[str(name)] = {key: _str_or_none(value) for key, value in row.items()}
    return result


def _row_count(client: Any, catalog: str, schema: str, table: str) -> int | None:
    rows = _optional_rows(
        client,
        _template("row_count.sql").format(
            table_name=_qualified_table_name(catalog, schema, table)
        ),
        None,
    )
    if not rows:
        return None
    return _int_or_none(rows[0].get("row_count"))


def _column_info(
    row: dict[str, Any],
    duckdb_column: dict[str, Any],
    summary_by_name: dict[str, dict[str, str | None]],
) -> TableInfoColumn:
    name = str(row["column_name"])
    summary = summary_by_name.get(name, {})
    return TableInfoColumn(
        name=name,
        data_type=str(row["data_type"]),
        nullable=str(row["is_nullable"]).upper() == "YES",
        ordinal_position=int(row["ordinal_position"]),
        default=_str_or_none(row.get("column_default")),
        comment=_str_or_none(duckdb_column.get("comment")),
        min=summary.get("min"),
        max=summary.get("max"),
        null_percentage=summary.get("null_percentage"),
        approx_unique=summary.get("approx_unique"),
        count=summary.get("count"),
        summary=dict(summary),
    )


def _ducklake_metadata(client: Any, params: dict[str, object]) -> DuckLakeTableMetadata | None:
    rows = _optional_rows(client, _template("ducklake_metadata.sql"), params)
    if not rows:
        return None
    row = rows[0]
    return DuckLakeTableMetadata(
        table_id=_int_or_none(row.get("table_id")),
        table_uuid=_str_or_none(row.get("table_uuid")),
        schema_id=_int_or_none(row.get("schema_id")),
        begin_snapshot=_int_or_none(row.get("begin_snapshot")),
        end_snapshot=_int_or_none(row.get("end_snapshot")),
        path=_str_or_none(row.get("path")),
        path_is_relative=_bool_or_none(row.get("path_is_relative")),
        record_count=_int_or_none(row.get("record_count")),
        next_row_id=_int_or_none(row.get("next_row_id")),
        file_size_bytes=_int_or_none(row.get("file_size_bytes")),
    )


def _partition_specs(client: Any, params: dict[str, object]) -> list[TablePartitionSpec]:
    rows = _optional_rows(client, _template("partition_specs.sql"), params)
    return [
        TablePartitionSpec(
            partition_id=_int_or_none(row.get("partition_id")),
            partition_key_index=_int_or_none(row.get("partition_key_index")),
            column_id=_int_or_none(row.get("column_id")),
            column_name=_str_or_none(row.get("column_name")),
            transform=_str_or_none(row.get("transform")),
        )
        for row in rows
    ]


def _sort_specs(client: Any, params: dict[str, object]) -> list[TableSortSpec]:
    rows = _optional_rows(client, _template("sort_specs.sql"), params)
    return [
        TableSortSpec(
            sort_id=_int_or_none(row.get("sort_id")),
            sort_key_index=_int_or_none(row.get("sort_key_index")),
            expression=_str_or_none(row.get("expression")),
            dialect=_str_or_none(row.get("dialect")),
            sort_direction=_str_or_none(row.get("sort_direction")),
            null_order=_str_or_none(row.get("null_order")),
        )
        for row in rows
    ]


def _snapshots(client: Any, catalog: str) -> list[TableSnapshotInfo]:
    rows = _optional_rows(
        client,
        _template("snapshots.sql").format(
            snapshots_function=f"{quote_identifier(catalog)}.snapshots()"
        ),
        None,
    )
    return [
        TableSnapshotInfo(
            snapshot_id=int(row["snapshot_id"]),
            snapshot_time=row.get("snapshot_time"),
            schema_version=_int_or_none(row.get("schema_version")),
            next_catalog_id=_int_or_none(row.get("next_catalog_id")),
            next_file_id=_int_or_none(row.get("next_file_id")),
            changes_made=_str_or_none(row.get("changes_made")),
            author=_str_or_none(row.get("author")),
            commit_message=_str_or_none(row.get("commit_message")),
            commit_extra_info=_str_or_none(row.get("commit_extra_info")),
        )
        for row in rows
        if row.get("snapshot_id") is not None
    ]


def _rows(client: Any, query: str, parameters: dict[str, object] | None) -> list[dict[str, Any]]:
    try:
        cursor = client.execute(query, parameters) if parameters is not None else client.execute(query)
        names = [str(column[0]) for column in cursor.description or []]
        return [dict(zip(names, row, strict=False)) for row in cursor.fetchall()]
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake table_info query failed") from exc


def _optional_rows(
    client: Any, query: str, parameters: dict[str, object] | None
) -> list[dict[str, Any]]:
    try:
        return _rows(client, query, parameters)
    except DuckLakeQueryError:
        return []


def _qualified_table_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(quote_identifier(part) for part in (catalog, schema, table))


def _template(name: str) -> str:
    return (
        files("ducklake_client.methods.table_info")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "t", "yes", "y"}
