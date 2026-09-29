import os
import unittest
import unittest.mock

from scriptbench import critic, generate, generate_detailed
from scriptbench.hooks import choose_archetypes, is_story, rank_hooks
from scriptbench.llm import FallbackClient, LLMError, client_from_env
from scriptbench.timing import plan_budget, spoken_words

GOOD_BODY = (
    "I set a transfer of 50 dollars every payday and turned off the notifications.\n\n"
    "For two years I never looked. No budgeting app, no spreadsheet, nothing.\n\n"
    "When I finally checked, there was more money in that account than I'd ever saved on purpose.\n\n"
    "Saving isn't about discipline. It's about removing the moment where you get to decide."
)


class FakeClient:
    """Returns queued responses in order and records the prompts it was sent."""

    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, system, prompt, schema, temperature):
        self.prompts.append(prompt)
        return self.responses.pop(0)


class TimingTests(unittest.TestCase):
    def test_budget_scales_with_runtime(self):
        short, long = plan_budget(30), plan_budget(60)
        self.assertEqual(short.total_words, 75)
        self.assertEqual(long.total_words, 150)
        self.assertLess(short.beats, long.beats)
        self.assertEqual(short.total_words, 10 + short.body_words + short.cta_words)

    def test_numbers_count_as_more_spoken_words(self):
        self.assertEqual(spoken_words("I saved $1,200"), 4)
        self.assertEqual(spoken_words("wait -- what"), 2)

    def test_rejects_non_short_form_runtimes(self):
        with self.assertRaises(ValueError):
            plan_budget(5)
        with self.assertRaises(ValueError):
            plan_budget(600)


class CriticTests(unittest.TestCase):
    budget = plan_budget(30)

    def codes(self, **script):
        base = {"hook": "I forgot about my savings for two years.", "body": GOOD_BODY,
                "cta": "Comment the first bill you'd automate."}
        return {i.code for i in critic.lint({**base, **script}, self.budget)}

    def test_catches_warmup_hook(self):
        self.assertIn("hook_warmup", self.codes(hook="Hey guys, today I want to talk about saving."))

    def test_catches_multiple_asks(self):
        self.assertIn("cta_multi_ask", self.codes(cta="Like, comment and follow for more."))

    def test_catches_stage_directions_and_hashtags(self):
        codes = self.codes(body=GOOD_BODY + "\n\n[cut to b-roll] #money")
        self.assertIn("stage_direction", codes)
        self.assertIn("hashtag_emoji", codes)

    def test_catches_length_both_ways(self):
        self.assertIn("too_short", self.codes(body="Short."))
        self.assertIn("too_long", self.codes(body=GOOD_BODY * 3))


class HookTests(unittest.TestCase):
    def test_story_detection_drives_archetypes(self):
        self.assertTrue(is_story("I automated my savings"))
        self.assertIn("in_media_res", choose_archetypes("I automated my savings"))
        self.assertIn("mistake", choose_archetypes("How to study for exams"))

    def test_ranker_prefers_specific_over_warmup(self):
        ranked = rank_hooks(
            [{"style": "a", "text": "Hey everyone, let's talk about money today."},
             {"style": "b", "text": "I haven't checked my savings in 730 days."}],
            plan_budget(45), story=True,
        )
        self.assertEqual(ranked[0].style, "b")


class GeneratorTests(unittest.TestCase):
    draft = {
        "angle": "Automation beats discipline.",
        "hooks": [{"style": "bold_claim", "text": "Hey guys, saving is easy."},
                  {"style": "specific_result", "text": "I didn't touch my savings for 730 days."}],
        "body_beats": GOOD_BODY.split("\n\n"),
        "cta": "Comment the first bill you'd automate.",
        "verify": ["$50 per payday"],
    }

    def test_offline_returns_brief_shape(self):
        script = generate("fitness", "Why walking beats HIIT for desk workers", 30, offline=True)
        self.assertEqual(set(script), {"hook", "body", "cta"})
        self.assertTrue(all(script.values()))

    def test_llm_path_picks_best_hook_without_revising_clean_draft(self):
        client = FakeClient(self.draft)
        result = generate_detailed("personal finance", "I automated my savings", 30, client=client)
        self.assertEqual(result.hook, "I didn't touch my savings for 730 days.")
        self.assertEqual(result.meta["revisions"], 0)
        self.assertEqual(len(client.prompts), 1)

    def test_revision_feeds_issues_back_and_keeps_best(self):
        bloated = {**self.draft, "body_beats": self.draft["body_beats"] * 3}
        fixed = {"hook": "I didn't touch my savings for 730 days.", "body": GOOD_BODY,
                 "cta": "Comment the first bill you'd automate.", "verify": []}
        client = FakeClient(bloated, fixed)
        result = generate_detailed("personal finance", "I automated my savings", 30, client=client)
        self.assertEqual(result.meta["revisions"], 1)
        self.assertIn("Cut about", client.prompts[1])
        self.assertEqual(result.body, GOOD_BODY)

    def test_worse_revision_is_discarded(self):
        bloated = {**self.draft, "body_beats": self.draft["body_beats"] * 3}
        worse = {"hook": "Hey guys, welcome back!", "body": "Short.", "cta": "Like and subscribe.", "verify": []}
        client = FakeClient(bloated, worse, worse)
        result = generate_detailed("personal finance", "I automated my savings", 30, client=client)
        self.assertEqual(result.meta["chosen_version"], 0)
        self.assertEqual(result.meta["revisions"], 2)


class FallbackTests(unittest.TestCase):
    class Model:
        def __init__(self, model, error=None):
            self.model, self.error, self.calls = model, error, 0

        def generate_json(self, system, prompt, schema, temperature):
            self.calls += 1
            if self.error:
                raise self.error
            return {"ok": self.model}

    def test_moves_past_overloaded_model_and_remembers_it(self):
        busy = self.Model("busy", LLMError("503", transient=True))
        good = self.Model("good")
        client = FallbackClient([busy, good])
        self.assertEqual(client.generate_json("", "", {}, 0), {"ok": "good"})
        client.generate_json("", "", {}, 0)
        self.assertEqual(busy.calls, 1)  # second call starts from the model that worked
        self.assertEqual(client.model, "good")

    def test_does_not_hide_permanent_errors(self):
        client = FallbackClient([self.Model("bad-key", LLMError("401")), self.Model("good")])
        with self.assertRaises(LLMError):
            client.generate_json("", "", {}, 0)


class ProviderConfigTests(unittest.TestCase):
    def test_explicit_provider_without_its_key_fails_loudly(self):
        env = {"SCRIPTBENCH_PROVIDER": "groq", "GEMINI_API_KEY": "x"}
        with unittest.mock.patch.dict(os.environ, env, clear=True), \
                unittest.mock.patch("scriptbench.llm.load_dotenv"):
            with self.assertRaisesRegex(LLMError, "GROQ_API_KEY is not set"):
                client_from_env()


if __name__ == "__main__":
    unittest.main()
