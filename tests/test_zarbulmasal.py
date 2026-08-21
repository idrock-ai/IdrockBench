"""Riddle scoring. Uzbek is agglutinative, so the matcher has to accept
inflections without accepting different words that share a stem."""

import pytest

from idrockbench.tasks.zarbulmasal import ZarbulmasalChoiceTask, ZarbulmasalTask, matches

ROWS = [
    {"id": 1, "riddle": "Oq sandiq, ichi to'la oltin.", "answer": "tuxum",
     "accepted": ["tuxum"], "distractors": ["asal", "bug'doy", "quti"],
     "theme": "oziq-ovqat", "difficulty": "oson"},
    {"id": 2, "riddle": "Ikki og'ayni, bir-birini ko'rmaydi.", "answer": "ko'zlar",
     "accepted": ["ko'z", "ko'zlar"], "distractors": ["quloqlar", "qo'llar", "oyoqlar"],
     "theme": "tana", "difficulty": "o'rta"},
]


class TestFreeTextMatching:
    ACCEPTED = ["ko'z", "ko'zlar"]

    @pytest.mark.parametrize("answer", [
        "ko'z", "koʻz", "ko'zlar", "ko'zlari", "ko'zni", "ko'zlarimiz",
        "koz", "  KO'ZLAR.  ", "Javob: ko'z",
    ])
    def test_inflections_and_spellings_are_accepted(self, answer):
        assert matches(answer, self.ACCEPTED)

    @pytest.mark.parametrize("answer,why", [
        ("ko'zoynak", "spectacles — a different word sharing the stem"),
        ("ko'zacha", "small jug — likewise"),
        ("quloq", "simply wrong"),
        ("", "empty"),
    ])
    def test_different_words_are_rejected(self, answer, why):
        assert not matches(answer, self.ACCEPTED), why

    def test_a_riddle_may_admit_several_answers(self):
        assert matches("daryo", ["suv", "daryo"])
        assert matches("suv", ["suv", "daryo"])


class TestTasks:
    def test_free_text_scores_an_inflected_answer(self):
        task = ZarbulmasalTask()
        item = task.prepare(ROWS)[1]
        assert task.score(task.parse("Javob: ko'zlari", item), item) == 1.0
        assert task.score(task.parse("Javob: quloq", item), item) == 0.0

    def test_multiple_choice_uses_the_same_riddles(self):
        free = {i.id for i in ZarbulmasalTask().prepare(ROWS)}
        mc = {i.id for i in ZarbulmasalChoiceTask().prepare(ROWS)}
        assert free == mc, "both formats must cover the same items to be comparable"

    def test_items_without_three_distractors_are_skipped_not_padded(self):
        rows = [{**ROWS[0], "distractors": ["asal"]}]
        assert ZarbulmasalChoiceTask().prepare(rows) == []
        assert len(ZarbulmasalTask().prepare(rows)) == 1, "free text still works"

    def test_a_distractor_equal_to_the_answer_is_reported(self):
        rows = [{**ROWS[0], "distractors": ["tuxumlar", "asal", "quti"]}]
        problems = ZarbulmasalChoiceTask().validate(rows)
        assert any("distractor" in p for p in problems)

    def test_chance_levels_differ_between_the_two_formats(self):
        assert ZarbulmasalTask().chance_level == 0.0, "naming a noun is not guessable"
        assert ZarbulmasalChoiceTask().chance_level == 0.25


def test_display_normalisation_keeps_the_tutuq_belgisi():
    """Uzbek uses two modifier letters and the rule between them is positional:
    U+02BB only in the digraphs oʻ and gʻ, U+02BC (tutuq belgisi) everywhere
    else. `normalize` folds both to U+02BB, which is right for comparison and
    wrong for text a human reads — it turns "sheʼr" into "sheʻr"."""
    from idrockbench.text.normalize import normalize, normalize_display

    assert normalize("she'r") == "sheʻr", "matching form folds everything"
    assert normalize_display("she'r") == "sheʼr"
    assert normalize_display("sheʻr") == "sheʼr", "repairs an over-folded input"
    for word in ("maʼno", "sanʼat", "taʼlim"):
        assert normalize_display(word) == word
    # The digraphs must keep U+02BB.
    assert normalize_display("bo'lib") == "boʻlib"
    assert normalize_display("g'oz") == "gʻoz"
    assert normalize_display("Oʻzbekiston") == "Oʻzbekiston"


def test_riddle_prompts_carry_correct_orthography():
    """The prompt is what a native speaker sees. A benchmark that misspells the
    language it measures is not publishable."""
    import re

    from idrockbench.data.loader import load
    from idrockbench.tasks.zarbulmasal import ZarbulmasalChoiceTask, ZarbulmasalTask

    misplaced = re.compile(r"(?<![oOgG])ʻ")
    rows = load("zarbulmasal.json").rows
    for task in (ZarbulmasalTask(seed=42), ZarbulmasalChoiceTask(seed=42)):
        for item in task.prepare(rows):
            assert not misplaced.search(item.payload["riddle"]), item.payload["riddle"]
            for option in item.payload.get("options", []):
                assert not misplaced.search(option), option


def test_an_accepted_answer_may_not_appear_in_the_riddle():
    """Otherwise a model scores by copying a word out of the question. Caught in
    the harvest: "Koʻk kosani toʻntardim" (answer osmon) accepted "koʻk"."""
    from idrockbench.tasks.zarbulmasal import ZarbulmasalTask

    leaky = [{"id": 1, "riddle": "Koʻk kosani toʻntardim.", "answer": "osmon",
              "accepted": ["osmon", "koʻk"], "distractors": ["bulut", "oy", "quyosh"]}]
    problems = ZarbulmasalTask(seed=1).validate(leaky)
    assert any("appears in the riddle text" in p for p in problems)


def test_the_shipped_riddle_set_is_clean():
    """The whole point of the harvest was that not one bad item ships."""
    from idrockbench.data.loader import load
    from idrockbench.tasks.zarbulmasal import ZarbulmasalChoiceTask, ZarbulmasalTask

    rows = load("zarbulmasal.json").rows
    assert len(rows) >= 300, f"only {len(rows)} riddles"
    for task in (ZarbulmasalTask(seed=42), ZarbulmasalChoiceTask(seed=42)):
        assert task.validate(rows) == []
        assert len(task.prepare(rows)) == len(rows)
