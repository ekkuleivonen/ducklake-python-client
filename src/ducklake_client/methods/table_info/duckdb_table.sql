SELECT *
FROM duckdb_tables()
WHERE database_name = $catalog
  AND schema_name = $schema
  AND table_name = $table
