"""Deterministic checks on a script.

The LLM is good at voice and bad at counting, and it drifts toward the same
tired phrases. These checks catch what a rule *can* catch reliably. Each issue's
message is written as an instruction, because it's fed straight back to the
model in the revision step.

"hard" issues trigger a revision. "soft" issues are reported and cost score
points, but don't force a rewrite on their own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .timing import HOOK_MIN_WORDS, Budget, spoken_seconds, spoken_words

HARD = "hard"
SOFT = "soft"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str


_I = re.IGNORECASE

# Openers that spend the most valuable seconds of the video saying nothing.
_WARMUP = re.compile(
    r"^\W*(hey|hi|hello|yo|what'?s up|welcome|so,|so today|today,? (i|we)|okay,? so|in this video)\b", _I
)
# Questions the viewer can answer "no" to and swipe.
_GENERIC_QUESTION = re.compile(
    r"^\W*(did you know|have you ever|are you (tired|struggling)|ever wonder(ed)?|want to know)\b", _I
)

# (pattern, severity). Hard = ruins the script; soft = sounds machine-written.
_CLICHES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, _I), sev)
    for p, sev in [
        (r"\bin (this|today'?s) video\b", HARD),
        (r"\blike and subscribe\b", HARD),
        (r"\bsmash (that|the)\b", HARD),
        (r"\blet'?s (dive|jump|get) in(to)?\b", HARD),
        (r"\bwithout further ado\b", HARD),
        (r"\byou won'?t believe\b", HARD),
        (r"\bdive (deep )?into\b", SOFT),
        (r"\bgame[- ]?changer\b", SOFT),
        (r"\bunlock(s|ing)?\b", SOFT),
        (r"\bdelve\b", SOFT),
        (r"\bbuckle up\b", SOFT),
        (r"\blook no further\b", SOFT),
        (r"\bit'?s no secret\b", SOFT),
        (r"\bstop scrolling\b", SOFT),
        (r"\blevel up\b", SOFT),
        (r"\bhere'?s the kicker\b", SOFT),
        (r"\bin today'?s .{0,15}world\b", SOFT),
        (r"\bsupercharge\b", SOFT),
        (r"\bthe power of\b", SOFT),
        (r"\bjourney\b", SOFT),
    ]
]

# Things that would be read aloud by accident.
_STAGE_DIRECTION = re.compile(
    r"\[[^\]]*\]"
    r"|\([^)]*\b(b-?roll|cut to|music|pause|beat|cue|scene|on[- ]screen)\b[^)]*\)"
    r"|^\s*(hook|body|cta|beat \d+|intro|outro)\s*:",
    _I | re.MULTILINE,
)
_HASHTAG = re.compile(r"(?<!\w)#[A-Za-z]\w*")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")

_ASK_VERBS = re.compile(
    r"\b(follow|like|subscribe|comment|share|save|click|tap|link in (my )?bio|dm|download|sign up|join)\b",
    _I,
)

_NUMBER = re.compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|"
    r"forty|fifty|hundred|thousand|million|half|double|twice|triple)\b",
    _I,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
LONG_SENTENCE_WORDS = 25


def has_specific(text: str) -> bool:
    return bool(_NUMBER.search(text))


def lint_hook(hook: str, budget: Budget) -> list[Issue]:
    issues: list[Issue] = []
    words = spoken_words(hook)
    if words > budget.hook_max:
        issues.append(Issue("hook_long", HARD,
            f"The hook is {words} words. Cut it to {budget.hook_max} or fewer so it lands in about 4 seconds."))
    if words < HOOK_MIN_WORDS:
        issues.append(Issue("hook_short", HARD,
            "The hook is too short to promise anything. Make it one full, specific line."))
    if _WARMUP.search(hook):
        issues.append(Issue("hook_warmup", HARD,
            "The hook opens with a greeting or warm-up. Start on the claim, result or moment itself."))
    if _GENERIC_QUESTION.search(hook):
        issues.append(Issue("hook_generic_question", SOFT,
            "The hook is a generic question the viewer can answer 'no' to. Make it a specific statement."))
    if len([s for s in _SENTENCE_SPLIT.split(hook.strip()) if s]) > 2:
        issues.append(Issue("hook_multi", SOFT,
            "The hook has more than two sentences. Keep it to one or two short lines."))
    return issues


def lint(script: dict[str, str], budget: Budget) -> list[Issue]:
    hook, body, cta = script["hook"], script["body"], script["cta"]
    issues = lint_hook(hook, budget)

    full = f"{hook} {body} {cta}"
    seconds = spoken_seconds(full, budget.wps)
    words = spoken_words(full)
    if seconds > budget.max_seconds:
        cut = words - budget.total_words
        issues.append(Issue("too_long", HARD,
            f"The script runs about {seconds:.0f}s ({words} spoken words) against a {budget.target_seconds}s target. "
            f"Cut about {cut} words, mostly from the body, without dropping any beat's point."))
    elif seconds < budget.min_seconds:
        add = budget.total_words - words
        issues.append(Issue("too_short", HARD,
            f"The script runs about {seconds:.0f}s ({words} spoken words) against a {budget.target_seconds}s target. "
            f"Add about {add} words to the body: a concrete example or detail, not filler."))

    asks = {m.group(0).lower() for m in _ASK_VERBS.finditer(cta)}
    if len(asks) > 1:
        issues.append(Issue("cta_multi_ask", HARD,
            f"The CTA asks for several things ({', '.join(sorted(asks))}). Pick the one ask that fits this video."))
    if spoken_words(cta) > budget.cta_words + 8:
        issues.append(Issue("cta_long", SOFT,
            f"The CTA is long. Keep it to about {budget.cta_words} words."))

    for pattern, severity in _CLICHES:
        match = pattern.search(full)
        if match:
            issues.append(Issue("cliche", severity,
                f'Replace the stock phrase "{match.group(0)}" with plain, specific wording.'))

    if _STAGE_DIRECTION.search(full):
        issues.append(Issue("stage_direction", HARD,
            "Remove labels, brackets and stage directions. Every word will be read aloud."))
    if _HASHTAG.search(full) or _EMOJI.search(full):
        issues.append(Issue("hashtag_emoji", HARD,
            "Remove hashtags and emojis. This is spoken, not captioned."))

    for sentence in _SENTENCE_SPLIT.split(full):
        if spoken_words(sentence) > LONG_SENTENCE_WORDS:
            start = " ".join(sentence.split()[:6])
            issues.append(Issue("long_sentence", SOFT,
                f'The sentence starting "{start}..." is too long to say in one breath. Split it.'))
            break

    if not has_specific(body):
        issues.append(Issue("body_vague", SOFT,
            "The body has no concrete number or quantity. Add one specific detail the viewer can picture."))

    if _normalise(hook) and _normalise(hook) in _normalise(body):
        issues.append(Issue("hook_repeated", SOFT,
            "The body repeats the hook word for word. Move forward instead of restating."))

    return issues


def score(issues: list[Issue]) -> int:
    hard = sum(1 for i in issues if i.severity == HARD)
    soft = len(issues) - hard
    return max(0, 100 - 20 * hard - 5 * soft)


def has_hard(issues: list[Issue]) -> bool:
    return any(i.severity == HARD for i in issues)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
