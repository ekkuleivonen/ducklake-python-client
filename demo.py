"""Examples for ducklake-client."""

import pprint
from ducklake_client import DiskStorage, DuckDBCatalog, DuckLake


def main() -> None:
    with DuckLake(
        catalog=DuckDBCatalog("demo.ducklake"),
        storage=DiskStorage("demo"),
    ) as lake:
        with lake.transaction():
            lake.schema.create("main")
            lake.table.create_from_csv(
                "nl_train_stations",
                "https://blobs.duckdb.org/nl_stations.csv",
            )
            lake.table.comment("nl_train_stations", "Dutch railway stations")
            lake.table.comment(
                "nl_train_stations",
                "Station ID",
                column_name="id",
            )

        # rows = lake.connection.sql("SELECT * FROM lake.main.nl_train_stations LIMIT 5").fetchall()
        info = lake.table.info("nl_train_stations")
        pprint.pprint(info.columns[0], indent=2)


if __name__ == "__main__":
    main()
