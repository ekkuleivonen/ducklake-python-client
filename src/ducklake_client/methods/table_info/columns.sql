SELECT column_name, data_type, is_nullable, ordinal_position, column_default
FROM information_schema.columns
WHERE table_catalog = $catalog
  AND table_schema = $schema
  AND table_name = $table
ORDER BY ordinal_position
