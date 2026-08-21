"""Uzbek text normalisation.

Every comparison in this benchmark — answer extraction, keyword matching,
translation references, gold strings — goes through here first. Without it the
benchmark measures which apostrophe a model happens to type.

Uzbek Latin uses two modifier letters that models spell inconsistently:

    oʻ  gʻ    U+02BB MODIFIER LETTER TURNED COMMA   (canonical, category Lm)
    ʼ         U+02BC MODIFIER LETTER APOSTROPHE     (canonical tutuq belgisi)

Models routinely emit ASCII ``'`` (U+0027, category Po) or the typographic
``'``/``'`` (U+2018/U+2019, category Pi/Pf) instead. The category matters: Lm is
a word character to ``\\w`` and ``\\b``, Po and Pi are not. So the *same word*
tokenises differently depending on the codepoint:

    "boʻlib"  (U+02BB) -> ["boʻlib"]                 1 token
    "bo'lib"  (U+0027) -> ["bo", "lib"]              2 tokens

That single difference is why an un-normalised harness scores a perfect Uzbek
answer below a random guesser, and why ``\\b[A-J]\\b`` extracts "G" from
"to'g'ri" — the most natural Uzbek word for "correct".
"""

from __future__ import annotations

import re
import unicodedata

# Every codepoint we have observed standing in for the Uzbek modifier letters,
# mapped to the canonical U+02BB. U+02BC (tutuq belgisi) also folds here: the
# two are visually and functionally distinct in careful orthography, but no
# model distinguishes them reliably, so treating them as one avoids penalising
# a correct answer for a typographic choice.
APOSTROPHE_VARIANTS = (
    "'"  # ' APOSTROPHE
    "‘"  # ' LEFT SINGLE QUOTATION MARK
    "’"  # ' RIGHT SINGLE QUOTATION MARK
    "‛"  # ‛ SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "ʼ"  # ʼ MODIFIER LETTER APOSTROPHE
    "ʽ"  # ʽ MODIFIER LETTER REVERSED COMMA
    "`"  # ` GRAVE ACCENT
    "´"  # ´ ACUTE ACCENT
    "′"  # ′ PRIME
)
CANONICAL_APOSTROPHE = "ʻ"

_APOSTROPHE_TABLE = {ord(c): CANONICAL_APOSTROPHE for c in APOSTROPHE_VARIANTS}

# Cyrillic letters that are visually identical to Latin ones. Scanned-source
# extraction leaves these inside otherwise-Latin words, where they silently
# break equality and regex matching.
_HOMOGLYPH_TABLE = {
    ord("а"): "a", ord("А"): "A",
    ord("е"): "e", ord("Е"): "E",
    ord("о"): "o", ord("О"): "O",
    ord("р"): "p", ord("Р"): "P",
    ord("с"): "c", ord("С"): "C",
    ord("у"): "y", ord("У"): "Y",
    ord("х"): "x", ord("Х"): "X",
    ord("к"): "k", ord("К"): "K",
    ord("в"): "B", ord("В"): "B",
    ord("м"): "m", ord("М"): "M",
    ord("н"): "H", ord("Н"): "H",
    ord("т"): "T", ord("Т"): "T",
}

_WHITESPACE_RE = re.compile(r"\s+")

# A word for counting purposes: letters/digits plus the canonical modifier
# letter. Runs after apostrophe folding, so "boʻlib" is one token.
_WORD_RE = re.compile(r"[\wʻ]+", re.UNICODE)

# Uzbek Cyrillic detection: any character in the Cyrillic block.
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def normalize(text: str, *, fold_homoglyphs: bool = False) -> str:
    """Canonicalise Uzbek text for comparison.

    Applies NFC composition and folds every apostrophe variant to U+02BB.
    Idempotent, and safe on Russian and English text (neither uses the folded
    codepoints in a meaning-bearing way).

    Args:
        text: Input string. ``None``-ish values are coerced to ``""``.
        fold_homoglyphs: Also map visually-identical Cyrillic letters to Latin.
            Off by default because it corrupts genuinely Cyrillic text; enable
            it for ingest-time dataset repair, not for scoring Cyrillic output.

    Returns:
        The normalised string.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFC", str(text))
    out = out.translate(_APOSTROPHE_TABLE)
    if fold_homoglyphs:
        out = out.translate(_HOMOGLYPH_TABLE)
    return out


#: U+02BB is correct in Uzbek Latin *only* as part of the digraphs oʻ and gʻ.
#: Every other apostrophe is the tutuq belgisi U+02BC — sheʼr, taʼm, maʼno,
#: sanʼat. Anything matching this is a fold that went one step too far.
_MISPLACED_TURNED_COMMA = re.compile(r"(?<![oOgG])" + CANONICAL_APOSTROPHE)

#: The tutuq belgisi (glottal stop), distinct from the oʻ/gʻ modifier.
TUTUQ_BELGISI = "ʼ"


def normalize_display(text: str, *, fold_homoglyphs: bool = False) -> str:
    """Canonicalise Uzbek text for *display*, preserving correct orthography.

    :func:`normalize` folds every apostrophe variant to U+02BB, which is right
    for comparison — no model distinguishes the two modifier letters reliably,
    so a correct answer must not be marked wrong over a typographic choice. It
    is wrong for text a human will read: it turns ``sheʼr`` into ``sheʻr``.

    Uzbek uses two marks and the rule between them is positional:

    * ``ʻ`` U+02BB only in the digraphs ``oʻ`` and ``gʻ``
    * ``ʼ`` U+02BC everywhere else — the tutuq belgisi in Arabic loanwords

    So this normalises every variant, then puts each one back as whichever mark
    its position calls for. Use it for prompt text; use :func:`normalize_for_match`
    to compare answers.
    """
    out = normalize(text, fold_homoglyphs=fold_homoglyphs)
    return _MISPLACED_TURNED_COMMA.sub(TUTUQ_BELGISI, out)


def normalize_for_match(text: str) -> str:
    """Normalise, casefold, and collapse whitespace.

    Use for equality tests between a model's answer and a gold string, where
    case and spacing carry no information.
    """
    return _WHITESPACE_RE.sub(" ", normalize(text).casefold()).strip()


def strip_apostrophes(text: str) -> str:
    """Normalise, then remove apostrophes entirely.

    The most permissive comparison form. Use as a documented fallback when a
    model omits the modifier letter altogether ("yoq" for "yoʻq") — never as
    the primary comparison, since it collapses real minimal pairs.
    """
    return normalize(text).replace(CANONICAL_APOSTROPHE, "")


def words(text: str) -> list[str]:
    """Tokenise into words, apostrophe-aware.

    ``len(words(t))`` is the word count this benchmark reports. It is *not*
    ``str.split()``: split() counts "bo'lib" as one token only by accident of
    whitespace, and miscounts hyphenated compounds ("ob-havo") as one word
    where every tokeniser counts two. Always report which counter was used.
    """
    return _WORD_RE.findall(normalize(text))


def count_words(text: str) -> int:
    """Number of words, apostrophe-aware. See :func:`words`."""
    return len(words(text))


def has_cyrillic(text: str) -> bool:
    """True if the text contains any Cyrillic character.

    Uzbek is written in both Latin and Cyrillic. A model answering in the wrong
    script is a real finding about the model, and must be reported as a
    diagnostic rather than silently folded into a score.
    """
    return bool(_CYRILLIC_RE.search(text or ""))


def cyrillic_ratio(text: str) -> float:
    """Fraction of letters that are Cyrillic, in ``[0, 1]``."""
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _CYRILLIC_RE.match(c)) / len(letters)
