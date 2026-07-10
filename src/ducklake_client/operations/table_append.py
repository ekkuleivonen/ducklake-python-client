"""Append Python records, Arrow data, or DuckDB relations to a table."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from ducklake_client.config import quote_identifier
from ducklake_client.exceptions import DuckLakeConfigError, DuckLakeQueryError
from ducklake_client.operations.base import OperationContext
from ducklake_client.operations.table_names import qualified_table_name, split_table_name

if TYPE_CHECKING:
    import duckdb


class ArrowArray(Protocol):
    """An object implementing the Arrow C array interface."""

    def __arrow_c_array__(self, requested_schema: object | None = None) -> object: ...


class ArrowStream(Protocol):
    """An object implementing the Arrow C stream interface."""

    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object: ...


if TYPE_CHECKING:
    AppendSource: TypeAlias = (
        Iterable[Mapping[str, object]]
        | ArrowArray
        | ArrowStream
        | duckdb.DuckDBPyRelation
    )
else:
    AppendSource: TypeAlias = object


def table_append(
    context: OperationContext,
    table_name: str,
    source: AppendSource,
    *,
    schema_name: str = "main",
) -> None:
    """Append a microbatch to an existing table, matching columns by name."""

    schema, table = split_table_name(table_name, schema_name=schema_name)
    target = qualified_table_name(context.alias, schema, table)

    try:
        import duckdb

        if isinstance(source, duckdb.DuckDBPyRelation):
            _append_relation(source, target)
        elif _is_arrow(source):
            _append_relation(context.connection.from_arrow(source), target)
        else:
            _append_records(context, target, source)
    except DuckLakeConfigError:
        raise
    except DuckLakeQueryError:
        raise
    except Exception as exc:
        raise DuckLakeQueryError("DuckLake table.append failed") from exc


def _append_relation(relation: Any, target: str) -> None:
    relation.query(
        "ducklake_append_source",
        f"INSERT INTO {target} BY NAME SELECT * FROM ducklake_append_source",
    )


def _append_records(context: OperationContext, target: str, source: object) -> None:
    if isinstance(source, Mapping) or isinstance(source, str | bytes | bytearray):
        raise DuckLakeConfigError(
            "table.append records must be an iterable of mappings, not a single value"
        )

    try:
        records = list(source)  # type: ignore[arg-type]
    except TypeError as exc:
        raise DuckLakeConfigError(
            "table.append source must contain records or implement the Arrow interface"
        ) from exc

    if not records:
        return
    if not all(isinstance(record, Mapping) for record in records):
        raise DuckLakeConfigError("table.append records must all be mappings")

    columns = list(records[0])
    if not columns:
        raise DuckLakeConfigError("table.append records must contain at least one column")
    if not all(isinstance(column, str) and column for column in columns):
        raise DuckLakeConfigError("table.append record keys must be non-empty strings")

    expected = set(columns)
    for index, record in enumerate(records[1:], start=1):
        if set(record) != expected:
            raise DuckLakeConfigError(
                f"table.append record {index} has different columns from the first record"
            )

    rendered_columns = ", ".join(quote_identifier(column) for column in columns)
    row_placeholders = "(" + ", ".join("?" for _ in columns) + ")"
    placeholders = ", ".join(row_placeholders for _ in records)
    parameters = [record[column] for record in records for column in columns]
    context.connection.execute(
        f"INSERT INTO {target} ({rendered_columns}) VALUES {placeholders}",
        parameters,
    )


def _is_arrow(source: object) -> bool:
    return hasattr(source, "__arrow_c_array__") or hasattr(source, "__arrow_c_stream__")
