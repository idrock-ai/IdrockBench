"""Task scoring. Each test pins a scoring bug that changed published numbers."""

import pytest

from idrockbench.core import Item
from idrockbench.metrics.accuracy import accuracy_with_ci, normalize_against_chance, wilson_interval
from idrockbench.metrics.translation import corpus_scores
from idrockbench.tasks.mcq import permute
from idrockbench.tasks.mmlu_pro_uz import parse_options
from idrockbench.tasks.reasoning_uz import ReasoningTask, normalize_yes_no, score_slots


class TestOptionParsing:
    def test_numpy_repr_with_short_options_keeps_all_ten(self):
        # Splitting on \n collapsed this to 2 "options" because NumPy only
        # line-wraps past ~75 chars, which put the gold answer outside the
        # prompt for 147 of 200 items.
        raw = ("['$50,200' '$45,100' '$60,400' '$56,300' '$58,800' '$54,400' "
               "'$65,500'\n '$62,900' '$48,700' '$52,600']")
        assert len(parse_options(raw)) == 10

    def test_json_array(self):
        assert parse_options('["a", "b"]') == ["a", "b"]

    def test_real_list_passes_through(self):
        assert parse_options(["a", "b"]) == ["a", "b"]

    def test_empty(self):
        assert parse_options("") == [] and parse_options(None) == []


class TestOptionPermutation:
    def test_gold_follows_by_index_not_by_text(self):
        # Remapping by text picks the first duplicate, so a correct reader was
        # marked wrong on a coin flip.
        import random
        options = ["fevral", "fevral", "dekabr", "noyabr"]
        for seed in range(50):
            shuffled, gold = permute(options, 1, random.Random(seed))
            assert shuffled[gold] == "fevral"

    def test_permutation_preserves_the_option_set(self):
        import random
        options = ["a", "b", "c", "d"]
        shuffled, gold = permute(options, 2, random.Random(7))
        assert sorted(shuffled) == sorted(options)
        assert shuffled[gold] == "c"


class TestUzbekOrthographyIsNotPenalised:
    """A perfect Uzbek answer scored 26.67% — below a constant guesser at 30% —
    purely because of which apostrophe the model typed."""

    @pytest.fixture
    def task(self):
        return ReasoningTask()

    @pytest.fixture
    def item(self):
        return Item(id="1", payload={"question": "", "task": "web_of_lies_v2"},
                    gold="yo'q, ha, ha")

    @pytest.mark.parametrize("answer", [
        "**yo'q, ha, ha**",     # ASCII
        "**yoʻq, ha, ha**",     # canonical U+02BB
        "**yo’q, ha, ha**",     # typographic U+2019
        "**yo‘q, ha, ha**",     # U+2018
        "**yoq, xa, xa**",      # colloquial spellings
        "**no, yes, yes**",     # English
    ])
    def test_every_correct_spelling_scores_full_marks(self, task, item, answer):
        assert task.score(task.parse(answer, item), item) == 1.0

    def test_a_wrong_answer_still_loses(self, task, item):
        assert task.score(task.parse("**ha, ha, ha**", item), item) < 0.5


class TestPartialCreditAlignment:
    def test_a_short_answer_list_is_not_left_aligned(self):
        # Padding shifted every remaining slot, turning one unrecognised token
        # into a near-total loss.
        assert score_slots(["no", "no"], ["yes", "no", "no"]) == 0.0

    def test_livebench_formula(self):
        assert score_slots(["a", "b", "c"], ["a", "b", "c"]) == 1.0
        assert score_slots(["a", "b", "x"], ["a", "b", "c"]) == pytest.approx(1 / 3)

    def test_yes_no_vocabulary(self):
        assert normalize_yes_no("Yoʻq") == "no"
        assert normalize_yes_no("HA") == "yes"
        assert normalize_yes_no("noma'lum") == "unknown"
        assert normalize_yes_no("qizil") is None


class TestZebraScoring:
    @pytest.fixture
    def task(self):
        return ReasoningTask()

    def test_negating_every_slot_is_not_a_perfect_score(self, task):
        gold = "1, kinorejissyorlik, politsiya xodimi, jurnalist"
        item = Item(id="1", payload={"question": "", "task": "zebra_puzzle"}, gold=gold)
        answer = ("<solution>1 emas, kinorejissyorlik emas, "
                  "politsiya xodimi emas, jurnalist emas</solution>")
        # Substring matching credited this with 1.0.
        assert task.score(task.parse(answer, item), item) == 0.0

    def test_exact_answer_scores_one(self, task):
        gold = "1, a, b, c"
        item = Item(id="1", payload={"question": "", "task": "zebra_puzzle"}, gold=gold)
        assert task.score(task.parse(f"<solution>{gold}</solution>", item), item) == 1.0

    def test_ten_is_not_one(self, task):
        item = Item(id="1", payload={"question": "", "task": "zebra_puzzle"}, gold="1")
        assert task.score(task.parse("<solution>10</solution>", item), item) == 0.0


class TestTranslationMetrics:
    def test_apostrophe_variant_does_not_destroy_the_score(self):
        ref = ["Bu oʻzbek tilidagi gap boʻlib, unda gʻalaba soʻzi ham bor va yana bir necha soʻz."]
        hyp = ["Bu o'zbek tilidagi gap bo'lib, unda g'alaba so'zi ham bor va yana bir necha so'z."]
        assert corpus_scores(hyp, ref)["bleu"] == 100.0
        # Without normalisation the same correct translation loses two thirds.
        assert corpus_scores(hyp, ref, normalize_uz=False)["bleu"] < 50

    def test_signatures_are_reported(self):
        out = corpus_scores(["a b c d e"], ["a b c d e"])
        assert "chrf2pp_signature" in out and "bleu_signature" in out

    def test_cyrillic_output_is_reported_not_hidden(self):
        out = corpus_scores(["бўлиб ўз ғалаба"], ["boʻlib oʻz gʻalaba"])
        assert out["cyrillic_output_rate"] == 1.0


class TestStatistics:
    def test_wilson_interval_stays_inside_zero_to_one(self):
        assert wilson_interval(0, 10)[0] == 0.0
        assert wilson_interval(10, 10)[1] == 100.0

    def test_a_chance_level_score_normalises_to_zero(self):
        assert normalize_against_chance(25.0, 0.25) == 0.0
        assert normalize_against_chance(10.0, 0.10) == 0.0

    def test_below_chance_clamps_rather_than_going_negative(self):
        assert normalize_against_chance(5.0, 0.25) == 0.0

    def test_ten_option_and_four_option_scores_are_not_comparable_raw(self):
        # 25% is chance on four options and real signal on ten.
        assert normalize_against_chance(25, 0.25) < normalize_against_chance(25, 0.10)

    def test_empty_input(self):
        assert accuracy_with_ci([])["accuracy"] == 0.0


class TestThinCellsAreWithheld:
    def test_a_cell_scored_on_a_fraction_of_items_is_not_published(self, tmp_path):
        """gemma4:26b scored 85.7 on reasoning from 7 of 100 items. A number
        with a 49-point interval must not sit on a leaderboard looking like a
        result — it reports the harness, not the model."""
        import json

        from idrockbench.config import SuiteConfig
        from idrockbench.report import build_leaderboard

        run = tmp_path / "runs" / "m"
        run.mkdir(parents=True)
        (run / "manifest.json").write_text(json.dumps({
            "run_id": "m", "model": "M", "license": "apache-2.0", "tasks": {
                "dtm": {"metrics": {"primary": 48.5, "ci_low": 46.4, "ci_high": 50.7},
                        "diagnostics": {"coverage": 1.0}, "n_scored": 2060, "n_items": 2062},
                "reasoning_uz": {"metrics": {"primary": 85.7, "ci_low": 48.7, "ci_high": 97.4},
                                 "diagnostics": {"coverage": 0.07}, "n_scored": 7, "n_items": 100},
            },
        }))
        board = build_leaderboard(tmp_path / "runs",
                                  SuiteConfig(name="t", tasks=["dtm", "reasoning_uz"]),
                                  tmp_path / "out.json")
        row = board["models"][0]
        assert "dtm" in row["scores"]
        assert "reasoning_uz" not in row["scores"], "7%-coverage cell must be withheld"
        assert row["withheld"]["reasoning_uz"] == 0.07
        assert row["composite"] is None, "an incomplete row gets no composite"
