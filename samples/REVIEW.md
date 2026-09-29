# Reviewing my own samples

The outputs in [`outputs/SAMPLES.md`](outputs/SAMPLES.md) are unedited. This is my read of them *after* generation: what works, what doesn't, and what that says about the generator.

## What worked

- **Timing.** All six land within ±12% of target (29.6s–62s against 30–60s targets). Two needed a revision to get there (fitness, travel), which is the critique loop doing its job.
- **Hooks fit the topic.** First-person stories got *specific result* hooks ("…found five-thousand dollars"). Explainers got *mistake* hooks ("Stop rereading your notes…"). None opened with a greeting.
- **CTAs make one ask, tied to the video.** "Comment your average daily step count", "Save this for the next night you look at an empty fridge". None of them say "like and subscribe".
- **The verify list earned its place.** The travel script flagged every price it quoted. The fitness script flagged its own shakiest claim (fat-burning enzymes). That's the list a creator needs before filming.

## What's wrong (and the critic scored most of it 100/100)

| # | Problem | Why the rules missed it |
|---|---|---|
| 1 finance | $50/week × 104 weeks is exactly $5,200, so the "high-yield" account earned nothing. The CTA also promises a setup guide the creator may not have. | Rules can't do arithmetic on claims or know what the creator can deliver. |
| 2 fitness | "Three ten-minute walks" is ~3,000 steps, not 8,000. "HIIT makes you crash and crave sugar" is overstated. | It's flagged in `verify`, but a script with a wrong number still passes. |
| 3 cooking | The hook says "three-ingredient", but the body uses spaghetti, garlic, olive oil and chilli flakes. | The hook's promise and the body's delivery are only checked by the prompt, never by code. |
| 4 careers | The body opens "They care about…" with no antecedent. The first sentence of beat 1 got lost. The verify list includes "fourteen months", which the creator gave us. | Coherence across sentences is invisible to regex checks. |
| 5 travel | The hook promises $99/day, but the body never adds the costs up to show it. | Same hook→body promise gap as #3. |
| 6 study | Solid. The critic's only complaint (no number in the body) is arguably wrong here: a number would be padding. | The "add a specific number" rule is a heuristic, which is why it's *soft*. |

## What this tells me

1. **The rules work as a floor, not a ceiling.** They reliably stop bad formats (wrong length, warm-ups, multiple asks, stage directions). They say nothing about whether the script is *true* or *coherent*.
2. **The biggest remaining failure is hook-promise drift** (#3, #5). The angle-first prompt reduced it but didn't eliminate it. The next thing I'd build is one extra LLM check: "Does the body deliver exactly what the hook promises? Quote the line that does." Its answer would be fed into the same revision loop.
3. **Consistency checks on numbers** (#1, #2) are the second priority. The model already lists its numbers under `verify`, so a follow-up pass could check whether they're consistent with each other.

I've left all of these in the outputs on purpose. The brief asked for unedited outputs, and they're more useful as evidence than hidden.
