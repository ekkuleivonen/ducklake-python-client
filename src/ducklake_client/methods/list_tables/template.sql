SELECT table_catalog, table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_catalog = $catalog
  AND ($schema IS NULL OR table_schema = $schema)
  AND table_type = 'BASE TABLE'
ORDER BY table_schema, table_name
