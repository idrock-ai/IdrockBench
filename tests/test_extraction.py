"""Answer extraction. Each test names the failure it prevents."""

import pytest

from idrockbench.extraction import (
    ParseStatus,
    extract_bold,
    extract_choice,
    extract_json,
    extract_last_line,
    extract_tagged,
    strip_reasoning,
)


class TestUzbekLetterExtraction:
    def test_togri_javob_does_not_extract_G(self):
        # "to'g'ri javob" is the natural Uzbek for "the correct answer". The
        # apostrophe is not a word character, so \b[A-J]\b matched the G in
        # "to'G'ri" before reaching the real answer.
        assert extract_choice("To'g'ri javob: H", 10).value == "H"

    @pytest.mark.parametrize("word,letter", [
        ("a'lo", "A"), ("e'lon", "E"), ("o'g'il", "G"), ("g'oya", "G"),
    ])
    def test_uzbek_words_never_supply_the_answer(self, word, letter):
        result = extract_choice(f"{word} degan so'z bor.", 10)
        assert result.value != letter
        assert result.status is ParseStatus.UNPARSED

    def test_answer_stated_then_alternatives_discussed(self):
        # Taking the LAST letter picked up D from the rejected options.
        assert extract_choice("Javob: B. A varianti noto'g'ri, C ham, D ham.", 4).value == "B"

    def test_letters_beyond_the_rendered_options_are_rejected(self):
        # A model cannot have chosen an option it was never shown.
        assert extract_choice("Javob: H", 4).status is ParseStatus.UNPARSED


class TestReasoningTraces:
    def test_closed_trace_is_removed(self):
        assert extract_choice("<think>Menimcha B</think>\nJavob: H", 10).value == "H"

    def test_unterminated_trace_counts_as_truncated_not_wrong(self):
        r = extract_choice("<think>Variant A mos emas. Keyin B ni ko'raman", 4)
        assert r.status is ParseStatus.TRUNCATED
        assert r.value is None

    def test_strip_reasoning_reports_the_dangling_case(self):
        assert strip_reasoning("<think>hmm</think> Javob") == ("Javob", False)
        assert strip_reasoning("<think>hmm")[1] is True


class TestParseFailureIsNotAWrongAnswer:
    def test_refusal_does_not_become_an_answer(self):
        # "Bilmayman" ("I don't know") starts with B, and a first-character
        # fallback turned that into a confident answer B.
        r = extract_choice("Bilmayman.", 4)
        assert r.status is ParseStatus.UNPARSED and r.value is None

    def test_empty_response(self):
        assert extract_choice("", 4).status is ParseStatus.UNPARSED


class TestCommonAnswerFormats:
    @pytest.mark.parametrize("response", [
        "B", " b ", "**B**", "Javob: B", "Javob — B", "javob: (B)",
        "Answer: B", "Ответ: B", r"\boxed{B}", "...\nB)", "B) ikkinchi variant",
    ])
    def test_formats_that_must_all_yield_B(self, response):
        assert extract_choice(response, 4).value == "B"


class TestFreeText:
    def test_translation_keeps_every_line(self):
        # Taking only the first line scored a correct multi-line translation
        # as BLEU 0, which is how a published "0.0" was produced.
        text = "Tarjima:\nThe cat sat on the mat\nand then went to sleep."
        got = extract_last_line(text, strip_prefixes=("Tarjima",)).value
        assert got == "The cat sat on the mat\nand then went to sleep."

    def test_hedging_with_several_bold_candidates_is_not_an_answer(self):
        assert extract_bold("**2**, **3** yoki **4**").status is ParseStatus.UNPARSED

    def test_reasoning_then_committing_is_an_answer(self):
        assert extract_bold("Balki **2**.\nYakuniy javob: **4**").value == "4"

    def test_tagged_solution(self):
        assert extract_tagged("<solution>a, b</solution>").value == "a, b"

    def test_json_must_be_the_whole_response(self):
        assert extract_json('```json\n{"a": 1}\n```').ok
        assert not extract_json('Here you go: {"a": 1} hope that helps').ok
