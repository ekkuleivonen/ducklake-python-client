import unittest

from ducklake_client import (
    ColumnDef,
    DecimalType,
    DuckLakeConfigError,
    ListType,
    MapType,
    StructType,
)


class ColumnDefTests(unittest.TestCase):
    def test_map_type(self) -> None:
        column = ColumnDef(MapType("VARCHAR", "VARCHAR"), nullable=False)
        self.assertEqual(
            column.sql("attributes"),
            '"attributes" MAP(VARCHAR, VARCHAR) NOT NULL',
        )

    def test_nested_types(self) -> None:
        column = ColumnDef(
            ListType(StructType({"amount": DecimalType(12, 2), "currency": "VARCHAR"}))
        )
        self.assertEqual(
            column.sql("prices"),
            '"prices" STRUCT("amount" DECIMAL(12, 2), "currency" VARCHAR)[]',
        )

    def test_invalid_nested_primitive_is_rejected(self) -> None:
        with self.assertRaises(DuckLakeConfigError):
            MapType("TEXT", "VARCHAR")  # type: ignore[arg-type]

    def test_invalid_decimal_is_rejected(self) -> None:
        with self.assertRaises(DuckLakeConfigError):
            DecimalType(4, 5)


if __name__ == "__main__":
    unittest.main()
