"""The pipeline: plan -> draft -> pick hook -> critique -> revise -> best.

    plan      code:  runtime -> word budget, beat count, hook styles
    draft     LLM:   angle, 3 hooks (one per style), body beats, CTA
    pick      code:  rank the hooks, keep the best
    critique  code:  timing, hook rules, one-ask CTA, cliches, read-aloud hazards
    revise    LLM:   fix only the listed problems (at most `max_revisions` times)
    best      code:  return the highest-scoring version seen
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import critic, prompts
from .hooks import choose_archetypes, is_story, rank_hooks
from .llm import JSONModel, client_from_env
from .templates import draft_offline
from .timing import DEFAULT_WPS, Budget, plan_budget, spoken_seconds, spoken_words


@dataclass
class Result:
    hook: str
    body: str
    cta: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def script(self) -> dict[str, str]:
        return {"hook": self.hook, "body": self.body, "cta": self.cta}


def generate(niche: str, topic: str, target_seconds: int, **options: Any) -> dict[str, str]:
    """The brief's interface: returns {"hook", "body", "cta"}."""
    return generate_detailed(niche, topic, target_seconds, **options).script


def generate_detailed(
    niche: str,
    topic: str,
    target_seconds: int,
    *,
    wps: float = DEFAULT_WPS,
    offline: bool = False,
    client: JSONModel | None = None,
    max_revisions: int = 2,
) -> Result:
    niche, topic = niche.strip(), topic.strip()
    if not niche or not topic:
        raise ValueError("niche and topic must not be empty")
    budget = plan_budget(int(target_seconds), wps)

    if client is None and not offline:
        client = client_from_env()
    if client is None:
        script = draft_offline(niche, topic, budget)
        return _result(script, budget, engine="templates", issues=critic.lint(script, budget))

    return _generate_with_llm(niche, topic, budget, client, max_revisions)


def _generate_with_llm(niche: str, topic: str, budget: Budget, client: JSONModel, max_revisions: int) -> Result:
    story = is_story(topic)
    archetypes = choose_archetypes(topic)

    draft = client.generate_json(
        prompts.SYSTEM, prompts.draft_prompt(niche, topic, budget, archetypes), prompts.DRAFT_SCHEMA, temperature=0.9
    )
    candidates = [
        {"style": h.get("style", ""), "text": _clean(h.get("text", ""))}
        for h in draft.get("hooks", [])
        if _clean(h.get("text", ""))
    ]
    if not candidates:
        raise ValueError("The model returned no usable hooks")
    ranked = rank_hooks(candidates, budget, story)

    script = {
        "hook": ranked[0].text,
        "body": "\n\n".join(_clean(b) for b in draft.get("body_beats", []) if _clean(b)),
        "cta": _clean(draft.get("cta", "")),
    }
    verify = list(draft.get("verify", []))

    # Every version is kept; the best one wins, so a revision can never make
    # the output worse than the draft.
    attempts = [(script, verify, critic.lint(script, budget))]
    while critic.has_hard(attempts[-1][2]) and len(attempts) <= max_revisions:
        current, _, issues = attempts[-1]
        revised = client.generate_json(
            prompts.SYSTEM,
            prompts.revise_prompt(
                niche, topic, budget, current,
                problems=[i.message for i in issues],
                current_words=spoken_words(" ".join(current.values())),
            ),
            prompts.REVISE_SCHEMA,
            temperature=0.4,
        )
        new_script = {key: _clean(revised.get(key, "")) or current[key] for key in ("hook", "body", "cta")}
        new_verify = list(revised.get("verify", verify))
        attempts.append((new_script, new_verify, critic.lint(new_script, budget)))

    best_index = max(range(len(attempts)), key=lambda i: (critic.score(attempts[i][2]), i))
    best_script, best_verify, best_issues = attempts[best_index]

    return _result(
        best_script,
        budget,
        engine=client.model,
        issues=best_issues,
        angle=_clean(draft.get("angle", "")),
        hook_style=ranked[0].style if best_script["hook"] == ranked[0].text else "revised",
        hook_candidates=[
            {"style": h.style, "text": h.text, "score": h.score, "reasons": list(h.reasons)} for h in ranked
        ],
        revisions=len(attempts) - 1,
        chosen_version=best_index,
        version_scores=[critic.score(a[2]) for a in attempts],
        verify=best_verify,
    )


def _result(script: dict[str, str], budget: Budget, *, engine: str, issues: list[critic.Issue], **extra: Any) -> Result:
    full = " ".join(script.values())
    meta: dict[str, Any] = {
        "engine": engine,
        "target_seconds": budget.target_seconds,
        "estimated_seconds": round(spoken_seconds(full, budget.wps), 1),
        "spoken_words": spoken_words(full),
        "section_seconds": {k: round(spoken_seconds(v, budget.wps), 1) for k, v in script.items()},
        "budget": asdict(budget),
        "score": critic.score(issues),
        "issues": [asdict(i) for i in issues],
        **extra,
    }
    return Result(script["hook"], script["body"], script["cta"], meta)


_LABEL = re.compile(r"^\s*(hook|body|cta|beat \d+)\s*:\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    """Strip labels and wrapping quotes the model sometimes adds; normalise spacing within lines."""
    text = _LABEL.sub("", (text or "").strip())
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1]
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    return "\n\n".join(p for p in paragraphs if p)
