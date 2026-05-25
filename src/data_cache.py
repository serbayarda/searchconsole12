"""In-memory cache of GSC query results as pandas DataFrames."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

_CACHE: dict[str, pd.DataFrame] = {}
_META: dict[str, dict[str, Any]] = {}


def make_key(prefix: str, params: dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, default=str).encode()
    return f"{prefix}_{hashlib.sha1(blob).hexdigest()[:10]}"


def put(key: str, df: pd.DataFrame, meta: dict[str, Any] | None = None) -> None:
    _CACHE[key] = df
    _META[key] = meta or {}


def get(key: str) -> pd.DataFrame:
    if key not in _CACHE:
        raise KeyError(f"No cached DataFrame for key={key!r}. Available: {list(_CACHE)}")
    return _CACHE[key]


def keys() -> list[str]:
    return list(_CACHE.keys())


def meta(key: str) -> dict[str, Any]:
    return _META.get(key, {})


def last_key() -> str | None:
    return next(reversed(_CACHE), None) if _CACHE else None
