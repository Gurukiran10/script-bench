"""Prompts and response schemas.

The draft prompt makes the model commit to an *angle* (the one payoff) before
writing anything else. Hooks, body and CTA all hang off that angle, which is
what keeps the hook's promise and the body's delivery in sync.
"""
from __future__ import annotations

import json

from .hooks import ARCHETYPES
from .timing import Budget

SYSTEM = """You write short-form video scripts (TikTok, Reels, Shorts) that the creator reads aloud to camera.

Write for the ear, not the page:
- Short sentences. One idea per sentence. Use contractions. Plain words.
- Concrete beats abstract: a number, a name, a specific moment or object beats any adjective.
- Every sentence earns the next one. Cut anything that only restates.
- No greetings, no "in this video", no "let's dive in", no hashtags, emojis, labels, brackets or stage directions.
- The body must deliver exactly what the hook promises, and deliver it early.
- Use the creator's voice: first person if the topic is their own story, otherwise talk straight to "you".
- Never present invented statistics or studies as fact. If you add a specific number that is illustrative, \
or a personal detail the creator didn't give you, list it under "verify" so they can swap in the real one."""

DRAFT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "angle": {"type": "STRING"},
        "hooks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"style": {"type": "STRING"}, "text": {"type": "STRING"}},
                "required": ["style", "text"],
            },
        },
        "body_beats": {"type": "ARRAY", "items": {"type": "STRING"}},
        "cta": {"type": "STRING"},
        "verify": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["angle", "hooks", "body_beats", "cta", "verify"],
    "propertyOrdering": ["angle", "hooks", "body_beats", "cta", "verify"],
}

REVISE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "hook": {"type": "STRING"},
        "body": {"type": "STRING"},
        "cta": {"type": "STRING"},
        "verify": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["hook", "body", "cta", "verify"],
    "propertyOrdering": ["hook", "body", "cta", "verify"],
}


def draft_prompt(niche: str, topic: str, budget: Budget, archetypes: list[str]) -> str:
    styles = "\n".join(f'   - "{name}": {ARCHETYPES[name]}' for name in archetypes)
    return f"""Niche: {niche}
Topic: {topic}
Runtime: {budget.target_seconds} seconds spoken, about {budget.total_words} words in total.

1. angle: one sentence. The single payoff the viewer walks away with. Not a summary of the topic; \
the surprising or useful thing inside it.

2. hooks: exactly {len(archetypes)} opening lines, one in each style below. Each is at most \
{budget.hook_max} words and lands in about 4 seconds. All of them promise the same angle, so any one \
can open the same body.
{styles}

3. body_beats: exactly {budget.beats} beats, about {budget.body_words} words in total.
   - Only ONE of the hooks will be used, and you don't know which. The body must read naturally after \
any of them: beat 1 must stand on its own, never continuing a specific hook's sentence or pointing back \
to it ("they", "that", "this is why").
   - Beat 1 pays off the promise straight away. No warm-up, no restating the hook.
   - Every specific a hook names (a count, a price, a timeframe) must be true of the body.
   - Each beat adds one new thing: a step, a proof, an example, a turn.
   - The last beat lands the takeaway in one line someone would repeat to a friend.

4. cta: one ask, about {budget.cta_words} words, that grows out of this specific video \
(for example: comment a specific answer, save it for a specific moment, or follow for a specific next part). \
Never "like and subscribe".

5. verify: specific numbers or claims the creator should confirm before filming. Empty if none."""


def revise_prompt(niche: str, topic: str, budget: Budget, script: dict[str, str],
                  problems: list[str], current_words: int) -> str:
    bullet_list = "\n".join(f"- {p}" for p in problems)
    return f"""Niche: {niche}
Topic: {topic}
Runtime: {budget.target_seconds} seconds, about {budget.total_words} spoken words. \
The current draft is {current_words} spoken words.

Fix every problem below. Keep the hook's promise, the angle and anything that already works. \
Change only what the fixes need.

Problems:
{bullet_list}

Limits: hook at most {budget.hook_max} words; body about {budget.body_words} words with a blank line \
between beats; cta about {budget.cta_words} words with a single ask.

Current script:
{json.dumps(script, indent=2, ensure_ascii=False)}"""
