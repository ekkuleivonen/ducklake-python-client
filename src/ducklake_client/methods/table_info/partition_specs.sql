SELECT pi.partition_id,
       pc.partition_key_index,
       pc.column_id,
       c.column_name,
       pc.transform
FROM ducklake_partition_info AS pi
JOIN ducklake_partition_column AS pc
  ON pc.partition_id = pi.partition_id AND pc.table_id = pi.table_id
JOIN ducklake_table AS t ON t.table_id = pi.table_id
JOIN ducklake_schema AS s ON s.schema_id = t.schema_id
LEFT JOIN ducklake_column AS c
  ON c.table_id = t.table_id
 AND c.column_id = pc.column_id
 AND c.end_snapshot IS NULL
WHERE s.schema_name = $schema
  AND t.table_name = $table
  AND pi.end_snapshot IS NULL
  AND t.end_snapshot IS NULL
  AND s.end_snapshot IS NULL
ORDER BY pc.partition_key_index
