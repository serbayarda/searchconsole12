"""Conversational GSC analyst agent using Claude tool use."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from .tools import TOOLS, dispatch

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_TOOL_ITERS = 25


def _system_prompt() -> list[dict[str, Any]]:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    text = f"""You are a senior SEO analyst with direct access to a user's Google Search Console (GSC) data via tools.

Today is {today}. GSC 'final' data lags by ~2-3 days, so the most recent complete day is usually around {yesterday} or earlier. Default windows: last 28 days of final data.

Operating principles:
1. If the user hasn't named a property, call `list_properties` first and ask them to pick (or pick the obvious single match).
2. Decompose every question into concrete GSC queries. Choose the right dimensions:
   - "top queries" -> dimensions=["query"]
   - "top pages" -> dimensions=["page"]
   - "trend over time" -> dimensions=["date"] (+ secondary if needed)
   - "by country/device" -> add those dimensions
3. For comparisons (week-over-week, month-over-month, vs prior period), prefer `compare_periods` for clean deltas. Use equal-length windows.
4. After fetching, use `run_pandas` on the returned cache_key for sorting, filtering, top-N, joins, and computed columns (e.g. CTR uplift potential, striking-distance keywords at positions 8-20, branded vs non-branded splits).
5. Always cite the date range, property, and any filters you applied. Show numbers with units (clicks, impressions, %, avg position). Highlight % deltas for comparisons.
6. When findings are large, surface the top 10-20 most decision-relevant rows rather than dumping everything. Offer to drill deeper.
7. If a tool errors (bad date, unknown property, no data), explain it plainly and adjust.
8. Be opinionated: don't just list numbers — say what they mean and what to do (e.g. "Page X is at avg position 11.4 with 8,200 impressions and 1.1% CTR; pushing it into the top 5 could roughly triple clicks").

Common analyses you should be ready to perform:
- Top movers (gainers/losers) week-over-week or month-over-month
- Striking-distance keywords (position 5-20 with strong impressions)
- Low-CTR-high-impression pages (snippet/title rewrite candidates)
- Cannibalization (multiple pages ranking for the same query)
- Country / device performance splits
- Trend / seasonality on dimensions=["date"]
- Branded vs non-branded performance (use regex filters on query)
- Indexing issues (`inspect_url`) for specific URLs

Be concise. Use markdown tables when listing rows.
"""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _cached_tools() -> list[dict[str, Any]]:
    tools = [dict(t) for t in TOOLS]
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


class Agent:
    def __init__(self) -> None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        self.client = Anthropic()
        self.messages: list[dict[str, Any]] = []
        self.system = _system_prompt()
        self.tools = _cached_tools()

    def reset(self) -> None:
        self.messages = []

    def ask(self, user_input: str, on_tool=None) -> str:
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(MAX_TOOL_ITERS):
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system,
                tools=self.tools,
                messages=self.messages,
            )

            self.messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                return _extract_text(resp.content)

            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                if on_tool:
                    on_tool(block.name, block.input)
                result_text = dispatch(block.name, block.input or {})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })
            self.messages.append({"role": "user", "content": tool_results})

        return "[stopped: hit max tool-iteration limit]"


def _extract_text(content_blocks: list[Any]) -> str:
    parts = []
    for b in content_blocks:
        if getattr(b, "type", None) == "text":
            parts.append(b.text)
    return "\n".join(parts).strip()
