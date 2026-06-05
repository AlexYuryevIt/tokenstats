# tokenstats

> **Token usage statistics for AI coding agents.**
> Zero telemetry. Zero dependencies. One tool for all agents.

## Why tokenstats?

- **Zero telemetry** -- No network calls, no data collection, no "phone home"
- **Privacy-first** -- No personal data, no API keys, no accounts required
- **Works offline** -- Fully air-gap compatible, no internet connection needed
- **Zero dependencies** -- Python stdlib only, no pip install required
- **Read-only access** -- Never writes to agent data, safe for any environment
- **CI/CD ready** -- JSON/CSV export, exit codes, budget enforcement in pipelines
- **MIT license** -- Free to use, modify, and distribute
- **Cross-platform** -- macOS, Linux, Windows (PowerShell, cmd.exe, Python launcher)

## Privacy

**No network. No telemetry. No data collection.** `tokenstats` reads local files
in read-only mode. Works fully offline. No API keys, no accounts, no cloud.

## Features

| Feature                    | Description                               |
|----------------------------|-------------------------------------------|
| Multi-agent list           | All sessions from all agents in one table |
| Session detail             | Per-step: in/out/reasoning/cache/cost     |
| Efficiency analysis        | Grade A–D + anomaly Z-score               |
| Digest                     | Overview with per-provider trends         |
| Trends                     | ASCII bar charts by day                   |
| Monthly report             | Per-provider and per-project breakdown    |
| Outliers                   | Statistical z-score anomalies             |
| Compare                    | Two sessions side by side                 |
| Budget                     | Monthly spend limit + warnings            |
| Export                     | JSON and CSV                              |
| Numeric select             | `tokenstats 3` — no long IDs             |
| Search                     | `tokenstats search "query"`               |
| Provider filter            | `tokenstats --provider cursor`            |
| Auto-detect                | Finds installed agents automatically     |

## Quick start

### macOS / Linux

```bash
npm install -g tokenstats

tokenstats                      # List all sessions
tokenstats 4                    # Session details by number
tokenstats analyze 4            # Efficiency analysis
tokenstats digest               # Overall usage digest
tokenstats trends --days 14     # Usage charts
tokenstats report last          # Monthly report
tokenstats outliers             # Unusual sessions
tokenstats compare 1 4          # Compare two sessions
tokenstats search "bug"         # Search by title
tokenstats export --format csv  # Export all data
tokenstats budget --set 50      # Budget $50/month
tokenstats shell-integration    # Generate shell shortcuts
eval "$(tokenstats shell-integration)"  # Activate in ~/.zshrc / ~/.bashrc
```

### Windows (PowerShell)

```powershell
npm install -g tokenstats

tokenstats                      # List all sessions
tokenstats 4                    # Session details by number
tokenstats analyze 4            # Efficiency analysis
tokenstats digest               # Overall usage digest
tokenstats trends --days 14     # Usage charts
tokenstats report last          # Monthly report
tokenstats outliers             # Unusual sessions
tokenstats compare 1 4          # Compare two sessions
tokenstats search "bug"         # Search by title
tokenstats export --format csv  # Export all data
tokenstats budget --set 50      # Budget $50/month
tokenstats shell-integration --powershell  # Generate PowerShell shortcuts
tokenstats shell-integration --powershell | Invoke-Expression  # Activate in $PROFILE
```

## Supported agents (9)

| Agent              | Provider          | Data source          | Status |
|--------------------|-------------------|----------------------|--------|
| OpenCode           | opencode          | SQLite               | stable |
| Claude Code        | claude            | JSONL transcripts    | stable |
| Cursor             | cursor            | SQLite + JSONL       | stable |
| Cline              | cline             | JSON conversations   | stable |
| GitHub Copilot CLI | github_copilot    | JSON sessions        | stable |
| Codex CLI          | codex_cli         | JSON sessions        | stable |
| Gemini CLI         | gemini_cli        | JSON sessions        | stable |
| Goose              | goose             | JSON sessions        | stable |
| PI Agent           | pi_agent          | JSON sessions        | stable |

Auto-detects which agents are installed. Only shows what's available.

## Commands

```
tokenstats                                       List all sessions
tokenstats --provider <name>                     Filter by agent
tokenstats <N>                                   Session by number
tokenstats <session_id>                          Session by ID
tokenstats last                                  Latest session
tokenstats search <text>                         Search by title
tokenstats analyze <N|id|last>                   Analysis + tips
tokenstats compare <A> <B>                       Compare two sessions
tokenstats trends [--days N]                     Usage charts (default 30d)
tokenstats digest                                Overall usage digest
tokenstats report <YYYY-MM>                      Monthly report
tokenstats outliers                              Find unusual sessions
tokenstats export --format json|csv              Export all data
tokenstats budget [--set N]                      Budget tracking
tokenstats --list-providers                      Available agents
tokenstats --help                                This message
```

## Shell shortcuts

### Bash / Zsh

```bash
eval "$(tokenstats shell-integration)"  # add to ~/.zshrc or ~/.bashrc
```

| Shortcut        | Long form                   |
|-----------------|-----------------------------|
| `ts`            | `tokenstats`                |
| `ts-analyze`    | `tokenstats analyze`        |
| `ts-digest`     | `tokenstats digest`         |
| `ts-compare`    | `tokenstats compare`        |
| `ts-trends`     | `tokenstats trends`         |
| `ts-report`     | `tokenstats report`         |
| `ts-export`     | `tokenstats export`         |
| `ts-budget`     | `tokenstats budget`         |
| `ts-search`     | `tokenstats search`         |
| `ts-outliers`   | `tokenstats outliers`       |

### PowerShell

```powershell
tokenstats shell-integration --powershell | Invoke-Expression
# Or manually add to your PowerShell profile:
#   tokenstats shell-integration --powershell >> $PROFILE
```

| Shortcut          | Long form                   |
|-------------------|-----------------------------|
| `ts`              | `tokenstats`                |
| `ts-analyze`      | `tokenstats analyze`        |
| `ts-digest`       | `tokenstats digest`         |
| `ts-compare`      | `tokenstats compare`        |
| `ts-trends`       | `tokenstats trends`         |
| `ts-report`       | `tokenstats report`         |
| `ts-export`       | `tokenstats export`         |
| `ts-budget`       | `tokenstats budget`         |
| `ts-search`       | `tokenstats search`         |
| `ts-outliers`     | `tokenstats outliers`       |

## Architecture

```
tokenstats/
├── python/
│   ├── stats.py              CLI, formatting, all commands
│   ├── models.py             Session, Message dataclasses
│   ├── types.py              Type aliases, protocols, field docs
│   └── providers/
│       ├── base.py           BaseProvider + register registry
│       ├── opencode.py       OpenCode (SQLite)
│       ├── claude_code.py    Claude Code (JSONL)
│       ├── cursor.py         Cursor (SQLite + JSONL)
│       ├── cline.py          Cline (JSON)
│       ├── github_copilot.py GitHub Copilot CLI
│       ├── codex_cli.py      Codex CLI
│       ├── gemini_cli.py     Gemini CLI
│       ├── goose.py          Goose
│       └── pi_agent.py       PI Agent
```

**Zero dependencies** – only Python stdlib (sqlite3, json, csv, statistics, pathlib).

## Add a provider

Create `providers/my_agent.py` with three methods (detect, list_sessions, get_messages),
decorate with @register, add to providers/__init__.py. Done.

## CI/CD integration

No dependencies besides Python, works offline, pure stdout. Data sources
(`~/.config/`, `~/.local/share/`, `%APPDATA%`) must be available on the runner -- pass them
via CI cache or restore from a previous step.

```bash
# Export as JSON for downstream pipeline processing
tokenstats export --format json > token-usage.json

# Digest with totals (human-readable, exits 0 on success)
tokenstats digest

# Budget check -- exits non-zero if over limit
tokenstats budget
```

**GitHub Actions example (also works on `windows-latest` and `macos-latest`):**

```yaml
# .github/workflows/token-usage-audit.yml
name: Token usage audit
on:
  schedule:
    - cron: '0 8 * * 1'
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Cache agent data
        uses: actions/cache@v4
        with:
          path: |
            ~/.config/opencode
            ~/.claude
            ~/.config/cursor
          key: agent-data-${{ runner.os }}
      - name: Run tokenstats
        run: |
          npm install -g tokenstats
          tokenstats export --format json > token-usage.json
          tokenstats digest
          tokenstats budget
```

Security note: tokenstats makes zero network requests, requires no API keys,
and stores no personal data -- safe to run in any CI environment without
secret management.

## Security audit

- **No network calls** -- zero http, requests, socket, or urllib imports.
  Verifiable: `grep -r 'import.*http\|import.*requests' python/` returns nothing.
- **No telemetry** -- no analytics, no tracking, no "phone home".
- **No personal data** -- does not ask for name, email, API keys, or any
  identifying information.
- **Read-only access** -- all DB connections use `mode=ro` with
  `PRAGMA query_only=ON`. Never writes to agent data.
- **Local files only** -- scoped to `~/.config/`, `~/.local/share/`,
  `%APPDATA%`, `~/.claude/`, `~/.cursor/`. Never accesses files outside home directory.
- **Zero dependencies** -- Python 3 stdlib only (sqlite3, json, csv,
  statistics, pathlib). No pip packages, no npm runtime dependencies.
- **Fully offline** -- no internet required. Works in air-gapped environments.
- **Fully open source** -- MIT license. Source at
  [github.com/AlexYuryevIt/tokenstats](https://github.com/AlexYuryevIt/tokenstats).

## License

MIT – do whatever you want.
