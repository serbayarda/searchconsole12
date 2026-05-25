"""Thin wrapper around the Google Search Console (webmasters v3) API."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_credentials


@lru_cache(maxsize=1)
def _service():
    return build("searchconsole", "v1", credentials=get_credentials(), cache_discovery=False)


def list_sites() -> list[dict[str, Any]]:
    resp = _service().sites().list().execute()
    return resp.get("siteEntry", [])


def list_sitemaps(site_url: str) -> list[dict[str, Any]]:
    resp = _service().sitemaps().list(siteUrl=site_url).execute()
    return resp.get("sitemap", [])


def query_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    row_limit: int = 1000,
    start_row: int = 0,
    search_type: str = "web",
    data_state: str = "final",
    aggregation_type: str = "auto",
) -> dict[str, Any]:
    """Call searchanalytics.query. Returns the raw API response dict.

    dimensions: any subset of ["query","page","country","device","date","searchAppearance"]
    filters: list of dimensionFilterGroup -> we wrap into one group with AND.
    search_type: "web" | "image" | "video" | "news" | "discover" | "googleNews"
    data_state: "final" | "all" (all includes fresh/partial data)
    """
    body: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "rowLimit": min(row_limit, 25000),
        "startRow": start_row,
        "type": search_type,
        "dataState": data_state,
        "aggregationType": aggregation_type,
    }
    if dimensions:
        body["dimensions"] = dimensions
    if filters:
        body["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]

    return _service().searchanalytics().query(siteUrl=site_url, body=body).execute()


def inspect_url(site_url: str, url: str, language: str = "en-US") -> dict[str, Any]:
    body = {"inspectionUrl": url, "siteUrl": site_url, "languageCode": language}
    return _service().urlInspection().index().inspect(body=body).execute()


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, HttpError):
        try:
            content = exc.content.decode("utf-8", errors="replace")
        except AttributeError:
            content = str(exc)
        return f"Google API error {exc.resp.status}: {content[:500]}"
    return f"{type(exc).__name__}: {exc}"
