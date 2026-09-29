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
| 2 fitness | "Three ten-minute walks" is ~3,000 steps, not 8,000. "Metabolism into a deep freeze", "HIIT makes you crash and crave sugar" and "fat-burning enzymes turned on all day" are not overstatements. They're wrong. I wouldn't let a creator film this as written. | It's flagged in `verify`, but a script with false claims still passes every rule. |
| 3 cooking | The hook says "three-ingredient", but the body uses spaghetti, garlic, olive oil and chilli flakes. That hook won 108–104 purely on the ranker's +8 bonus for containing a number. The runner-up ("You are pouring your best pasta ingredient straight down the kitchen sink drain") was *true* to the body, which is about pasta water. | **My ranker caused this.** It rewarded "has a number" without knowing whether the number was right. |
| 4 careers | The body opens "They care about…" with nothing for "they" to refer to. That line continues a *rejected* hook ("Your senior developers do not care how clean your code is"). The model wrote the body to follow that hook, and my ranker then picked a different one. The verify list also includes "fourteen months", which the creator gave us. | **My pipeline caused this.** The body is written once, but the hook is chosen afterwards, and nothing guaranteed the body worked after every hook. |
| 5 travel | The hook promises $99/day, but the body never adds the costs up to show it. | Same hook→body promise gap as #3. |
| 6 study | Solid. The critic's only complaint (no number in the body) is arguably wrong here: a number would be padding. | The "add a specific number" rule is a heuristic, which is why it's *soft*. |

## What this tells me

1. **Two of the six failures were caused by my own design, not the model** (#3, #4). Choosing the hook *after* the body is written only works if the body fits every hook. A ranker that rewards "has a number" will pick a wrong number over a true statement.
2. **The rules work as a floor, not a ceiling.** They reliably stop bad formats (wrong length, warm-ups, multiple asks, stage directions). They say nothing about whether the script is *true* or *coherent*.
3. **Hook-promise drift** (#3, #5) is the biggest remaining failure. The next thing I'd build is one extra LLM check: "Does the body deliver exactly what the hook promises? Quote the line that does." Its answer would be fed into the same revision loop.
4. **Consistency checks on numbers** (#1, #2) come next. The model already lists its numbers under `verify`, so a follow-up pass could check whether they're consistent with each other.

## What I changed after this review

- **The body must work after any of the three hooks.** The draft prompt now says only one hook will be used, so beat 1 must stand on its own and never continue or point back to a specific hook. It also says every specific a hook names must be true of the body. This fixes the cause of #4.
- **The number bonus is now a nudge, not a trump card** (+8 → +3). Re-scoring the saved cooking candidates with the new weights, the true "pasta water" hook wins over the false "three-ingredient" one. This fixes the cause of #3.

I've left the outputs above unedited and haven't regenerated them. The brief asked for outputs exactly as generated, and they're the evidence for these changes. A fresh run (`python run_samples.py --fresh`) uses the fixed pipeline.
