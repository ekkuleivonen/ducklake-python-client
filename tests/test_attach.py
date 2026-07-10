import unittest

from ducklake_client import (
    DiskStorage,
    DuckDBCatalog,
    DuckLakeAttachConfig,
    DuckLakeConfigError,
)
from ducklake_client._attach import build_attach_sql


class AttachConfigTests(unittest.TestCase):
    def test_renders_typed_attach_options(self) -> None:
        sql = build_attach_sql(
            catalog=DuckDBCatalog("metadata.ducklake"),
            storage=DiskStorage("data"),
            alias="lake",
            attach=DuckLakeAttachConfig(
                data_inlining_row_limit=50,
                automatic_migration=False,
                encrypted=True,
            ),
        )

        self.assertIn("DATA_INLINING_ROW_LIMIT 50", sql)
        self.assertIn("AUTOMATIC_MIGRATION false", sql)
        self.assertIn("ENCRYPTED true", sql)

    def test_raw_options_can_override_typed_options(self) -> None:
        sql = build_attach_sql(
            catalog=DuckDBCatalog("metadata.ducklake"),
            storage=DiskStorage("data"),
            alias="lake",
            attach=DuckLakeAttachConfig(data_inlining_row_limit=50),
            attach_options={"data_inlining_row_limit": 100},
        )

        self.assertIn("DATA_INLINING_ROW_LIMIT 100", sql)
        self.assertNotIn("DATA_INLINING_ROW_LIMIT 50", sql)

    def test_rejects_negative_inlining_limit(self) -> None:
        with self.assertRaises(DuckLakeConfigError):
            DuckLakeAttachConfig(data_inlining_row_limit=-1)

    def test_rejects_boolean_inlining_limit(self) -> None:
        with self.assertRaises(DuckLakeConfigError):
            DuckLakeAttachConfig(data_inlining_row_limit=True)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
