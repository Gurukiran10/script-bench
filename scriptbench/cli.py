"""Command line: python -m scriptbench --niche ... --topic ... --seconds 45"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap

from .generator import Result, generate_detailed
from .llm import LLMError
from .timing import DEFAULT_WPS


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # model output has curly quotes and dashes

    parser = argparse.ArgumentParser(prog="scriptbench", description="Turn an idea into a short-form video script.")
    parser.add_argument("--niche", required=True, help='creator\'s subject, e.g. "personal finance"')
    parser.add_argument("--topic", required=True, help="one sentence on what this video is about")
    parser.add_argument("--seconds", type=int, required=True, help="target spoken runtime, e.g. 30, 45, 60")
    parser.add_argument("--wps", type=float, default=DEFAULT_WPS, help=f"speaking rate in words/sec (default {DEFAULT_WPS})")
    parser.add_argument("--offline", action="store_true", help="skip the LLM and use the rules-only fallback")
    parser.add_argument("--json", action="store_true", help='print {"hook", "body", "cta"} as JSON')
    parser.add_argument("--verbose", action="store_true", help="with --json, include the diagnostics")
    args = parser.parse_args(argv)

    try:
        result = generate_detailed(args.niche, args.topic, args.seconds, wps=args.wps, offline=args.offline)
    except (LLMError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    if result.meta["engine"] == "templates" and not args.offline:
        print("note: no API key found (GEMINI_API_KEY or GROQ_API_KEY), so this used the rules-only fallback.", file=sys.stderr)

    if args.json:
        payload = {**result.script, "meta": result.meta} if args.verbose else result.script
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render(result))
    return 0


def render(result: Result) -> str:
    meta = result.meta
    secs = meta["section_seconds"]
    lines: list[str] = []
    for label, key in (("HOOK", "hook"), ("BODY", "body"), ("CTA", "cta")):
        lines.append(f"{label}  (~{secs[key]:.0f}s)")
        for paragraph in getattr(result, key).split("\n\n"):
            lines.append(textwrap.fill(paragraph, width=78, initial_indent="  ", subsequent_indent="  "))
            lines.append("")
    lines.append("-" * 78)
    summary = f"~{meta['estimated_seconds']:.0f}s spoken (target {meta['target_seconds']}s) | engine: {meta['engine']}"
    if "revisions" in meta:
        summary += f" | revisions: {meta['revisions']}"
    summary += f" | score: {meta['score']}/100"
    lines.append(summary)
    if meta.get("hook_style"):
        lines.append(f"hook style: {meta['hook_style']}")
    for issue in meta["issues"]:
        lines.append(f"  [{issue['severity']}] {issue['message']}")
    if meta.get("verify"):
        lines.append("check before filming:")
        lines.extend(f"  - {item}" for item in meta["verify"])
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
