# Search Console AI Agent

> **First time setting this up? Read [SETUP.md](./SETUP.md) — it's a 3-step,
> hand-held walkthrough. Don't try to follow the "Setup" section below until
> you've done that once.**

An AI agent that connects to your Google Search Console (GSC), pulls data via
the official API, and answers free-form analytical questions in natural
language. Powered by Claude Sonnet 4.6 with tool use.

Ask things like:
- "What were my top 10 queries by clicks in the last 28 days?"
- "Which pages dropped the most clicks vs the previous 28 days?"
- "Find striking-distance keywords (positions 5–15 with >500 impressions)."
- "Pages with high impressions but CTR under 1% — title rewrite candidates."
- "Compare US vs UK performance for sc-domain:example.com last month."
- "Which queries does my blog rank for that the homepage also ranks for? (cannibalization)"

The agent fetches the data it needs via GSC API calls, crunches it in pandas,
and writes the analysis. It is interactive and multi-turn — follow up to drill
deeper.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Google OAuth client (one-time)

1. Open the [Google Cloud Console](https://console.cloud.google.com/), create
   (or pick) a project.
2. **APIs & Services → Library** → enable **"Google Search Console API"**.
3. **APIs & Services → OAuth consent screen** → configure (External, add your
   own email as a test user).
4. **APIs & Services → Credentials** → **Create Credentials → OAuth client ID
   → Application type: Desktop app**.
5. Download the JSON and save it as `client_secret.json` in the repo root.
   (See `client_secret.example.json` for the expected shape.)

The Google account you sign in with must have access to the GSC properties
you want to analyze (verified owner or delegated user).

### 3. Set your Anthropic API key

```bash
cp .env.example .env
# Then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at <https://console.anthropic.com/>.

### 4. Run it

```bash
python -m src.cli
```

On the **first run** a browser window opens for Google consent. After approving,
a `token.json` is cached locally and the agent will refresh it automatically.

## CLI commands

| Command | Effect |
| --- | --- |
| `/help` | Show help |
| `/reset` | Clear conversation history |
| `/keys` | List cached DataFrames |
| `/save <key> <path.csv>` | Export a cached DataFrame to CSV |
| `/exit` | Quit |

Anything else is sent to the agent.

## Architecture

```
cli.py  ──▶  agent.py  ──Claude (tool use)──▶  tools.py  ──▶  gsc_client.py  ──▶  GSC API
                                          │
                                          └──▶  data_cache.py  (pandas DataFrames)
```

- **`auth.py`** — OAuth desktop flow, cached refresh token in `token.json`.
- **`gsc_client.py`** — thin wrapper over `googleapiclient` for Search
  Analytics, Sitemaps, URL Inspection.
- **`tools.py`** — Anthropic tool definitions + dispatcher. Tools:
  `list_properties`, `query_search_analytics`, `list_sitemaps`, `inspect_url`,
  `compare_periods`, `run_pandas`.
- **`data_cache.py`** — in-memory DataFrame cache keyed by query hash so the
  model can run further pandas analysis without re-fetching.
- **`agent.py`** — Claude client, multi-turn loop, prompt caching on the
  system prompt and tool defs.

## Notes / limits

- Read-only scope (`webmasters.readonly`). No sitemap submission, no settings
  changes.
- GSC has a ~2–3 day lag for finalized data (use `data_state="all"` in a query
  for fresh/partial data).
- GSC caps result rows at 25,000 per query; the agent pages or filters when it
  needs more.
- No persistent storage — the DataFrame cache lives in memory for the session.
  Use `/save` to export anything worth keeping.
- Out of scope for v1: scheduled reports, GA4 join, multi-property comparison
  dashboards.

## Troubleshooting

- **`FileNotFoundError: client_secret.json`** — see step 2 above.
- **`ANTHROPIC_API_KEY not set`** — copy `.env.example` to `.env` and fill in.
- **`access_denied` in browser** — your Google account isn't a verified user on
  the OAuth consent screen yet. Add it under "Test users".
- **Empty results** — the requested date range may be before your property was
  verified or have no traffic. The agent will tell you.
