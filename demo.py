"""Examples for ducklake-client."""

from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake


def main() -> None:
    with DuckLake(
        catalog=DuckDBCatalog("demo.ducklake"),
        storage=DiskStorage("demo_data"),
    ) as lake:
        lake.connection.begin()
        try:
            lake.schema.create("main")
            lake.table.create(
                "items",
                id=ColumnDef("INTEGER", nullable=False),
                name=ColumnDef("VARCHAR"),
            )
            lake.connection.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])
            lake.connection.commit()
        except Exception:
            lake.connection.rollback()
            raise

        rows = lake.connection.sql("SELECT * FROM lake.main.items ORDER BY id").fetchall()
        print(rows)


if __name__ == "__main__":
    main()
