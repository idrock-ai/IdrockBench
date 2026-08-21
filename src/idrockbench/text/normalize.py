from __future__ import annotations

import re
import unicodedata

APOSTROPHE_VARIANTS = (
    "'"
    "‘"
    "’"
    "‛"
    "ʼ"
    "ʽ"
    "`"
    "´"
    "′"
)
CANONICAL_APOSTROPHE = "ʻ"

_APOSTROPHE_TABLE = {ord(c): CANONICAL_APOSTROPHE for c in APOSTROPHE_VARIANTS}

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

_WORD_RE = re.compile(r"[\wʻ]+", re.UNICODE)

_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def normalize(text: str, *, fold_homoglyphs: bool = False) -> str:
    if not text:
        return ""
    out = unicodedata.normalize("NFC", str(text))
    out = out.translate(_APOSTROPHE_TABLE)
    if fold_homoglyphs:
        out = out.translate(_HOMOGLYPH_TABLE)
    return out


_MISPLACED_TURNED_COMMA = re.compile(r"(?<![oOgG])" + CANONICAL_APOSTROPHE)

TUTUQ_BELGISI = "ʼ"


def normalize_display(text: str, *, fold_homoglyphs: bool = False) -> str:
    out = normalize(text, fold_homoglyphs=fold_homoglyphs)
    return _MISPLACED_TURNED_COMMA.sub(TUTUQ_BELGISI, out)


def normalize_for_match(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", normalize(text).casefold()).strip()


def strip_apostrophes(text: str) -> str:
    return normalize(text).replace(CANONICAL_APOSTROPHE, "")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(normalize(text))


def count_words(text: str) -> int:
    return len(words(text))


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text or ""))


def cyrillic_ratio(text: str) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _CYRILLIC_RE.match(c)) / len(letters)
