"""Examples for ducklake-client."""

from ducklake_client import DuckLake


def main() -> None:
    with DuckLake(catalog="demo.ducklake", storage="demo_data") as lake:
        lake.execute("CREATE SCHEMA IF NOT EXISTS lake.main")
        lake.execute(
            "CREATE TABLE IF NOT EXISTS lake.main.items (id INTEGER, name VARCHAR)"
        )
        lake.execute("INSERT INTO lake.main.items VALUES (?, ?)", [1, "example"])

        rows = lake.sql("SELECT * FROM lake.main.items ORDER BY id").fetchall()
        print(rows)


if __name__ == "__main__":
    main()
