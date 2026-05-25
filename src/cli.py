"""Interactive REPL for the GSC AI agent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import readline  # noqa: F401  (improves input() UX)
except ImportError:
    pass

from dotenv import load_dotenv

from . import data_cache
from .agent import Agent

ROOT = Path(__file__).resolve().parent.parent


def _preflight() -> bool:
    """Check that everything needed is in place. Print friendly fixes if not."""
    load_dotenv(ROOT / ".env")
    ok = True

    if not (ROOT / "client_secret.json").exists():
        print("\n[setup needed] client_secret.json is missing.")
        print("  -> Download an OAuth Desktop client from Google Cloud Console")
        print("     and save it as client_secret.json in this folder.")
        print("     Full steps: see SETUP.md, section 2.")
        ok = False

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("sk-ant-...") or key == "":
        print("\n[setup needed] ANTHROPIC_API_KEY is not set.")
        if not (ROOT / ".env").exists():
            print("  -> Copy .env.example to .env, then paste your key into it.")
        else:
            print("  -> Edit .env and replace the placeholder with your real key")
            print("     (get one at https://console.anthropic.com/settings/keys).")
        ok = False

    return ok


HELP = """
Commands:
  /help            Show this help
  /reset           Clear the conversation history
  /keys            List cached DataFrame keys
  /save <key> <p>  Save cached DataFrame <key> to CSV at path <p>
  /exit, /quit     Exit

Tip: just type a question, e.g.
  "List my properties"
  "Top 10 queries by clicks for https://example.com/ in the last 28 days"
  "Which pages dropped the most clicks vs the previous 28 days?"
  "Striking-distance keywords for sc-domain:example.com (positions 5-20, >500 impressions)"
"""


def _print_tool_call(name: str, args: dict) -> None:
    pretty = {k: (v if not isinstance(v, str) or len(v) < 80 else v[:77] + "...") for k, v in (args or {}).items()}
    print(f"  > calling {name}({pretty})", file=sys.stderr)


def main() -> None:
    print("Search Console AI Agent — ask anything about your GSC data.")
    print("Type /help for commands, /exit to quit.\n")

    if not _preflight():
        print("\nFix the items above, then re-run: python -m src.cli")
        sys.exit(1)

    try:
        agent = Agent()
    except Exception as e:  # noqa: BLE001
        print(f"\n[startup error] {type(e).__name__}: {e}")
        print("See SETUP.md for help, or paste this error to Claude.")
        sys.exit(1)

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        if line in {"/exit", "/quit"}:
            break
        if line == "/help":
            print(HELP)
            continue
        if line == "/reset":
            agent.reset()
            print("[conversation reset]")
            continue
        if line == "/keys":
            ks = data_cache.keys()
            print("Cached DataFrames:", ks or "(none)")
            continue
        if line.startswith("/save"):
            parts = line.split()
            if len(parts) != 3:
                print("Usage: /save <cache_key> <path.csv>")
                continue
            try:
                df = data_cache.get(parts[1])
            except KeyError as e:
                print(e)
                continue
            out = Path(parts[2]).expanduser()
            df.to_csv(out, index=False)
            print(f"Saved {len(df)} rows -> {out}")
            continue

        try:
            answer = agent.ask(line, on_tool=_print_tool_call)
        except Exception as e:  # noqa: BLE001
            print(f"[error] {type(e).__name__}: {e}", file=sys.stderr)
            continue

        print(f"\nclaude> {answer}\n")


if __name__ == "__main__":
    main()
