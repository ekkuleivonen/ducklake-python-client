SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_catalog = $catalog
  AND table_schema = $schema
  AND table_name = $table
