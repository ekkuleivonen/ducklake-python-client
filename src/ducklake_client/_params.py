"""Query parameter normalization shared by connection helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

QueryParameters: TypeAlias = Mapping[str, object] | Sequence[object] | None


def normalize_parameters(
    positional: tuple[object, ...],
    named: Mapping[str, object],
) -> QueryParameters:
    if positional and named:
        raise TypeError("pass either positional parameters or named parameters, not both")
    if named:
        return dict(named)
    if not positional:
        return None
    if len(positional) == 1 and isinstance(positional[0], Mapping):
        return dict(positional[0])
    return list(positional)
