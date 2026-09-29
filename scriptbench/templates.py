"""Offline fallback: a rules-only script when no API key is set.

This exists so the tool always runs and so there's a baseline to compare
against. It gets structure and timing right, but it can't invent the specific
details that make a script good. Seeing that gap side by side is the argument
for putting the LLM in the loop.
"""
from __future__ import annotations

from .hooks import is_story
from .timing import Budget, spoken_words

_STORY_BEATS = [
    "Here's the setup. I didn't plan anything clever. I made one decision and then left it alone.",
    "The first few weeks felt like nothing was happening. That's the part where most people quit.",
    "Then the results started to compound, and I finally understood why the boring version works.",
    "The mistake I almost made was checking on it every day and tweaking it. Doing less was the whole trick.",
    "If I started again tomorrow, I'd do exactly the same thing, just sooner.",
    "So here's the lesson: set it up once, make it automatic, and get out of your own way.",
]

_EXPLAINER_BEATS = [
    "Here's what's actually going on. The obvious approach feels productive, but it's working against you.",
    "Step one: pick the smallest version of this you can do today. Not the perfect version, the smallest one.",
    "Step two: make it the default, so you don't need willpower to keep doing it.",
    "Step three: measure one thing for two weeks. Just one. That's how you know it's working.",
    "Most people skip that last step, and that's exactly why they give up too early.",
    "Do the simple thing consistently, and it beats the clever thing done once.",
]


def draft_offline(niche: str, topic: str, budget: Budget) -> dict[str, str]:
    subject = topic.strip().rstrip(".!?")
    subject = subject[0].upper() + subject[1:]
    story = is_story(topic)

    if story:
        hook = f"{subject}. Here's what happened."
        cta = f"Follow if you want the next part of this {niche} story."
        beats = _STORY_BEATS
    else:
        hook = f"Most people get this part of {niche} wrong."
        cta = f"Save this for the next time you're stuck on {niche}."
        beats = [f"{subject}.", *_EXPLAINER_BEATS]

    # Keep the payoff line last, then fill from the front until the word budget is used.
    payoff = beats[-1]
    chosen: list[str] = []
    used = spoken_words(payoff)
    for beat in beats[:-1]:
        if used >= budget.body_words:
            break
        chosen.append(beat)
        used += spoken_words(beat)
    chosen.append(payoff)

    return {"hook": hook, "body": "\n\n".join(chosen), "cta": cta}
