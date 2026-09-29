# Script Bench

Turns an idea into a short-form video script (hook, body, CTA) timed to a runtime a creator actually wants to film.

```python
>>> from scriptbench import generate
>>> generate(niche="personal finance",
...          topic="I automated my savings and forgot about it for two years",
...          target_seconds=45)
{"hook": "...", "body": "...", "cta": "..."}
```

## Approach: the LLM writes, code decides

A language model writes better sentences than any template I could build. But it can't count, it slides toward the same stock phrases ("let's dive in", "game-changer"), and when you ask for one hook it gives you the safe, average one. So the model does the writing and plain code does the parts that need to be reliable:

```
plan      code   runtime -> spoken word budget, beat count, 3 hook styles that fit the topic
draft     LLM    angle (the one payoff), 3 hooks (one per style), body beats, CTA, facts to verify
pick      code   score the hooks, keep the best
critique  code   timing, hook rules, single-ask CTA, cliches, anything that can't be read aloud
revise    LLM    fix only the listed problems (at most 2 rounds)
best      code   return the highest-scoring version seen, so a revision can never make it worse
```

**1. Time is a word budget.** A script is spoken, so "45 seconds" becomes about 112 words at 2.5 words/sec (~150 wpm, brisk on-camera delivery). Numbers count double because "$1,200" takes several words to say. The budget sets how many words the hook, body and CTA get and how many beats the body has (30s → 3 beats, 60s → 5). The finished script has to land within ±12% of the target. See [`timing.py`](scriptbench/timing.py).

**2. Angle first.** Before writing anything, the model has to state the angle: the single payoff the viewer walks away with. The hooks, body and CTA are all written around that one sentence. This is what stops the usual failure where the hook promises one thing and the body delivers another.

**3. Three hooks in different styles, then choose.** The topic's shape decides which styles to try. A first-person story ("I automated my savings…") gets *in media res*, *specific result* and *bold claim*. An explainer ("Why rereading is the worst…") gets *mistake*, *bold claim* and *curiosity gap*. A ranker heavily penalises hooks that break the rules (too long, opens with "Hey guys") and mildly prefers short, specific hooks that sound like the creator or speak to the viewer. Because the hook is chosen *after* the body is written, the prompt requires a body that reads naturally after any of the three hooks. The samples taught me that the hard way; see [`samples/REVIEW.md`](samples/REVIEW.md). See [`hooks.py`](scriptbench/hooks.py).

**4. A critic that talks back.** [`critic.py`](scriptbench/critic.py) checks what a rule can check reliably: runtime, hook length, warm-up openers, more than one ask in the CTA, stock phrases, stage directions, hashtags and emojis, sentences too long to say in one breath, and a body with nothing concrete in it. Each issue is written as an instruction ("Cut about 18 words, mostly from the body…") and sent straight back to the model. Only *hard* issues trigger a rewrite.

**5. Don't put invented facts in a creator's mouth.** Specific details make scripts better, and specific details are exactly what LLMs make up. Instead of banning numbers, the model lists every figure it invented or any claim that needs checking under `verify`. The CLI prints them as "check before filming".

**6. It always runs.** With no API key, a rules-only fallback ([`templates.py`](scriptbench/templates.py)) produces a correctly structured, roughly timed script. It's deliberately a baseline. Put next to the LLM output, it shows what the model adds.

## Run it

Requires Python 3.10+. There are **no dependencies to install**: the API calls use the standard library.

1. Get a free API key from **Gemini** (<https://aistudio.google.com/apikey>) or **Groq** (<https://console.groq.com/keys>).
2. Copy `.env.example` to `.env` and paste the key in as `GEMINI_API_KEY` or `GROQ_API_KEY`. Setting it as an environment variable also works.

```bash
python -m scriptbench --niche "personal finance" --topic "I automated my savings and forgot about it for two years" --seconds 45
```

Options:

| flag | what it does |
|---|---|
| `--json` | print exactly `{"hook", "body", "cta"}` |
| `--json --verbose` | add diagnostics: hook candidates and their scores, revisions, estimated timing, remaining issues, facts to verify |
| `--offline` | skip the LLM and use the rules-only fallback |
| `--wps 2.8` | speaking rate for a faster talker |

**In the browser:** run the command below, then open <http://127.0.0.1:8000>. It's a small local page (standard library only) with the same generator behind it, plus a view of every hook candidate and its score. It only listens on your own machine, so your API key and quota stay private.

```bash
python -m scriptbench.web
```

**Models:** Gemini tries `gemini-3.5-flash`, then `gemini-3.7-flash`, `gemini-3.8-flash` and `gemini-flash-latest`. It moves to the next model only when one is overloaded or unreachable. A bad key or a bad request fails immediately instead of being retried somewhere else. After a fallback, later calls in the same run start from the model that worked. To pin a single model or set your own chain, use `GEMINI_MODEL` (comma-separated). Groq defaults to `llama-3.3-70b-versatile`, which you can change with `GROQ_MODEL`. If both keys are set, Gemini is used unless `SCRIPTBENCH_PROVIDER=groq`.

**Why two providers:** the pipeline only depends on a `generate_json(system, prompt, schema)` interface. Gemini enforces the JSON schema server-side. Groq's JSON mode only guarantees valid JSON, so its client puts the schema in the prompt instead. In both cases the critic re-checks everything the model returns. Swapping providers is a config change, not a code change. It paid off while building this: Gemini was overloaded for hours during development.

To reproduce the samples:

```bash
python run_samples.py
python run_samples.py --offline
```

The first command writes to `samples/outputs/` and the second writes the rules-only baseline to `samples/offline/`. To run the tests (no network or key needed, since a fake model is swapped in):

```bash
python -m unittest -v
```

## Sample outputs

[`samples/outputs/SAMPLES.md`](samples/outputs/SAMPLES.md) has six topics across six niches at 30, 45 and 60 seconds, printed exactly as generated. Each one also has a JSON file with the full diagnostics. [`samples/offline/`](samples/offline/) has the same topics from the rules-only fallback for comparison. [`samples/REVIEW.md`](samples/REVIEW.md) is my critique of the outputs: what worked, and the flaws the critic missed.

## Why it produces good scripts

- **Timed to the runtime.** Length is measured and enforced, not requested and hoped for.
- **The hook is chosen, not accepted.** Three real alternatives in different styles, filtered by rules.
- **Hook and body can't drift apart.** Both are written around one committed angle.
- **It sounds spoken.** Short sentences, no labels or brackets, and nothing that only works on a screen.
- **One ask at the end, tied to the video.** Never "like and subscribe".
- **Revisions are safe.** Every version is scored and the best one is returned.
- **It's honest about facts.** Invented specifics are flagged instead of passed off as true.

## What it doesn't do (yet)

- **The critic can reject bad scripts but can't recognise good ones.** The rules-only baseline scores 100/100 on some topics while reading like filler (see `samples/offline/`). Good writing still comes from the model. Using a second LLM as a judge to compare hooks is the natural next step. I left it out to keep the cost at 1–3 calls per script and every decision explainable.
- **Speaking rate is one number.** It could be calibrated per creator from a sample video.
- **English only.** The critic's patterns are English.

## Layout

```
scriptbench/
  timing.py     runtime -> word budget
  hooks.py      hook styles, topic shape, hook ranking
  critic.py     deterministic checks and score
  prompts.py    system prompt, draft/revise prompts, JSON schemas
  llm.py        Gemini and Groq clients (stdlib only), .env loading
  templates.py  offline fallback
  generator.py  the pipeline; generate() and generate_detailed()
  cli.py        command line
  web.py        local browser UI server (python -m scriptbench.web)
  index.html    the browser UI page: form, timing bar, hook candidates, checks
run_samples.py  regenerates samples/
tests/          unit tests with a fake model
NOTE.md         what makes a script good
```
