"""Collect DuckLake table metadata."""

from __future__ import annotations

from typing import Any

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError
from ducklake_client.operations.base import OperationContext, optional_rows, rows, template
from ducklake_client.schema import (
    DuckLakeTableMetadata,
    TableInfo,
    TableInfoColumn,
    TablePartitionSpec,
    TableSnapshotInfo,
    TableSortSpec,
)


def table_info(
    context: OperationContext,
    name: str,
    *,
    schema_name: str = "main",
    include_row_count: bool = True,
    include_snapshots: bool = True,
) -> TableInfo:
    schema, table = _split_table_name(name, schema_name=schema_name)
    parameters = {"catalog": context.alias, "schema": schema, "table": table}
    table_record = _require_table(context, parameters)
    duckdb_table_record = _duckdb_table_record(context, parameters)
    duckdb_column_comments = _duckdb_column_comments(context, parameters)
    summary_by_name = _summary_by_column(context, context.alias, schema, table)
    row_count = (
        _row_count(context, context.alias, schema, table) if include_row_count else None
    )

    columns = [
        _column_info(row, duckdb_column_comments.get(str(row["column_name"]), {}), summary_by_name)
        for row in _information_schema_columns(context, parameters)
    ]

    return TableInfo(
        catalog_name=str(context.alias),
        schema_name=schema,
        table_name=table,
        qualified_name=_qualified_table_name(context.alias, schema, table),
        table_type=str(table_record["table_type"]),
        columns=columns,
        row_count=row_count,
        estimated_size=_int_or_none(duckdb_table_record.get("estimated_size"))
        if duckdb_table_record
        else None,
        table_comment=_str_or_none(duckdb_table_record.get("comment"))
        if duckdb_table_record
        else None,
        partition_specs=_partition_specs(context, parameters),
        sort_specs=_sort_specs(context, parameters),
        ducklake_metadata=_ducklake_metadata(context, parameters),
        snapshots=_snapshots(context, context.alias) if include_snapshots else [],
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


def _require_table(
    context: OperationContext, parameters: dict[str, object]
) -> dict[str, Any]:
    result = rows(
        context,
        template("table_info_table.sql"),
        parameters,
        operation="table.info",
    )
    if not result:
        qualified = f"{parameters['schema']}.{parameters['table']}"
        raise DuckLakeConfigError(f"table not found: {qualified}")
    return result[0]


def _information_schema_columns(
    context: OperationContext, parameters: dict[str, object]
) -> list[dict[str, Any]]:
    return rows(
        context,
        template("table_info_columns.sql"),
        parameters,
        operation="table.info",
    )


def _duckdb_table_record(
    context: OperationContext, parameters: dict[str, object]
) -> dict[str, Any]:
    result = optional_rows(
        context,
        template("table_info_duckdb_table.sql"),
        parameters,
        operation="table.info",
    )
    return result[0] if result else {}


def _duckdb_column_comments(
    context: OperationContext, parameters: dict[str, object]
) -> dict[str, dict[str, Any]]:
    result = optional_rows(
        context,
        template("table_info_duckdb_columns.sql"),
        parameters,
        operation="table.info",
    )
    return {str(row["column_name"]): row for row in result if row.get("column_name") is not None}


def _summary_by_column(
    context: OperationContext, catalog: str, schema: str, table: str
) -> dict[str, dict[str, str | None]]:
    result = optional_rows(
        context,
        template("table_info_summary.sql").format(
            table_name=_qualified_table_name(catalog, schema, table)
        ),
        operation="table.info",
    )
    summary: dict[str, dict[str, str | None]] = {}
    for row in result:
        name = row.get("column_name")
        if name is not None:
            summary[str(name)] = {key: _str_or_none(value) for key, value in row.items()}
    return summary


def _row_count(
    context: OperationContext, catalog: str, schema: str, table: str
) -> int | None:
    result = optional_rows(
        context,
        template("table_info_row_count.sql").format(
            table_name=_qualified_table_name(catalog, schema, table)
        ),
        operation="table.info",
    )
    if not result:
        return None
    return _int_or_none(result[0].get("row_count"))


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


def _ducklake_metadata(
    context: OperationContext, parameters: dict[str, object]
) -> DuckLakeTableMetadata | None:
    result = optional_rows(
        context,
        template("table_info_ducklake_metadata.sql"),
        parameters,
        operation="table.info",
    )
    if not result:
        return None
    row = result[0]
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


def _partition_specs(
    context: OperationContext, parameters: dict[str, object]
) -> list[TablePartitionSpec]:
    return [
        TablePartitionSpec(
            partition_id=_int_or_none(row.get("partition_id")),
            partition_key_index=_int_or_none(row.get("partition_key_index")),
            column_id=_int_or_none(row.get("column_id")),
            column_name=_str_or_none(row.get("column_name")),
            transform=_str_or_none(row.get("transform")),
        )
        for row in optional_rows(
            context,
            template("table_info_partition_specs.sql"),
            parameters,
            operation="table.info",
        )
    ]


def _sort_specs(
    context: OperationContext, parameters: dict[str, object]
) -> list[TableSortSpec]:
    return [
        TableSortSpec(
            sort_id=_int_or_none(row.get("sort_id")),
            sort_key_index=_int_or_none(row.get("sort_key_index")),
            expression=_str_or_none(row.get("expression")),
            dialect=_str_or_none(row.get("dialect")),
            sort_direction=_str_or_none(row.get("sort_direction")),
            null_order=_str_or_none(row.get("null_order")),
        )
        for row in optional_rows(
            context,
            template("table_info_sort_specs.sql"),
            parameters,
            operation="table.info",
        )
    ]


def _snapshots(context: OperationContext, catalog: str) -> list[TableSnapshotInfo]:
    result = optional_rows(
        context,
        template("table_info_snapshots.sql").format(
            snapshots_function=f"{quote_identifier(catalog)}.snapshots()"
        ),
        operation="table.info",
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
        for row in result
        if row.get("snapshot_id") is not None
    ]


def _qualified_table_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(quote_identifier(part) for part in (catalog, schema, table))


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
