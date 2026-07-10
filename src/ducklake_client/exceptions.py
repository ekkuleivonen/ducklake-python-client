"""Exception hierarchy for the DuckLake client."""


class DuckLakeError(Exception):
    """Base class for all client-level errors."""


class DuckLakeConfigError(DuckLakeError, ValueError):
    """Raised when DuckLake connection configuration is invalid."""


class DuckLakeConnectionError(DuckLakeError):
    """Raised when the client cannot create or initialize a DuckDB connection."""


class DuckLakeQueryError(DuckLakeError):
    """Raised when a query fails through the client wrapper."""


class DuckLakeFenceError(DuckLakeError):
    """Raised when a cooperative catalog fence cannot be operated."""


class DuckLakeFenceTimeout(DuckLakeFenceError, TimeoutError):
    """Raised when a cooperative catalog fence cannot be acquired in time."""
