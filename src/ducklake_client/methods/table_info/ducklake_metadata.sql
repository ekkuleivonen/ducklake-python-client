SELECT t.table_id,
       t.table_uuid,
       t.schema_id,
       t.begin_snapshot,
       t.end_snapshot,
       t.path,
       t.path_is_relative,
       ts.record_count,
       ts.next_row_id,
       ts.file_size_bytes
FROM ducklake_table AS t
JOIN ducklake_schema AS s ON s.schema_id = t.schema_id
LEFT JOIN ducklake_table_stats AS ts ON ts.table_id = t.table_id
WHERE s.schema_name = $schema
  AND t.table_name = $table
  AND t.end_snapshot IS NULL
  AND s.end_snapshot IS NULL
ORDER BY t.begin_snapshot DESC
LIMIT 1
