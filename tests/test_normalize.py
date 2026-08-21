"""Uzbek normalisation. Every apostrophe a model might type must compare equal."""

import pytest

from idrockbench.text.normalize import (
    count_words,
    cyrillic_ratio,
    has_cyrillic,
    normalize,
    normalize_for_match,
    strip_apostrophes,
    words,
)

# The five spellings of "boʻlib" seen in real model output.
VARIANTS = ["boʻlib", "bo'lib", "bo‘lib", "bo’lib", "boʼlib", "bo`lib"]


@pytest.mark.parametrize("text", VARIANTS)
def test_all_apostrophe_variants_normalise_to_one_form(text):
    assert normalize(text) == "boʻlib"


@pytest.mark.parametrize("text", VARIANTS)
def test_apostrophe_variants_are_one_word_not_two(text):
    # str.split() and a naive \w+ both count "bo'lib" as two tokens, which
    # doubles every word count depending on which codepoint was typed.
    assert count_words(text) == 1


def test_normalize_is_idempotent():
    assert normalize(normalize("bo'lib")) == normalize("bo'lib")


def test_hyphenated_compound_is_two_words():
    assert count_words("ob-havo yaxshi") == 3


def test_match_form_ignores_case_and_spacing():
    assert normalize_for_match("  YOʻQ   ha ") == normalize_for_match("yo'q ha")


def test_strip_apostrophes_is_the_permissive_fallback():
    assert strip_apostrophes("yo'q") == "yoq"


def test_homoglyph_folding_is_opt_in():
    cyrillic_a = "buzаr"          # Cyrillic а inside a Latin word
    assert normalize(cyrillic_a) == cyrillic_a
    assert normalize(cyrillic_a, fold_homoglyphs=True) == "buzar"


def test_script_detection_reports_rather_than_hides():
    assert has_cyrillic("бўлиб") and not has_cyrillic("boʻlib")
    assert cyrillic_ratio("бўлиб") == 1.0
    assert cyrillic_ratio("boʻlib") == 0.0


def test_empty_and_none_are_safe():
    assert normalize("") == "" and normalize(None) == ""
    assert words("") == []
