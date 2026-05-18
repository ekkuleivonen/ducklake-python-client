# ducklake-client docs

This folder explains how `ducklake-client` is structured and how to use it without reading the whole source tree.

## Quick path

1. Start with [Getting started](./getting-started.md).
2. Read [Configuration](./configuration.md) to choose catalog, storage, and DuckDB settings.
3. Use [Architecture](./architecture.md) and [Modules](./modules.md) when you need to understand internals or extend the client.

## What is in this docs set?

| File | Purpose |
|------|---------|
| [getting-started.md](./getting-started.md) | Happy-path usage, lifecycle, and common flows |
| [configuration.md](./configuration.md) | Catalog, storage, alias, attach options, and DuckDB runtime settings |
| [architecture.md](./architecture.md) | How connection setup, attach SQL, modules, and operations fit together |
| [modules.md](./modules.md) | Public API surface and what each module is responsible for |

## Reader checklist

- [ ] I know that `DuckLake` opens the DuckDB connection lazily.
- [ ] I know which config object chooses the catalog and which chooses the data storage.
- [ ] I know when to use `lake.connection` directly versus the helper modules.

## Next step

Open [getting-started.md](./getting-started.md).
