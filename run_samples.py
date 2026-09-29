"""Generate every topic in samples/topics.json and save the outputs exactly as generated.

    python run_samples.py            # uses Gemini -> samples/outputs/
    python run_samples.py --offline  # rules-only baseline -> samples/offline/
    python run_samples.py --fresh    # regenerate topics that already have output

Topics that already have a saved output are skipped, so an interrupted run
(rate limits, an overloaded model) picks up where it stopped. SAMPLES.md is
rebuilt from the saved JSON every time; nothing in it is hand-written.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from scriptbench import Result, generate_detailed
from scriptbench.cli import render
from scriptbench.llm import LLMError

ROOT = Path(__file__).parent


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    topics = json.loads((ROOT / "samples" / "topics.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "samples" / ("offline" if args.offline else "outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for index, spec in enumerate(topics, start=1):
        path = out_dir / f"{index:02d}-{slug(spec['niche'])}-{spec['target_seconds']}s.json"
        paths.append(path)
        if path.exists() and not args.fresh:
            print(f"[{index}/{len(topics)}] already generated, skipping ({path.name})", file=sys.stderr)
            continue

        print(f"[{index}/{len(topics)}] {spec['niche']}: {spec['topic']} ({spec['target_seconds']}s)", file=sys.stderr)
        try:
            result = generate_detailed(spec["niche"], spec["topic"], spec["target_seconds"], offline=args.offline)
        except LLMError as err:
            print(f"error: {err}\nRerun to continue from this topic.", file=sys.stderr)
            return 1
        if not args.offline and result.meta["engine"] == "templates":
            print("error: no API key found. Set GEMINI_API_KEY or GROQ_API_KEY, or pass --offline.", file=sys.stderr)
            return 1

        record = {
            "input": spec,
            **result.script,
            "meta": {**result.meta, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_report(out_dir, paths)
    print(f"Wrote {len(paths)} scripts to {out_dir}", file=sys.stderr)
    return 0


def write_report(out_dir: Path, paths: list[Path]) -> None:
    report = ["# Sample outputs", "", "Printed exactly as the generator returned them, with no edits.", ""]
    for index, path in enumerate(paths, start=1):
        record = json.loads(path.read_text(encoding="utf-8"))
        spec = record["input"]
        result = Result(record["hook"], record["body"], record["cta"], record["meta"])
        report += [
            f"## {index}. {spec['niche']} | {spec['target_seconds']}s",
            "",
            f"**Topic:** {spec['topic']}",
            "",
            "```text",
            render(result),
            "```",
            "",
        ]
    (out_dir / "SAMPLES.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
