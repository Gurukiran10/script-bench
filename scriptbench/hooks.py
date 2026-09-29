"""Hook strategy: pick which kinds of hooks to try, then pick the best one.

A single hook from an LLM tends toward the safe middle. Asking for three
hooks in *deliberately different* styles, all promising the same payoff, gives
the ranker real alternatives. The ranker is a filter, not a judge of taste: it
throws out hooks that break the rules and prefers short, specific, personal
ones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .critic import HARD, has_specific, lint_hook
from .timing import Budget, spoken_words

ARCHETYPES: dict[str, str] = {
    "in_media_res": "Drop into the most tense or surprising moment of the story, mid-action. No setup.",
    "specific_result": "Lead with the concrete outcome: a number, a before/after, or a timeframe.",
    "bold_claim": "A confident claim that contradicts what this viewer currently believes.",
    "mistake": "Name a mistake this exact viewer is probably making right now.",
    "curiosity_gap": "Open one specific question that only this video answers. Never 'you won't believe'.",
    "direct_callout": "Name the exact viewer by their situation in the first few words.",
}

# First-person topics are the creator's own story.
_STORY = re.compile(r"\b(I|I'm|I've|I'd|my|me|we|our)\b")
_EXPLAINER = re.compile(
    r"^\s*(how|why|what|when|the (one|best|worst|real|only))\b"
    r"|\b(ways?|tips?|steps?|mistakes?|habits?|rules?|using only|under \$?\d)\b",
    re.IGNORECASE,
)


def is_story(topic: str) -> bool:
    return bool(_STORY.search(topic))


def choose_archetypes(topic: str) -> list[str]:
    """Three hook styles that suit the topic's shape."""
    if is_story(topic):
        return ["in_media_res", "specific_result", "bold_claim"]
    if _EXPLAINER.search(topic):
        return ["mistake", "bold_claim", "curiosity_gap"]
    return ["bold_claim", "curiosity_gap", "direct_callout"]


@dataclass(frozen=True)
class RankedHook:
    text: str
    style: str
    score: float
    reasons: tuple[str, ...]


def score_hook(text: str, budget: Budget, story: bool) -> RankedHook:
    reasons: list[str] = []
    points = 100.0
    for issue in lint_hook(text, budget):
        points -= 20 if issue.severity == HARD else 5
        reasons.append(f"-{issue.code}")

    if has_specific(text):
        points += 8
        reasons.append("+specific")
    # The story hooks should sound like the creator, the explainer hooks
    # should talk to the viewer.
    if story and re.search(r"\b(I|I'm|I've|my|me)\b", text):
        points += 4
        reasons.append("+first_person")
    elif not story and re.search(r"\byou(r|'re)?\b", text, re.IGNORECASE):
        points += 4
        reasons.append("+direct_address")
    if spoken_words(text) <= 10:
        points += 4
        reasons.append("+short")
    # Statements usually hit harder than questions: a question invites "no".
    if text.rstrip().endswith("?"):
        points -= 2
        reasons.append("-question")

    return RankedHook(text=text, style="", score=points, reasons=tuple(reasons))


def rank_hooks(candidates: list[dict[str, str]], budget: Budget, story: bool) -> list[RankedHook]:
    """Best first. Ties keep the model's original order."""
    ranked = []
    for candidate in candidates:
        scored = score_hook(candidate["text"], budget, story)
        ranked.append(RankedHook(candidate["text"], candidate.get("style", ""), scored.score, scored.reasons))
    return sorted(ranked, key=lambda h: -h.score)
