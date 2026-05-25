"""Anthropic tool schemas + dispatcher for the GSC agent."""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from . import data_cache, gsc_client

# ---------- Tool schemas exposed to the model ----------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_properties",
        "description": (
            "List the Google Search Console properties (sites) the authenticated "
            "user has access to. Always call this first if the user hasn't "
            "specified a property."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "query_search_analytics",
        "description": (
            "Query GSC Search Analytics. Returns aggregated metrics (clicks, "
            "impressions, ctr, position) sliced by the chosen dimensions. The "
            "full DataFrame is cached server-side; the tool returns a cache_key, "
            "row totals, and a preview of the top rows. Use run_pandas with the "
            "cache_key to do deeper analysis on the full dataset.\n\n"
            "Tips: default to 28-day windows ending 3 days ago (GSC has ~2-3 day "
            "lag for 'final' data). Use data_state='all' to include fresh data. "
            "Use filters to narrow by query/page/country/device."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site_url": {
                    "type": "string",
                    "description": "GSC property URL, e.g. 'https://example.com/' or 'sc-domain:example.com'.",
                },
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD."},
                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["query", "page", "country", "device", "date", "searchAppearance"],
                    },
                    "description": "Dimensions to group by. Empty array = totals only.",
                },
                "filters": {
                    "type": "array",
                    "description": "List of dimensionFilter dicts, e.g. [{'dimension':'country','operator':'equals','expression':'usa'}]. Combined with AND.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {
                                "type": "string",
                                "enum": ["query", "page", "country", "device", "searchAppearance"],
                            },
                            "operator": {
                                "type": "string",
                                "enum": [
                                    "equals", "notEquals", "contains", "notContains",
                                    "includingRegex", "excludingRegex",
                                ],
                            },
                            "expression": {"type": "string"},
                        },
                        "required": ["dimension", "operator", "expression"],
                    },
                },
                "row_limit": {
                    "type": "integer",
                    "description": "Max rows to return (up to 25000). Default 1000.",
                },
                "start_row": {"type": "integer", "description": "Offset for paging. Default 0."},
                "search_type": {
                    "type": "string",
                    "enum": ["web", "image", "video", "news", "discover", "googleNews"],
                    "description": "Search surface. Default 'web'.",
                },
                "data_state": {
                    "type": "string",
                    "enum": ["final", "all"],
                    "description": "'final' = finalized data only (default). 'all' = includes fresh/partial last few days.",
                },
            },
            "required": ["site_url", "start_date", "end_date"],
        },
    },
    {
        "name": "list_sitemaps",
        "description": "List sitemaps submitted for a GSC property.",
        "input_schema": {
            "type": "object",
            "properties": {"site_url": {"type": "string"}},
            "required": ["site_url"],
        },
    },
    {
        "name": "inspect_url",
        "description": "Run a URL Inspection (indexing status, last crawl, AMP, etc.) for a single URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_url": {"type": "string"},
                "url": {"type": "string", "description": "Full URL to inspect; must be under the site_url property."},
            },
            "required": ["site_url", "url"],
        },
    },
    {
        "name": "run_pandas",
        "description": (
            "Run a pandas expression against one or more cached DataFrames from "
            "prior query_search_analytics calls. Use this for sorting, top-N, "
            "joins, deltas, CTR/position math, anomaly checks, etc.\n\n"
            "Namespace contains: `pd` (pandas), `df` (the DataFrame for the "
            "single cache_key passed), or `dfs` (dict of key -> DataFrame when "
            "multiple keys passed). Provide ONE expression or a short multi-line "
            "script ending in an expression. The repr of the final value is "
            "returned (truncated to ~6000 chars). Examples:\n"
            "  df.nlargest(20, 'clicks')[['query','clicks','impressions','ctr','position']]\n"
            "  dfs['k1'].merge(dfs['k2'], on='query', suffixes=('_now','_prev')).assign(delta=lambda x: x.clicks_now - x.clicks_prev).nsmallest(20, 'delta')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cache_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One or more cache_keys returned by query_search_analytics.",
                },
                "code": {
                    "type": "string",
                    "description": "Python/pandas expression or script ending in an expression.",
                },
            },
            "required": ["cache_keys", "code"],
        },
    },
    {
        "name": "compare_periods",
        "description": (
            "Convenience: pull two date ranges with identical dimensions+filters "
            "and join them on the dimension keys to compute deltas. Returns a "
            "cache_key for the joined DataFrame plus a preview of the largest "
            "absolute changes in clicks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site_url": {"type": "string"},
                "current_start": {"type": "string"},
                "current_end": {"type": "string"},
                "previous_start": {"type": "string"},
                "previous_end": {"type": "string"},
                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["query", "page", "country", "device", "searchAppearance"],
                    },
                    "description": "Non-empty list (date dimension not allowed here).",
                },
                "filters": {"type": "array", "items": {"type": "object"}},
                "row_limit": {"type": "integer"},
                "search_type": {"type": "string"},
            },
            "required": [
                "site_url", "current_start", "current_end",
                "previous_start", "previous_end", "dimensions",
            ],
        },
    },
]


# ---------- Dispatcher ----------

def _rows_to_df(rows: list[dict[str, Any]], dimensions: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=(dimensions or []) + ["clicks", "impressions", "ctr", "position"])
    records = []
    for r in rows:
        rec: dict[str, Any] = {}
        keys = r.get("keys", [])
        for i, dim in enumerate(dimensions or []):
            rec[dim] = keys[i] if i < len(keys) else None
        rec["clicks"] = r.get("clicks", 0)
        rec["impressions"] = r.get("impressions", 0)
        rec["ctr"] = r.get("ctr", 0.0)
        rec["position"] = r.get("position", 0.0)
        records.append(rec)
    return pd.DataFrame.from_records(records)


def _truncate(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text)-limit} more chars]"


def _df_preview(df: pd.DataFrame, n: int = 50) -> str:
    with pd.option_context("display.max_rows", n, "display.max_columns", None,
                           "display.width", 200, "display.max_colwidth", 80):
        return df.head(n).to_string(index=False)


def _totals(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": None, "rows": 0}
    return {
        "clicks": int(df["clicks"].sum()),
        "impressions": int(df["impressions"].sum()),
        "ctr": float(df["clicks"].sum() / df["impressions"].sum()) if df["impressions"].sum() else 0.0,
        "avg_position": float(df["position"].mean()),
        "rows": int(len(df)),
    }


def _do_query_search_analytics(args: dict[str, Any]) -> dict[str, Any]:
    dimensions = args.get("dimensions") or []
    resp = gsc_client.query_search_analytics(
        site_url=args["site_url"],
        start_date=args["start_date"],
        end_date=args["end_date"],
        dimensions=dimensions,
        filters=args.get("filters"),
        row_limit=args.get("row_limit", 1000),
        start_row=args.get("start_row", 0),
        search_type=args.get("search_type", "web"),
        data_state=args.get("data_state", "final"),
    )
    df = _rows_to_df(resp.get("rows", []), dimensions)
    key = data_cache.make_key("sa", args)
    data_cache.put(key, df, {"args": args})
    return {
        "cache_key": key,
        "totals": _totals(df),
        "preview_rows": min(50, len(df)),
        "preview": _df_preview(df, 50),
        "note": "Use run_pandas with this cache_key for deeper analysis on the full dataset.",
    }


def _do_compare_periods(args: dict[str, Any]) -> dict[str, Any]:
    dims = args["dimensions"]
    common = {
        "site_url": args["site_url"],
        "dimensions": dims,
        "filters": args.get("filters"),
        "row_limit": args.get("row_limit", 5000),
        "search_type": args.get("search_type", "web"),
    }
    cur = gsc_client.query_search_analytics(
        start_date=args["current_start"], end_date=args["current_end"], **common
    )
    prev = gsc_client.query_search_analytics(
        start_date=args["previous_start"], end_date=args["previous_end"], **common
    )
    df_cur = _rows_to_df(cur.get("rows", []), dims)
    df_prev = _rows_to_df(prev.get("rows", []), dims)

    join = df_cur.merge(df_prev, on=dims, how="outer", suffixes=("_now", "_prev")).fillna(0)
    join["clicks_delta"] = join["clicks_now"] - join["clicks_prev"]
    join["impressions_delta"] = join["impressions_now"] - join["impressions_prev"]
    join["position_delta"] = join["position_now"] - join["position_prev"]

    key = data_cache.make_key("cmp", args)
    data_cache.put(key, join, {"args": args})

    top_drops = join.nsmallest(15, "clicks_delta")[dims + ["clicks_now", "clicks_prev", "clicks_delta", "position_now", "position_prev"]]
    top_gains = join.nlargest(15, "clicks_delta")[dims + ["clicks_now", "clicks_prev", "clicks_delta", "position_now", "position_prev"]]
    return {
        "cache_key": key,
        "totals": {
            "current": _totals(df_cur),
            "previous": _totals(df_prev),
        },
        "biggest_drops": _df_preview(top_drops, 15),
        "biggest_gains": _df_preview(top_gains, 15),
        "note": "Full joined DataFrame cached under cache_key; use run_pandas for more.",
    }


def _do_run_pandas(args: dict[str, Any]) -> dict[str, Any]:
    keys = args["cache_keys"]
    code = args["code"]
    dfs = {k: data_cache.get(k) for k in keys}
    namespace: dict[str, Any] = {"pd": pd, "dfs": dfs}
    if len(keys) == 1:
        namespace["df"] = dfs[keys[0]]

    code = code.strip()
    try:
        # Try eval (single expression) first
        try:
            result = eval(code, namespace)  # noqa: S307
        except SyntaxError:
            # Multi-line: exec all but last line, eval last line
            lines = code.splitlines()
            body, last = "\n".join(lines[:-1]), lines[-1]
            exec(body, namespace)  # noqa: S102
            result = eval(last, namespace)  # noqa: S307
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}

    if isinstance(result, pd.DataFrame):
        text = _df_preview(result, 100) + f"\n\n[{len(result)} rows x {len(result.columns)} cols]"
    elif isinstance(result, pd.Series):
        text = result.to_string() + f"\n\n[Series len={len(result)}]"
    else:
        text = repr(result)
    return {"result": _truncate(text)}


def dispatch(name: str, args: dict[str, Any]) -> str:
    """Run a tool call and return a JSON string suitable for a tool_result block."""
    try:
        if name == "list_properties":
            sites = gsc_client.list_sites()
            payload: Any = [
                {"site_url": s.get("siteUrl"), "permission_level": s.get("permissionLevel")}
                for s in sites
            ]
        elif name == "query_search_analytics":
            payload = _do_query_search_analytics(args)
        elif name == "list_sitemaps":
            payload = gsc_client.list_sitemaps(args["site_url"])
        elif name == "inspect_url":
            payload = gsc_client.inspect_url(args["site_url"], args["url"])
        elif name == "run_pandas":
            payload = _do_run_pandas(args)
        elif name == "compare_periods":
            payload = _do_compare_periods(args)
        else:
            payload = {"error": f"Unknown tool: {name}"}
    except Exception as e:  # noqa: BLE001
        payload = {"error": gsc_client.friendly_error(e)}

    return json.dumps(payload, default=str)
