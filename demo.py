"""Examples for ducklake-client."""

from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake


def main() -> None:
    with DuckLake(
        catalog=DuckDBCatalog("demo.ducklake"),
        storage=DiskStorage("demo_data"),
    ) as lake:
        with lake.transaction() as tx:
            tx.execute("CREATE SCHEMA IF NOT EXISTS lake.main")
            tx.execute("CREATE TABLE IF NOT EXISTS lake.main.items (id INTEGER, name VARCHAR)")
            tx.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])

        rows = lake.sql("SELECT * FROM lake.main.items ORDER BY id").fetchall()
        print(rows)


if __name__ == "__main__":
    main()
