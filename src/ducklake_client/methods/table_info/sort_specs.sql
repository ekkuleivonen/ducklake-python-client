SELECT si.sort_id,
       se.sort_key_index,
       se.expression,
       se.dialect,
       se.sort_direction,
       se.null_order
FROM ducklake_sort_info AS si
JOIN ducklake_sort_expression AS se
  ON se.sort_id = si.sort_id AND se.table_id = si.table_id
JOIN ducklake_table AS t ON t.table_id = si.table_id
JOIN ducklake_schema AS s ON s.schema_id = t.schema_id
WHERE s.schema_name = $schema
  AND t.table_name = $table
  AND si.end_snapshot IS NULL
  AND t.end_snapshot IS NULL
  AND s.end_snapshot IS NULL
ORDER BY se.sort_key_index
