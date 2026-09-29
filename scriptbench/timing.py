"""Turn a runtime into a word budget.

A script is performed, not read, so length is measured in *spoken* seconds.
Everything downstream (prompts, the critic, the CLI) works from the Budget
produced here, so "45 seconds" means the same thing everywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ~150 words per minute: brisk, clear on-camera delivery. Fast talkers run
# closer to 170 wpm; pass wps=2.8 if that's your creator.
DEFAULT_WPS = 2.5

# The hook has to land before the viewer decides to swipe. At 2.5 wps,
# 14 words is ~5.5s; the prompt aims lower (~10 words, ~4s).
HOOK_MAX_WORDS = 14
HOOK_MIN_WORDS = 4
HOOK_TYPICAL_WORDS = 10

MIN_SECONDS = 10
MAX_SECONDS = 180  # beyond this it isn't short-form any more

_TOKEN = re.compile(r"\S+")
_HAS_ALNUM = re.compile(r"[A-Za-z0-9]")
_HAS_DIGIT = re.compile(r"\d")


def spoken_words(text: str) -> int:
    """Count words as they'll be *said*.

    "$1,200" or "8,000" takes several words to say, so any token containing
    a digit counts as two. Lone punctuation (dashes, ellipses) counts as zero.
    """
    count = 0
    for token in _TOKEN.findall(text):
        if not _HAS_ALNUM.search(token):
            continue
        count += 2 if _HAS_DIGIT.search(token) else 1
    return count


def spoken_seconds(text: str, wps: float = DEFAULT_WPS) -> float:
    return spoken_words(text) / wps


@dataclass(frozen=True)
class Budget:
    target_seconds: int
    wps: float
    total_words: int
    hook_max: int
    body_words: int
    cta_words: int
    beats: int
    tolerance: float = 0.12  # +/-12%: a 45s target accepts ~40-50s

    @property
    def min_seconds(self) -> float:
        return self.target_seconds * (1 - self.tolerance)

    @property
    def max_seconds(self) -> float:
        return self.target_seconds * (1 + self.tolerance)


def plan_budget(target_seconds: int, wps: float = DEFAULT_WPS) -> Budget:
    if not MIN_SECONDS <= target_seconds <= MAX_SECONDS:
        raise ValueError(
            f"target_seconds must be between {MIN_SECONDS} and {MAX_SECONDS}, got {target_seconds}"
        )
    if wps <= 0:
        raise ValueError("wps must be positive")

    total = round(target_seconds * wps)
    # One clear ask takes 8-18 words; ~12% of the runtime.
    cta = max(8, min(18, round(total * 0.12)))
    body = total - HOOK_TYPICAL_WORDS - cta
    # Roughly one new idea every ~15 seconds, plus the payoff beat:
    # 30s -> 3 beats, 45s -> 4, 60s -> 5.
    beats = max(2, min(6, round(target_seconds / 15) + 1))

    return Budget(
        target_seconds=target_seconds,
        wps=wps,
        total_words=total,
        hook_max=HOOK_MAX_WORDS,
        body_words=body,
        cta_words=cta,
        beats=beats,
    )
