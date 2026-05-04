"""Examples for ducklake-client."""

from ducklake_client import ColumnDef, DiskStorage, DuckDBCatalog, DuckLake


def main() -> None:
    with DuckLake(
        catalog=DuckDBCatalog("demo.ducklake"),
        storage=DiskStorage("demo_data"),
    ) as lake:
        with lake.transaction() as tx:
            tx.create_schema("main")
            tx.create_table(
                "items",
                id=ColumnDef("INTEGER", nullable=False),
                name=ColumnDef("VARCHAR"),
            )
            tx.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])

        rows = lake.sql("SELECT * FROM lake.main.items ORDER BY id").fetchall()
        print(rows)


if __name__ == "__main__":
    main()
