#!/usr/bin/env python3
"""
tokenstats — Token usage statistics for AI coding agents.

Usage:
  tokenstats                               List sessions from all detected agents
  tokenstats --provider <name>              Filter by agent
  tokenstats <N|id|last>                   Session detail by number, ID, or latest
  tokenstats analyze <N|id|last>           Efficiency analysis + anomaly Z-score
  tokenstats compare <A> <B>               Side-by-side session comparison
  tokenstats digest                        Overall full digest across all sessions
  tokenstats outliers                      Flag statistically anomalous sessions
  tokenstats trends [--days N]             ASCII bar-chart daily usage trends
  tokenstats report <YYYY-MM|last>         Monthly report with totals & averages
  tokenstats export [--format json|csv]    Export all sessions as JSON or CSV
  tokenstats budget [add|set|show]         Monthly budget tracking
  tokenstats search <text>                 Search sessions by title
  tokenstats shell-integration             Install shell integration (zsh)
  tokenstats --list-providers              Show available providers
  tokenstats --help                        This message

Security: Zero telemetry. Zero network. Zero data collection.
          Reads local configuration and database files only.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from providers.base import detect_providers, get_provider, all_providers
from models import Session, Message


# ─── Config paths ──────────────────────────────────────────────────────────

if sys.platform == "win32":
    _config_base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
else:
    _config_base = Path.home() / ".config"
CONFIG_DIR = _config_base / "tokenstats"
BUDGET_FILE = CONFIG_DIR / "budget.json"

def _load_budget() -> dict:
    try:
        return json.loads(BUDGET_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

def _save_budget(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(data, indent=2))


# ─── ANSI & Unicode ─────────────────────────────────────────────────────

def _c(code, s):
    return f"\033[{code}m{s}\033[0m"

# Unicode constants (avoids backslash in f-string expressions for Python < 3.12)
_U = type('_U', (), {})()  # simple namespace
_U.hline   = '\u2500'   # ─
_U.corner  = '\u2514'   # └
_U.block   = '\u2588'   # █
_U.shade   = '\u2591'   # ░
_U.lblock  = '\u2581'   # ▁
_U.square  = '\u25a0'   # ■
_U.tri     = '\u25b6'   # ▶
_U.circle  = '\u25cf'   # ●
_U.check   = '\u2713'   # ✓
_U.xmark   = '\u2717'   # ✗
_U.warn    = '\u26a0'   # ⚠
_U.up      = '\u2191'   # ↑
_U.down    = '\u2193'   # ↓
_U.right   = '\u2192'   # →
_U.bull    = '\u2022'   # •
_U.mdash   = '\u2014'   # —
_U.lq      = '\u201c'   # "
_U.rq      = '\u201d'   # "
_U.mdot    = '\u00b7'   # ·
_U.sigma   = '\u03c3'   # σ


def format_num(n):
    if n is None:
        return _U.mdash
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def pct(a, b):
    return (a / b * 100) if b else 0


def bar(ratio, width=20, high_is_good=True):
    filled = max(0, min(int(ratio * width), width))
    empty = width - filled
    if high_is_good:
        color = "31" if ratio < 0.3 else ("33" if ratio < 0.6 else "32")
    else:
        color = "32" if ratio < 0.3 else ("33" if ratio < 0.6 else "31")
    return _c(color, _U.block * filled) + _c("2", _U.shade * empty)




def ts_str(ts):
    if not ts:
        return _U.mdash
    d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return d.strftime("%d %b %Y %H:%M")




def dollar_str(cost_micro):
    if cost_micro is None or cost_micro <= 0:
        return "$0.00"
    dollars = cost_micro / 100_000_000
    if dollars < 0.01:
        return f"${dollars:.6f}"
    if dollars < 1:
        return f"${dollars:.4f}"
    return f"${dollars:.2f}"


# ─── Core helpers ──────────────────────────────────────────────────────

def _load_all(provider_filter: Optional[str] = None) -> list[Session]:
    """Load all sessions from all (or one) provider, sorted by time DESC."""
    providers = detect_providers()
    if provider_filter:
        p = get_provider(provider_filter)
        if not p:
            print(_c("31", f"{_U.xmark} Unknown provider '{provider_filter}'"))
            print(f"  Available: {', '.join(p.name for p in all_providers())}")
            sys.exit(1)
        if not p.detect():
            print(_c("31", f"{_U.xmark} Provider '{provider_filter}' has no data on this machine"))
            sys.exit(1)
        providers = [p]

    all_sessions = []
    for p_cls in providers:
        try:
            sessions = p_cls.list_sessions()
            for s in sessions:
                s.provider = p_cls.name
            all_sessions.extend(sessions)
        except Exception as e:
            print(_c("33", f"  Warning: {p_cls.name} error: {e}"), file=sys.stderr)

    all_sessions.sort(key=lambda s: s.time_created or 0, reverse=True)
    return all_sessions


def _resolve_session(all_sessions: list[Session], spec: str) -> Optional[Session]:
    if spec == "last":
        return all_sessions[0] if all_sessions else None

    try:
        n = int(spec)
        if 1 <= n <= len(all_sessions):
            return all_sessions[n - 1]
    except ValueError:
        pass

    for s in all_sessions:
        if s.id == spec:
            return s
    return None


def _find_messages(session: Session) -> list[Message]:
    p_cls = get_provider(session.provider)
    if not p_cls:
        return []
    try:
        return p_cls.get_messages(session.id)
    except Exception:
        return []


# ─── Commands ────────────────────────────────────────────────────────────

def cmd_list(all_sessions: list[Session], provider_filter: Optional[str] = None):
    if not all_sessions:
        if provider_filter:
            print(_c("33", f"No sessions found for '{provider_filter}'."))
        else:
            print(_c("33", "No sessions found from any agent."))
            print("  Detected agents: " + ", ".join(p.name for p in detect_providers()) if detect_providers() else "  No agents detected.")
        return

    agent_counts: dict[str, int] = {}
    for s in all_sessions:
        agent_counts[s.provider] = agent_counts.get(s.provider, 0) + 1

    label = "All agents" if not provider_filter else provider_filter
    counts_str = ", ".join(f"{p}: {c}" for p, c in sorted(agent_counts.items()))
    print(f"\n  {_c('1', 'Sessions')}  ({len(all_sessions)} total — {counts_str})\n")

    sep = _U.hline * 130
    print(f"  {sep}")
    header_str = f"{'':>4} {'ID':<24} {'Provider':<10} {'Title':<50} {'Input':>10} {'Output':>10} {'Cache':>10} {'Steps':>6}"
    print(f"  {_c('1', header_str)}")
    print(f"  {sep}")

    for i, s in enumerate(all_sessions, 1):
        idx_str = f"{str(i):>4}"
        sid_str = f"{s.id[:24]:<24}"
        prov_str = f"{s.provider:<10}"
        title_str = f"{(s.title or '')[:48]:<50}"
        print(
            f"  {_c('2', idx_str)} "
            f"{_c('36', sid_str)} "
            f"{_c('33', prov_str)} "
            f"{_c('97', title_str)} "
            f"{format_num(s.input_tokens):>10} {format_num(s.output_tokens):>10} {format_num(s.cache_read):>10} "
            f"{s.steps:>6}"
        )

    print(f"  {sep}\n")
    print(f"  {_c('2', 'Select: tokenstats <N>  |  Details: tokenstats <N>  |  Analysis: tokenstats analyze <N>')}")
    print(f"  {_c('2', 'Filter:  tokenstats --provider <name>')}")
    print()


def cmd_detail(session: Session):
    print(f"\n  {_c('1', 'Session details')}")
    print(f"  {_U.hline * 80}")
    print(f"  {_c('36', 'Provider:')} {session.provider}")
    print(f"  {_c('36', 'ID:')}      {session.id}")
    print(f"  {_c('36', 'Title:')}   {session.title or '(untitled)'}")
    print(f"  {_c('36', 'Date:')}    {ts_str(session.time_created)}")
    if session.model:
        print(f"  {_c('36', 'Model:')}   {session.model[:60]}")
    print()

    ti = session.input_tokens
    to = session.output_tokens
    tr = session.reasoning_tokens
    tcr = session.cache_read
    tcw = session.cache_write
    cost = session.cost
    total = ti + to

    def _row(label, val, pct_val=None, pct_of=None):
        pct_s = f"  {pct(pct_val, pct_of):5.1f}%" if pct_val is not None and pct_of else ""
        denom = max(pct_of, val, 1) if pct_of is not None else val or 1
        padded_label = f"{label + ':' :<25}"
        return f"  {_c('97', padded_label)} {format_num(val):>12}  {bar(val / denom, 15)} {pct_s}"

    print(f"  {_c('1', 'Token usage')}")
    print(f"  {_U.hline * 60}")
    print(_row("Total", total))
    print(_row("Input (prompt)", ti, ti, total))
    print(_row("Output (response)", to, to, total))
    print(
        f"  {_c('97', f'{_U.corner} Reasoning:'.ljust(25))} {format_num(tr):>12}  {bar(tr / max(to, 1), 15, high_is_good=False)}  {pct(tr, to):5.1f}% of output"
    )
    print(
        f"  {_c('97', 'Cache read:'.ljust(25))} {format_num(tcr):>12}  {bar(tcr / max(ti, 1), 15)}  {pct(tcr, ti):5.1f}% of input"
    )
    print(f"  {_c('97', 'Cache write:'.ljust(25))} {format_num(tcw):>12}")
    print(f"  {_c('33', 'Cost:'.ljust(25))} {dollar_str(cost):>12}")

    messages = _find_messages(session)
    if messages:
        print(f"\n  {_c('1', f'Step-by-step breakdown ({len(messages)} steps)')}")
        print(f"  {_U.hline * 90}")
        cols = [
            ("#", 4), ("Input", 8), ("Output", 8), ("Reason", 8),
            ("CacheR", 8), ("CacheW", 8), ("Total", 8), ("Cost", 10), ("Finish", 20),
        ]
        hdr = " " + _c("1", "".join(label.rjust(w) for label, w in cols))
        print(hdr)
        print(f"  {_U.hline * 90}")

        for i, m in enumerate(messages, 1):
            step_total = m.input_tokens + m.output_tokens
            print(
                f"  {i:>4} "
                f"{format_num(m.input_tokens):>8} {format_num(m.output_tokens):>8} {format_num(m.reasoning_tokens):>8} "
                f"{format_num(m.cache_read):>8} {format_num(m.cache_write):>8} "
                f"{_c('1', f'{format_num(step_total):>8}')} "
                f"{_c('33', f'{dollar_str(m.cost):>10}')} "
                f"  {_c('2', f'{m.finish_reason[:18]:<20}')}"
            )
        print(f"  {_U.hline * 90}")

    print(
        f"\n  {_c('2', 'Hint: tokenstats analyze ' + session.id + ' — efficiency analysis + tips')}\n"
    )


def cmd_analyze(session: Session, all_sessions: Optional[list[Session]] = None):
    ti = session.input_tokens
    to = session.output_tokens
    tr = session.reasoning_tokens
    tcr = session.cache_read
    tcw = session.cache_write
    cost = session.cost
    total = ti + to

    messages = _find_messages(session)
    n_steps = len(messages)
    tips = []

    if total == 0:
        print(_c("31", "  No token data for this session."))
        return

    anomalies = []
    if all_sessions and len(all_sessions) >= 5:
        from statistics import median, stdev
        totals = [(s.input_tokens + s.output_tokens) for s in all_sessions]
        costs = [s.cost for s in all_sessions]
        raw_ratios = []
        for s in all_sessions:
            t = s.input_tokens + s.output_tokens
            raw_ratios.append(s.output_tokens / max(t, 1))

        this_total = ti + to
        m_total = median(totals)
        sd_total = stdev(totals) if len(totals) > 1 else 1
        z_total = (this_total - m_total) / max(sd_total, 1)

        if z_total > 2:
            anomalies.append((_c("31", _U.warn), f"Anomalously large ({z_total:.1f}{_U.sigma} above median)"))
        elif z_total > 1.5:
            anomalies.append((_c("33", _U.warn), f"Larger than average ({z_total:.1f}{_U.sigma} above median)"))
        elif z_total < -1.5:
            anomalies.append((_c("32", _U.check), f"Smaller than average ({abs(z_total):.1f}{_U.sigma} below median)"))

        if cost > 0:
            m_cost = median(costs)
            sd_cost = stdev(costs) if len(costs) > 1 else 1
            z_cost = (cost - m_cost) / max(sd_cost, 1)
            if z_cost > 2:
                anomalies.append((_c("31", _U.warn), f"Anomalously expensive ({z_cost:.1f}{_U.sigma} above median)"))

        this_ratio = to / max(this_total, 1)
        m_ratio = median(raw_ratios)
        if this_ratio > m_ratio * 1.5:
            anomalies.append((_c("33", _U.warn), f"Output ratio higher than typical"))
        elif this_ratio < m_ratio * 0.5:
            anomalies.append((_c("33", _U.warn), f"Input ratio higher than typical"))

    # Derived metrics
    cache_ratio = tcr / ti if ti > 0 else 0
    reasoning_ratio = tr / to if to > 0 else 0
    tool_call_steps = sum(
        1 for m in messages if m.finish_reason in ("tool-calls", "tool_use")
    )
    tool_ratio = pct(tool_call_steps, n_steps) if n_steps > 0 else 0
    avg_in_per_step = ti // max(n_steps, 1)
    avg_out_per_step = to // max(n_steps, 1)
    avg_total_per_step = total // max(n_steps, 1)
    cache_hit_pct = min(cache_ratio * 100, 9999)

    # Grade
    def session_grade():
        score = 0
        if cache_ratio > 2:
            score += 3
        elif cache_ratio > 1:
            score += 2
        elif cache_ratio > 0.5:
            score += 1
        if reasoning_ratio < 0.1:
            score += 2
        elif reasoning_ratio < 0.25:
            score += 1
        if n_steps < 15:
            score += 2
        elif n_steps < 50:
            score += 1
        if tool_ratio < 50:
            score += 1
        if score >= 7:
            return _c("1;32", "A")
        if score >= 5:
            return _c("1;33", "B")
        if score >= 3:
            return _c("1;33", "C")
        return _c("1;31", "D")

    print(f"\n  {_U.hline * 78}")
    print(f"  {_c('1', f'Efficiency analysis')}  {_c('2', session.id[:36])}")
    print(f"  {_U.hline * 78}")
    print(f"  {_c('2', 'Title:')}  {session.title or '(untitled)'}")
    print(f"  {_c('2', 'Model:')}  {session.model or '?'}")
    print(f"  {_c('2', 'Grade:')}  {session_grade()}  ({n_steps} steps, "
          f"{format_num(ti)} in / {format_num(to)} out)")
    print(f"  {_U.hline * 78}\n")

    print(f"  {_c('1', 'Anomaly detection')}")
    print(f"  {'' :->50}")
    if anomalies:
        for icon, msg in anomalies:
            print(f"  {icon} {_c('97', msg)}")
    else:
        print(f"  {_c('32', f'{_U.check} No significant anomalies')}  {_c('2', 'this session is typical for your usage')}")
    print()

    print(f"  {_c('1', 'Token overview')}")
    print(f"  {'' :->50}")

    def sparkline(val, max_val, length=30, high_is_good=None, fixed_color=None):
        filled = max(0, min(int(val / max(max_val, 1) * length), length))
        empty = length - filled
        if fixed_color:
            color = fixed_color
        elif val == 0:
            color = "2"
        elif high_is_good is None:
            color = "34"
        elif high_is_good:
            color = "31" if filled < length * 0.3 else ("33" if filled < length * 0.6 else "32")
        else:
            color = "32" if filled < length * 0.3 else ("33" if filled < length * 0.6 else "31")
        return _c(color, _U.block * filled) + _c("2", _U.shade * empty)

    max_metric = max(ti, to, tcr, 1)
    pct_in = pct(ti, total)
    pct_out = pct(to, total)

    print(f"  {_c('97', 'Input tokens:')}     {format_num(ti):>10}  "
          f"{sparkline(ti, max_metric)}  {_c('2', f'{pct_in:.1f}% of total')}")
    print(f"  {_c('97', 'Output tokens:')}    {format_num(to):>10}  "
          f"{sparkline(to, max_metric)}  {_c('2', f'{pct_out:.1f}% of total')}")
    if tr:
        print(f"  {_c('97', 'Reasoning tokens:')}  {format_num(tr):>10}  "
              f"{sparkline(tr, max(to, 1), high_is_good=False)}  {_c('2', f'{pct(tr, to):.1f}% of output')}")
    if tcr:
        print(f"  {_c('97', 'Cache read:')}      {format_num(tcr):>10}  "
              f"{sparkline(tcr, max_metric)}  {_c('2', f'{cache_hit_pct:.0f}% of input')}")

    # Efficiency score bar
    efficiency_pct = min(cache_ratio / 3 * 50 + (1 - reasoning_ratio) * 40 + max(0, 1 - n_steps / 100) * 10, 100)
    eff_color = "32" if efficiency_pct >= 70 else ("33" if efficiency_pct >= 40 else "31")
    filled = max(0, min(int(efficiency_pct / 100 * 30), 30))
    print(f"\n  {_c('1', 'Efficiency:')}  {_c(eff_color, _U.block * filled + _U.shade * (30 - filled))}"
          f"  {_c(eff_color, f'{efficiency_pct:.0f}%')}")
    print()

    if n_steps > 1:
        # Find biggest step
        step_totals = [m.input_tokens + m.output_tokens for m in messages]
        max_step = max(step_totals)
        max_step_idx = step_totals.index(max_step) + 1
        min_step = min(step_totals)
        min_step_idx = step_totals.index(min_step) + 1
        print(f"  Biggest step:  {_c('33', f'{format_num(max_step):>10}')}  (#{max_step_idx})")
        print(f"  Smallest step: {_c('32', f'{format_num(min_step):>10}')}  (#{min_step_idx})")

        # Step size distribution
        if n_steps >= 5:
            small = sum(1 for t in step_totals if t < avg_total_per_step * 0.5)
            medium = sum(1 for t in step_totals if avg_total_per_step * 0.5 <= t < avg_total_per_step * 1.5)
            large = sum(1 for t in step_totals if t >= avg_total_per_step * 1.5)
            s_pct = pct(small, n_steps)
            m_pct = pct(medium, n_steps)
            l_pct = pct(large, n_steps)
            print(f"  Distribution:  {_c('32', f'{_U.square} {s_pct:.0f}%')} {_c('33', f'{_U.square} {m_pct:.0f}%')}"
                  f" {_c('31', f'{_U.square} {l_pct:.0f}%')}  "
                  f"{_c('2', 'small / medium / large')}")
            # Step bar chart
            bar_w = min(n_steps, 30)
            step_chars = ""
            for idx in range(bar_w):
                step_idx = round(idx * (n_steps - 1) / (bar_w - 1)) if bar_w > 1 else 0
                t = step_totals[step_idx]
                if t < avg_total_per_step * 0.5:
                    step_chars += _c("32", _U.lblock)
                elif t < avg_total_per_step * 1.5:
                    step_chars += _c("33", _U.lblock)
                else:
                    step_chars += _c("31", _U.lblock)
            print(f"  Steps:         {step_chars}")

    print(f"  Tool calls:    {tool_call_steps}/{n_steps}  ({_c('33', f'{tool_ratio:.0f}%')})")

    if n_steps > 50:
        tips.append(("warning", "Too many small steps", [
            f"{n_steps} steps add {format_num(n_steps * 1000)} tokens of prompt overhead",
            'Batch multiple changes in one request',
        ]))
    if tool_ratio > 70:
        tips.append(("warning", "High tool-call ratio", [
            f"{tool_ratio:.0f}% of steps end with a tool call",
            "Group commands: `cmd1 && cmd2` instead of separate steps",
        ]))
    if n_steps <= 15 and tool_ratio <= 70:
        tips.append(("good", "Compact session — low overhead", []))
    print()

    print(f"  {_c('1', 'Cache analysis')}")
    print(f"  {'' :->50}")
    if ti > 0:
        if cache_ratio > 0:
            reads_pct = cache_ratio * 100
            print(f"  Cache reads:  {reads_pct:.1f}% of input  "
                  f"{bar(min(cache_ratio, 3) / 3, 20)}")
        else:
            print(f"  Cache reads:  none")
        if cache_ratio >= 1:
            print(f"  Reuse:        {_c('32', f'{cache_ratio:.1f}x')}  "
                  f"({_c('2', 'each input token read from cache multiple times')})")

        if tcw > 0:
            print(f"  Cache writes: {format_num(tcw)} tokens written to cache")

        if cache_ratio < 0.1:
            tips.append(("critical", "Prompt cache is unused", [
                "Cache can reduce costs by 50-90%",
                "Longer sessions with stable system prompts improve caching",
                'Set cachePolicy in provider config if supported',
            ]))
        elif cache_ratio < 0.5:
            tips.append(("warning", "Low cache efficiency", [
                f"Only {cache_ratio * 100:.0f}% of input from cache",
                "Keep AGENTS.md stable across steps",
                "Group related tasks in one session",
            ]))
        elif cache_ratio >= 1:
            tips.append(("good", "Excellent cache reuse", [
                f"Each input token reused {cache_ratio:.1f}x on average",
                "Cache is working well — keep long sessions",
            ]))
    print()

    if to > 0:
        print(f"  {_c('1', 'Reasoning')}")
        print(f"  {'' :->50}")
        print(f"  Reasoning:    {format_num(tr)} tokens  "
              f"{bar(reasoning_ratio, 20, high_is_good=False)}  {reasoning_ratio * 100:.1f}% of output")

        if reasoning_ratio > 0.5:
            tips.append(("warning", "High reasoning overhead", [
                f"{reasoning_ratio * 100:.0f}% of output is model thinking",
                'For simple edits, set reasoningEffort: "low"',
            ]))
        elif reasoning_ratio < 0.1:
            tips.append(("good", "Low reasoning — direct answers", []))
        elif reasoning_ratio < 0.25:
            tips.append(("good", "Moderate reasoning — healthy balance", []))
        print()

    if cost > 0:
        cost_per_step = cost / max(n_steps, 1)
        cost_per_input = cost / max(ti, 1) * 1_000_000  # $ per M tokens

        print(f"  {_c('1', 'Cost')}")
        print(f"  {'' :->50}")
        print(f"  Total:        {_c('33', f'${cost:.6f}')}")
        print(f"  Per step:     {_c('33', f'${cost_per_step:.6f}')}")
        if cost_per_input > 0:
            print(f"  Per 1M in:    {_c('33', f'${cost_per_input:.4f}')}")
        if cost > 0.01:
            tips.append(("warning", "Session cost adds up", [
                f"Total ${cost:.4f}",
                "Consider smaller models for simple tasks",
            ]))
        print()

    cache_savings = max(0, int(ti * (1 - tcr / max(ti, 1)) * 0.3)) if tcr > 0 else 0
    overhead_per_step = min(int(ti / max(n_steps, 1) * 0.15), 500)
    step_savings = overhead_per_step * max(0, n_steps - 20) if n_steps > 20 else 0
    reasoning_savings = int(to * 0.3) if reasoning_ratio > 0.5 else 0
    total_savable = cache_savings + step_savings + reasoning_savings

    print(f"  {_c('1', 'Potential savings')}")
    print(f"  {'' :->50}")

    if total_savable > 0:
        pct_savable = pct(total_savable, total)
        print(f"  {_c('97', f'{format_num(total_savable):>10} tokens')} can be saved "
              f"({_c('33', f'{pct_savable:.0f}%')} of session)")
        if cache_savings:
            print(f"  {_c('32', _U.up)}  Cache:        +{format_num(cache_savings):>8}  "
                  f"({_c('2', 'improve cache hit rate')})")
        if step_savings:
            print(f"  {_c('33', _U.up)}  Batching:     +{format_num(step_savings):>8}  "
                  f"({_c('2', 'fewer steps = less overhead')})")
        if reasoning_savings:
            print(f"  {_c('33', _U.up)}  Reasoning:    +{format_num(reasoning_savings):>8}  "
                  f"({_c('2', 'lower reasoningEffort')})")
    else:
        print(f"  {_c('32', f'Session is already optimal {_U.check}')}")
        print(f"  {_c('2', '  Nothing significant to improve here')}")
    print(f"  {'' :->50}")

    if tips:
        print(f"\n  {_c('1', 'Recommendations')}")
        print(f"  {_U.hline * 78}")
        for severity, title, items in tips:
            icon = _c("31", _U.circle) if severity == "critical" else (
                _c("33", _U.circle) if severity == "warning" else _c("32", _U.circle))
            has_items = len(items) > 0
            if has_items:
                print(f"  {icon} {_c('1', title)}")
                for item in items:
                    print(f"  {_c('2', _U.bull)} {item}")
            else:
                print(f"  {icon} {_c('1', title)}")
        print(f"  {_U.hline * 78}")

    print(
        f"\n  {_c('2', 'Edit opencode.json (OpenCode) or settings.json (others) to apply config changes.')}"
    )
    print()


def cmd_digest(all_sessions: list[Session]):
    if not all_sessions:
        print(_c("33", "  No sessions found."))
        return

    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    day_ms = 86_400_000

    total_in = sum(s.input_tokens for s in all_sessions)
    total_out = sum(s.output_tokens for s in all_sessions)
    total_cost = sum(s.cost for s in all_sessions)
    total_sessions = len(all_sessions)

    providers: dict[str, list[Session]] = {}
    for s in all_sessions:
        providers.setdefault(s.provider, []).append(s)

    recent = [s for s in all_sessions if s.time_created and s.time_created > now - 7 * day_ms]
    prev = [s for s in all_sessions if s.time_created and now - 14 * day_ms <= s.time_created <= now - 7 * day_ms]

    # Sessions per day
    if all_sessions[0].time_created and all_sessions[-1].time_created:
        span_days = max(1, (all_sessions[0].time_created - all_sessions[-1].time_created) / day_ms)
    else:
        span_days = 1
    sessions_per_day = total_sessions / span_days

    avg_in = total_in // max(total_sessions, 1)
    avg_out = total_out // max(total_sessions, 1)

    sessions_day = len(recent) / len(prev) if prev else None

    print(f"\n  {_c('1', 'Digest')}  {_c('2', 'overall token usage across all sessions')}")
    print(f"  {_U.hline * 70}")

    print(f"  {_c('97', 'Sessions:      ')} {total_sessions}  "
          f"({sessions_per_day:.1f}/day)")
    print(f"  {_c('97', 'Total in:      ')} {format_num(total_in):>12} tokens")
    print(f"  {_c('97', 'Total out:     ')} {format_num(total_out):>12} tokens")
    print(f"  {_c('97', 'Avg / session: ')} {format_num(avg_in):>8} in  {format_num(avg_out):>8} out")
    if total_cost:
        print(f"  {_c('33', 'Total cost:    ')} {dollar_str(total_cost):>12}")

    # Trend arrow
    if recent or prev:
        trend_str = ""
        if sessions_day is None:
            trend_str = _c("32", f'{_U.up} {len(recent)} vs 0 (new activity)')
        elif sessions_day > 1.5:
            trend_str = _c("31", f'{_U.up} {len(recent)} vs {len(prev)} ({(sessions_day - 1) * 100:.0f}% up)')
        elif sessions_day < 0.5:
            trend_str = _c("32", f'{_U.down} {len(recent)} vs {len(prev)} ({(1 - sessions_day) * 100:.0f}% down)')
        else:
            trend_str = _c("33", f'{_U.right} {len(recent)} vs {len(prev)} (steady)')
        print(f"  {_c('97', 'Trend (7d):    ')} {trend_str}")

    print()

    # Per-provider breakdown
    print(f"  {_c('1', 'Per provider')}")
    print(f"  {_U.hline * 70}")
    digest_hdr = f"{'Provider':<14} {'Sessions':>8} {'Input':>12} {'Output':>12} {'Cost':>12}"
    print(f"  {_c('1', digest_hdr)}")
    for pname in sorted(providers):
        ps = providers[pname]
        p_in = sum(s.input_tokens for s in ps)
        p_out = sum(s.output_tokens for s in ps)
        p_cost = sum(s.cost for s in ps)
        print(f"  {pname:<14} {len(ps):>8} {format_num(p_in):>12} {format_num(p_out):>12} {dollar_str(p_cost):>12}")

    # Top 3 largest
    print()
    print(f"  {_c('1', 'Largest sessions')}")
    print(f"  {_U.hline * 70}")
    sorted_by_total = sorted(all_sessions, key=lambda s: s.input_tokens + s.output_tokens, reverse=True)
    for i, s in enumerate(sorted_by_total[:3], 1):
        total = s.input_tokens + s.output_tokens
        print(f"  {i}. {_c('33', f'{s.provider:>14}')} {format_num(total):>12}  "
              f"{_c('36', f'{s.title[:48]:<48}')}")

    print()


def cmd_outliers(all_sessions: list[Session]):
    if not all_sessions or len(all_sessions) < 3:
        print(_c("33", "  Need at least 3 sessions for outlier detection."))
        return

    from statistics import median, stdev

    def z_score(val, values):
        if len(values) < 3:
            return 0
        m = median(values)
        sd = stdev(values) if len(values) > 1 else 1
        return (val - m) / max(sd, 1)

    print(f"\n  {_c('1', 'Outliers')}  {_c('2', 'sessions with unusual characteristics')}")
    print(f"  {_U.hline * 70}")

    totals = [s.input_tokens + s.output_tokens for s in all_sessions]
    costs = [s.cost for s in all_sessions]
    steps_counts = [s.steps for s in all_sessions]
    ratios = []
    for s in all_sessions:
        tot = s.input_tokens + s.output_tokens
        ratios.append(s.output_tokens / max(tot, 1))

    outputs = [s.output_tokens for s in all_sessions]
    reasoning_ratios = []
    for s in all_sessions:
        rr = s.reasoning_tokens / max(s.output_tokens, 1)
        reasoning_ratios.append(rr)

    cache_ratios = []
    for s in all_sessions:
        cr = s.cache_read / max(s.input_tokens, 1)
        cache_ratios.append(cr)

    # Collect outliers with z > 2
    found = []

    for i, s in enumerate(all_sessions):
        z = z_score(totals[i], totals)
        if z > 2:
            found.append((z, f"Large session ({format_num(totals[i])} tokens)", s))
        elif z < -1.5:
            found.append((abs(z), f"Small session ({format_num(totals[i])} tokens)", s))

        if costs[i] > 0:
            zc = z_score(costs[i], costs)
            if zc > 2:
                found.append((zc, f"High cost ({dollar_str(costs[i])})", s))

        zs = z_score(steps_counts[i], steps_counts)
        if zs > 2:
            found.append((zs, f"Many steps ({steps_counts[i]})", s))

        if ratios[i] > 0.9:
            found.append((3.0, f"Output-heavy ({(ratios[i]*100):.0f}% out)", s))
        elif ratios[i] < 0.1 and totals[i] > 0:
            found.append((2.0, f"Input-heavy ({(ratios[i]*100):.0f}% out)", s))

        if s.reasoning_tokens and outputs[i] > 0:
            zr = z_score(reasoning_ratios[i], reasoning_ratios)
            if zr > 2:
                found.append((zr, f"High reasoning ({(reasoning_ratios[i]*100):.0f}%)", s))

        if s.cache_read and s.input_tokens > 0:
            zc = z_score(cache_ratios[i], cache_ratios)
            if zc < -1.5:
                found.append((abs(zc), f"Low cache ({(cache_ratios[i]*100):.0f}%)", s))

    found.sort(key=lambda x: x[0], reverse=True)

    if not found:
        print(f"  {_c('32', 'No significant outliers found.')}")
        print()
        return

    seen_ids = set()
    for z, label, s in found[:15]:
        if s.id in seen_ids:
            continue
        seen_ids.add(s.id)
        print(f"  {_c('31', _U.tri)} {_c('1', f'{label:<50}')}  {_c('36', f'{s.id[:20]:<20}')}  "
              f"{_c('33', f'{s.provider:<12}')}  {_c('2', (s.title or '')[:24])}")
    print()


def cmd_export(all_sessions: list[Session], fmt: str):
    if fmt == "json":
        data = []
        for s in all_sessions:
            data.append({
                "id": s.id, "title": s.title, "provider": s.provider,
                "project": s.project, "model": s.model, "steps": s.steps,
                "input_tokens": s.input_tokens, "output_tokens": s.output_tokens,
                "reasoning_tokens": s.reasoning_tokens,
                "cache_read": s.cache_read, "cache_write": s.cache_write,
                "cost_usd": s.cost / 100_000_000 if s.cost else 0,
                "time_created": s.time_created,
            })
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif fmt == "csv":
        import csv, io
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["id","title","provider","project","model","steps",
                     "input_tokens","output_tokens","reasoning_tokens",
                     "cache_read","cache_write","cost_usd","time_created"])
        for s in all_sessions:
            w.writerow([
                s.id, s.title, s.provider, s.project, s.model, s.steps,
                s.input_tokens, s.output_tokens, s.reasoning_tokens,
                s.cache_read, s.cache_write,
                f"{s.cost / 100_000_000:.8f}" if s.cost else "0",
                s.time_created,
            ])
        print(out.getvalue(), end="")
    else:
        print(_c("31", f"  Unknown format: {fmt}. Use json or csv."))


def cmd_compare(s1: Session, s2: Session):
    print(f"\n  {_c('1', 'Comparison')}")
    print(f"  {_U.hline * 100}")
    label_a = (s1.title or "(untitled)")[:36]
    label_b = (s2.title or "(untitled)")[:36]
    empty_col = f"{'':>42}"
    metric_hdr = f"{'Metric':<30}"
    a_hdr = f"{'Session A':<20}"
    b_hdr = f"{'Session B':<20}"
    print(f"  {_c('1', empty_col)}  {_c('36', f'{label_a:<42}')}  {_c('36', f'{label_b:<42}')}")
    print(f"  {_c('1', metric_hdr)}  {_c('1', a_hdr)}  {_c('1', b_hdr)}  {'Diff'}")

    pairs = [
        ("Provider", s1.provider, s2.provider, "s"),
        ("Project", s1.project, s2.project, "s"),
        ("Model", s1.model[:20], s2.model[:20], "s"),
        ("Steps", str(s1.steps), str(s2.steps), "n"),
        ("Input tokens", format_num(s1.input_tokens), format_num(s2.input_tokens), "t"),
        ("Output tokens", format_num(s1.output_tokens), format_num(s2.output_tokens), "t"),
        ("Reasoning", format_num(s1.reasoning_tokens), format_num(s2.reasoning_tokens), "t"),
        ("Cache read", format_num(s1.cache_read), format_num(s2.cache_read), "t"),
        ("Cost", dollar_str(s1.cost), dollar_str(s2.cost), "$"),
    ]

    print(f"  {_U.hline * 100}")
    for label, va, vb, typ in pairs:
        if typ == "s":
            eq = _c("32", _U.check) if va == vb else _c("33", _U.xmark)
            print(f"  {label:<30} {va:<24} {vb:<24} {eq}")
        elif typ == "n":
            diff = int(vb) - int(va)
            ds = f"+{diff}" if diff > 0 else str(diff)
            dc = "32" if diff < 0 else "31"
            print(f"  {label:<30} {va:<24} {vb:<24} {_c(dc, f'{ds:>6}')}")
        elif typ == "t":
            def _n(v):
                return int(v.replace(",", "")) if v != _U.mdash else 0
            da, db = _n(va), _n(vb)
            diff = db - da
            p = diff / max(da, 1) * 100
            ds = f"{'+' if diff > 0 else ''}{format_num(abs(diff))} ({p:+.0f}%)"
            dc = "31" if p > 10 else ("32" if p < -10 else "33")
            print(f"  {label:<30} {va:<24} {vb:<24} {_c(dc, ds)}")
        elif typ == "$":
            da = s1.cost / 100_000_000
            db = s2.cost / 100_000_000
            diff = db - da
            ds = f"{'+' if diff > 0 else ''}${diff:.6f}"
            dc = "31" if diff > 0.001 else ("32" if diff < -0.001 else "33")
            print(f"  {label:<30} {va:<24} {vb:<24} {_c(dc, ds)}")

    # Winner picker
    print(f"  {_U.hline * 100}")
    t1 = s1.input_tokens + s1.output_tokens
    t2 = s2.input_tokens + s2.output_tokens
    c1 = s1.cost / 100_000_000
    c2 = s2.cost / 100_000_000
    print(f"  Winner: ", end="")
    if t1 < t2 and c1 <= c2:
        print(f"{_c('32', 'A uses fewer tokens and costs less')}")
    elif t2 < t1 and c2 <= c1:
        print(f"{_c('32', 'B uses fewer tokens and costs less')}")
    else:
        print(f"{_c('33', f'Trade-off {_U.mdash} depends on priority (speed vs cost)')}")
    print()


def cmd_trends(all_sessions: list[Session], days: int = 30):
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    day_ms = 86_400_000
    cutoff = now - days * day_ms

    # Bucket by day
    from collections import OrderedDict
    days_map: dict[str, list[Session]] = OrderedDict()
    for i in range(days - 1, -1, -1):
        d = datetime.fromtimestamp((now - i * day_ms) / 1000, tz=timezone.utc)
        days_map[d.strftime("%Y-%m-%d")] = []

    for s in all_sessions:
        if not s.time_created or s.time_created < cutoff:
            continue
        d = datetime.fromtimestamp(s.time_created / 1000, tz=timezone.utc)
        key = d.strftime("%Y-%m-%d")
        if key in days_map:
            days_map[key].append(s)

    dates = list(days_map.keys())
    max_sessions = max((len(v) for v in days_map.values()), default=1)
    max_tokens = max((sum(x.input_tokens + x.output_tokens for x in v) for v in days_map.values()), default=1)

    print(f"\n  {_c('1', f' Trends (last {days} days)')}")
    print(f"  {_U.hline * 70}")

    # Sessions per day
    print(f"\n  {_c('1', 'Sessions per day')}")
    barlen = 40
    for key in dates:
        n = len(days_map[key])
        filled = int(n / max(max_sessions, 1) * barlen) if n else 0
        pct_val = n / max(max_sessions, 1) * 100
        color = "32" if pct_val > 66 else ("33" if pct_val > 33 else "2")
        bar_s = _c(color, _U.block * filled) + _c("2", _U.shade * (barlen - filled))
        print(f"  {key}  {bar_s}  {_c('1', str(n) if n else '-')}")

    # Tokens per day (top 3 providers)
    print(f"\n  {_c('1', 'Token volume per day')}")
    for key in dates:
        sessions = days_map[key]
        if not sessions:
            print(f"  {key}  {_c('2', _U.shade * barlen)}  -")
            continue
        total = sum(s.input_tokens + s.output_tokens for s in sessions)
        filled = int(total / max_tokens * barlen)
        bar_s = _c("34", _U.block * filled) + _c("2", _U.shade * (barlen - filled))
        print(f"  {key}  {bar_s}  {format_num(total)}")

    # Summary stats
    active = sum(1 for v in days_map.values() if v)
    total_s = sum(len(v) for v in days_map.values())
    total_t = sum(sum(s.input_tokens + s.output_tokens for s in v) for v in days_map.values())
    print(f"\n  {_c('2', f'{active}/{days} days active  {_U.mdot}  {total_s} sessions  {_U.mdot}  {format_num(total_t)} total tokens')}")
    print()


def cmd_budget(all_sessions: list[Session], args: list[str]):
    budget = _load_budget()
    monthly_limit = budget.get("monthly_limit", 0)

    if args and args[0] == "--set" and len(args) >= 2:
        try:
            monthly_limit = float(args[1])
            budget["monthly_limit"] = monthly_limit
            _save_budget(budget)
            print(_c("32", f"  Monthly budget set to ${monthly_limit:.2f}"))
            return
        except ValueError:
            print(_c("31", "  Usage: tokenstats budget --set <amount>"))
            return

    if args and args[0] == "--reset":
        budget["monthly_limit"] = 0
        budget["spent"] = {}
        _save_budget(budget)
        print(_c("32", "  Budget tracking reset"))
        return

    # Calculate current month spend
    now = datetime.now(timezone.utc)
    month_start = int(datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp() * 1000)

    month_spend = 0
    for s in all_sessions:
        if s.time_created and s.time_created >= month_start and s.cost:
            month_spend += s.cost

    month_spend_usd = month_spend / 100_000_000

    print(f"\n  {_c('1', 'Budget')}  {_c('2', now.strftime('%B %Y'))}")
    print(f"  {_U.hline * 50}")

    if monthly_limit > 0:
        pct_used = (month_spend_usd / monthly_limit * 100) if monthly_limit else 0
        barw = 30
        filled = min(int(pct_used / 100 * barw), barw)
        color = "32" if pct_used < 50 else ("33" if pct_used < 80 else "31")
        bar_s = _c(color, _U.block * filled) + _c("2", _U.shade * (barw - filled))

        print(f"  Budget:       ${monthly_limit:.2f}/month")
        print(f"  Spent:        ${month_spend_usd:.4f}")
        print(f"  Usage:        {bar_s}  {_c('1', f'{pct_used:.1f}%')}")
        remaining = monthly_limit - month_spend_usd
        if remaining > 0:
            print(f"  Remaining:    ${remaining:.4f}")
        else:
            print(f"  {_c('31', f'  {_U.warn} Exceeded by ${abs(remaining):.4f}')}")
    else:
        print(f"  Spent:        ${month_spend_usd:.4f}")
        print(f"  No budget set. Use:  {_c('33', 'tokenstats budget --set 50')}")
    print()


def cmd_report(all_sessions: list[Session], month_str: str):
    # Parse month: "2026-05" or "last"
    if month_str == "last":
        if not all_sessions:
            print(_c("31", "  No sessions."))
            return
        valid = [s.time_created for s in all_sessions if s.time_created]
        if not valid:
            print(_c("31", "  No sessions with timestamps."))
            return
        latest = max(valid)
        dt = datetime.fromtimestamp(latest / 1000, tz=timezone.utc)
        month_str = dt.strftime("%Y-%m")

    try:
        year, month = map(int, month_str.split("-"))
        ms_start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
        if month == 12:
            ms_end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            ms_end = int(datetime(year, month + 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    except (ValueError, AttributeError):
        print(_c("31", f"  Usage: tokenstats report 2026-05  or  tokenstats report last"))
        return

    filtered = [s for s in all_sessions if s.time_created and ms_start <= s.time_created < ms_end]

    if not filtered:
        print(_c("33", f"  No sessions in {month_str}."))
        return

    total_in = sum(s.input_tokens for s in filtered)
    total_out = sum(s.output_tokens for s in filtered)
    total_cost = sum(s.cost for s in filtered)
    total_sessions = len(filtered)

    providers: dict[str, list[Session]] = {}
    projects: dict[str, list[Session]] = {}
    for s in filtered:
        providers.setdefault(s.provider, []).append(s)
        if s.project:
            projects.setdefault(s.project, []).append(s)

    month_name = datetime(year, month, 1).strftime("%B %Y")

    print(f"\n  {_c('1', 'Report')}  {_c('2', month_name)}")
    print(f"  {_U.hline * 70}")

    print(f"  Sessions:     {total_sessions}")
    print(f"  Total in:     {format_num(total_in):>12} tokens")
    print(f"  Total out:    {format_num(total_out):>12} tokens")
    if total_cost:
        print(f"  Total cost:   {dollar_str(total_cost):>12}")
    print(f"  Avg / session: {format_num(total_in // max(total_sessions, 1)):>8} in  "
          f"{format_num(total_out // max(total_sessions, 1)):>8} out")

    # Providers
    if len(providers) > 1:
        print(f"\n  {_c('1', 'By provider')}")
        print(f"  {_U.hline * 70}")
        for pname in sorted(providers):
            ps = providers[pname]
            p_in = sum(s.input_tokens for s in ps)
            p_out = sum(s.output_tokens for s in ps)
            p_cost = sum(s.cost for s in ps)
            print(f"  {pname:<14} {len(ps):>4} sessions  {format_num(p_in):>10} in "
                  f"{format_num(p_out):>10} out  {dollar_str(p_cost)}")

    # Projects
    if projects:
        print(f"\n  {_c('1', 'By project')}")
        print(f"  {_U.hline * 70}")
        for pname in sorted(projects, key=lambda p: len(projects[p]), reverse=True)[:10]:
            ps = projects[pname]
            p_in = sum(s.input_tokens for s in ps)
            p_out = sum(s.output_tokens for s in ps)
            print(f"  {pname:<30} {len(ps):>4} sessions  {format_num(p_in):>10} in "
                  f"{format_num(p_out):>10} out")

    print()


def cmd_shell_integration(powershell: bool = False):
    cmds = [
        ("analyze", "Analyze a session"),
        ("digest", "Usage digest"),
        ("compare", "Compare two sessions"),
        ("trends", "Usage charts"),
        ("report", "Monthly report"),
        ("export", "Export data"),
        ("budget", "Budget tracking"),
        ("search", "Search sessions"),
        ("outliers", "Find anomalies"),
    ]
    if powershell:
        print("# Add to your PowerShell profile ($PROFILE):")
        print()
        for cmd, desc in cmds:
            print(f"function ts-{cmd} {{ tokenstats {cmd} @args }}  # {desc}")
        print()
        print("# Generic shortcut")
        print('function ts { if ($args.Count -eq 0) { tokenstats } else { tokenstats @args } }')
    else:
        print("# Add to ~/.zshrc or ~/.bashrc:")
        print("eval \"$(tokenstats shell-integration)\"")
        print()
        for cmd, desc in cmds:
            print(f"ts-{cmd}() {{ tokenstats {cmd} \"$@\"; }}  # {desc}")
        print()
        print("# Generic shortcut")
        print('ts() { if [ $# -eq 0 ]; then tokenstats; else tokenstats "$@"; fi; }')


def cmd_search(all_sessions: list[Session], query: str):
    query_lower = query.lower()
    matching = [s for s in all_sessions if query_lower in (s.title or "").lower()]

    if not matching:
        print(_c("31", f"{_U.xmark} No sessions matching '{query}'"))
        return []

    print(f"\n  {_c('1', f'Sessions matching {_U.lq}{query}{_U.rq}')}  (found: {len(matching)})\n")
    for i, s in enumerate(matching, 1):
        title = (s.title or "")[:60]
        print(
            f"  {_c('2', f'{str(i):>4}')}  "
            f"{_c('33', f'{s.provider:<8}')} "
            f"{_c('36', f'{s.id[:32]:<32}')} "
            f"{_c('97', f'{title:<60}')} "
            f"in:{format_num(s.input_tokens)} out:{format_num(s.output_tokens)}"
        )
    print()
    print(f"  {_c('2', 'Select: tokenstats <N> or tokenstats ' + matching[0].id)}\n")
    return matching


def print_help():
    print(f"  {_c('1', 'tokenstats — Token usage statistics for AI coding agents')}")
    print()
    print(f"  {_c('36', 'Usage:')}")
    print(f"    tokenstats                                       List all sessions")
    print(f"    tokenstats --provider <name>                     Filter by agent")
    print(f"    tokenstats <N>                                  Session by number")
    print(f"    tokenstats <session_id>                         Session by ID")
    print(f"    tokenstats last                                 Latest session")
    print(f"    tokenstats search <text>                        Search by title")
    print(f"    tokenstats analyze <N|id|last>                  Analysis + tips")
    print(f"    tokenstats compare <A> <B>                      Compare two sessions")
    print(f"    tokenstats trends [--days N]                    Usage charts (default 30d)")
    print(f"    tokenstats digest                               Overall usage digest")
    print(f"    tokenstats report <YYYY-MM>                     Monthly report")
    print(f"    tokenstats outliers                             Find unusual sessions")
    print(f"    tokenstats export --format json|csv             Export all data")
    print(f"    tokenstats budget [--set N]                     Budget tracking")
    print(f"    tokenstats shell-integration                     Generate ts/ts-* shims (bash/zsh)")
    print(f"    tokenstats shell-integration --powershell        Generate ts/ts-* shims (PowerShell)")
    print(f"    tokenstats --list-providers                     Available agents")
    print(f"    tokenstats --help                                This message")
    print()
    print(f"  {_c('36', 'Shell shortcuts:')}")
    print(f"  {_c('33', 'tokenstats shell-integration')}  Generate ts/ts-analyze/ts-digest/...")
    print(f"    eval \"$(tokenstats shell-integration)\"  Activate in shell")
    print(f"    tokenstats shell-integration --powershell  | Add to $PROFILE  (PowerShell)")
    print()
    print(f"  {_c('36', 'Supported agents:')}")
    agents = all_providers()
    for p in agents:
        status = _c("32", _U.check) if p.detect() else _c("2", _U.mdash)
        print(f"  {status} {p.name:<12} {p.display_name}")
    print()
    print(f"  {_c('1', 'Security')}")
    print(f"  {_c('2', '  Zero telemetry. Zero network. Zero data collection.')}")
    print(f"  {_c('2', '  Reads local files only.')}")
    print()


# ─── CLI ────────────────────────────────────────────────────────────────



def main():
    if sys.platform == "win32":
        os.system("")
        sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]

    provider_filter = None
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] in ("--provider", "-p") and i + 1 < len(args):
            provider_filter = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1
    args = filtered_args

    if args and args[0] in ("help", "--help", "-h"):
        print_help()
        return

    if args and args[0] == "--list-providers":
        print()
        for p in all_providers():
            status = _c("32", "detected") if p.detect() else _c("2", "not found")
            print(f"  {p.name:<14} {p.display_name:<14} {status}")
        print()
        return

    no_data_commands = ("digest", "outliers", "--list-providers", "help", "--help", "-h", "export", "budget", "shell-integration")
    if not detect_providers() and args and args[0] not in no_data_commands:
        print(_c("31", f"{_U.xmark} No supported coding agents detected."))
        print("  Checked for: " + ", ".join(p.name for p in all_providers()))
        print("  Use --list-providers or --help for details.")
        sys.exit(1)

    all_sessions = _load_all(provider_filter)

    if not args:
        cmd_list(all_sessions, provider_filter)

    elif args[0] == "analyze":
        if len(args) < 2:
            print(_c("31", f"{_U.xmark} Usage: tokenstats analyze <N|id|last>"))
            sys.exit(1)
        s = _resolve_session(all_sessions, args[1])
        if not s:
            print(_c("31", f"{_U.xmark} Session '{args[1]}' not found."))
            sys.exit(1)
        cmd_analyze(s, all_sessions)

    elif args[0] == "compare" and len(args) >= 3:
        s1 = _resolve_session(all_sessions, args[1])
        s2 = _resolve_session(all_sessions, args[2])
        if not s1 or not s2:
            print(_c("31", f"{_U.xmark} Session not found. Use numbers or IDs."))
            sys.exit(1)
        cmd_compare(s1, s2)

    elif args[0] == "digest":
        cmd_digest(all_sessions)

    elif args[0] == "outliers":
        cmd_outliers(all_sessions)

    elif args[0] == "trends":
        days = 30
        if "--days" in args:
            try:
                idx = args.index("--days")
                days = int(args[idx + 1])
            except (ValueError, IndexError):
                pass
        cmd_trends(all_sessions, days)

    elif args[0] == "report" and len(args) >= 2:
        cmd_report(all_sessions, args[1])

    elif args[0] == "export":
        fmt = "json"
        if "--format" in args:
            try:
                idx = args.index("--format")
                fmt = args[idx + 1]
            except (ValueError, IndexError):
                pass
        cmd_export(all_sessions, fmt)

    elif args[0] == "budget":
        cmd_budget(all_sessions, args[1:])

    elif args[0] == "shell-integration":
        cmd_shell_integration("--powershell" in args)

    elif args[0] == "search" and len(args) >= 2:
        cmd_search(all_sessions, " ".join(args[1:]))

    else:
        s = _resolve_session(all_sessions, args[0])
        if not s:
            print(_c("31", f"{_U.xmark} Session '{args[0]}' not found."))
            print("  Use a number from the list, 'last', or a session ID.")
            sys.exit(1)
        cmd_detail(s)


if __name__ == "__main__":
    main()
