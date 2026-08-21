"""Verifiable instruction checkers, localised for Uzbek.

Each checker declares a :class:`Disposition` saying how it survives the move
from English. That declaration is the point of this module: the previous
implementation silently *passed* every constraint it could not evaluate, which
let a four-word reply score 20.7% on a benchmark whose whole purpose is to
verify compliance.

Here, a constraint that cannot be evaluated in Uzbek is **excluded and
counted**, never passed and never failed. ``ifeval_uz`` reports the excluded
fraction alongside the score, so the number always states what it covers.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable
from dataclasses import dataclass

from ..text.normalize import count_words, normalize, normalize_for_match


class Disposition(enum.StrEnum):
    """How an instruction type survives translation into Uzbek."""

    TRANSFERABLE = "transferable"
    """Language-neutral — formatting, punctuation, structure. Scored as-is."""

    NEEDS_LOCALE = "needs_localised_kwargs"
    """Scored only when the row supplies Uzbek kwargs. The English kwargs from
    the source dataset ask for English words the Uzbek prompt never requests, so
    scoring them measures translation coverage, not instruction-following."""

    RECALIBRATE = "recalibrate"
    """Scored, but the numeric target was set for English. Uzbek is
    agglutinative and needs materially fewer whitespace words for the same
    content, so a copied word count silently changes the difficulty."""

    DROPPED = "dropped"
    """Not meaningful in Uzbek. Excluded from every reported number."""


@dataclass(slots=True)
class Checker:
    fn: Callable[[str, dict, str], bool]
    disposition: Disposition
    #: kwargs that must be localised before this constraint can be scored.
    locale_keys: tuple[str, ...] = ()
    note: str = ""


REGISTRY: dict[str, Checker] = {}


def checker(instruction_id: str, disposition: Disposition, *,
            locale_keys: tuple[str, ...] = (), note: str = "") -> Callable:
    def deco(fn: Callable[[str, dict, str], bool]) -> Callable:
        REGISTRY[instruction_id] = Checker(fn, disposition, locale_keys, note)
        return fn
    return deco


def _int(kw: dict, *names: str, default: int = 0) -> int:
    """Read a count kwarg. Values arrive as JSON floats; indexing a list with a
    float raises TypeError, which the old code charged to the model as a
    failure — but only when the model actually complied."""
    for n in names:
        v = kw.get(n)
        if v is not None:
            return int(float(v))
    return default


def _relation_ok(count: int, relation: str, target: int) -> bool:
    """Evaluate a relation. Unknown relations raise rather than pass.

    The English original ships "less than" as well as "at least"/"at most";
    a chain that handles two of three and falls through to ``return True``
    hands out free passes on a quarter of the length constraints.
    """
    rel = (relation or "at least").strip().lower()
    if rel == "at least":
        return count >= target
    if rel == "at most":
        return count <= target
    if rel == "less than":
        return count < target
    if rel == "more than":
        return count > target
    if rel in ("exactly", "equal to"):
        return count == target
    raise ValueError(f"unhandled relation {relation!r}")


def _paragraphs(text: str, divider: str = "***") -> list[str]:
    parts = text.split(divider) if divider in text else re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


# -- structure and formatting: language-neutral ----------------------------

@checker("punctuation:no_comma", Disposition.TRANSFERABLE)
def _no_comma(response: str, kw: dict, prompt: str) -> bool:
    return not re.search(r"[,،、，]", response)


@checker("detectable_format:number_bullet_lists", Disposition.TRANSFERABLE,
         note="exact count, per the English original")
def _bullets(response: str, kw: dict, prompt: str) -> bool:
    n = len(re.findall(r"^\s*[\*\-•]\s+\S", response, re.MULTILINE))
    return n == _int(kw, "num_bullets")


@checker("detectable_format:number_highlighted_sections", Disposition.TRANSFERABLE)
def _highlights(response: str, kw: dict, prompt: str) -> bool:
    n = len(re.findall(r"\*{1,2}[^\n\*]+\*{1,2}", response))
    return n >= _int(kw, "num_highlights")


@checker("detectable_format:json_format", Disposition.TRANSFERABLE)
def _json_format(response: str, kw: dict, prompt: str) -> bool:
    from ..extraction import extract_json
    return extract_json(response).ok


@checker("detectable_format:title", Disposition.TRANSFERABLE,
         note="<<...>> is unambiguous in Uzbek Latin")
def _title(response: str, kw: dict, prompt: str) -> bool:
    return bool(re.search(r"<<[^\n]+>>", response))


@checker("detectable_content:number_placeholders", Disposition.TRANSFERABLE)
def _placeholders(response: str, kw: dict, prompt: str) -> bool:
    return len(re.findall(r"\[[^\[\]]*\]", response)) >= _int(kw, "num_placeholders")


@checker("combination:two_responses", Disposition.TRANSFERABLE)
def _two_responses(response: str, kw: dict, prompt: str) -> bool:
    parts = [p.strip() for p in response.split("******") if p.strip()]
    # Two *different* responses: emitting the same text twice is not compliance.
    return len(parts) == 2 and normalize_for_match(parts[0]) != normalize_for_match(parts[1])


@checker("length_constraints:number_paragraphs", Disposition.TRANSFERABLE,
         note="exact count; the prompts name *** as the divider")
def _paragraph_count(response: str, kw: dict, prompt: str) -> bool:
    return len(_paragraphs(response)) == _int(kw, "num_paragraphs")


@checker("startend:quotation", Disposition.TRANSFERABLE)
def _quotation(response: str, kw: dict, prompt: str) -> bool:
    s = response.strip()
    return len(s) >= 2 and s[0] in '"«“' and s[-1] in '"»”'


# -- length: scored, but the target was calibrated for English -------------

@checker("length_constraints:number_words", Disposition.RECALIBRATE)
def _word_count(response: str, kw: dict, prompt: str) -> bool:
    return _relation_ok(count_words(response), kw.get("relation", "at least"),
                        _int(kw, "num_words"))


@checker("length_constraints:number_sentences", Disposition.RECALIBRATE)
def _sentence_count(response: str, kw: dict, prompt: str) -> bool:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", normalize(response).strip()) if s.strip()]
    return _relation_ok(len(sentences), kw.get("relation", "at least"),
                        _int(kw, "num_sentences"))


# -- constraints naming specific Uzbek strings -----------------------------

@checker("keywords:existence", Disposition.NEEDS_LOCALE, locale_keys=("keywords",),
         note="supply Uzbek stems; substring matching then covers inflected forms")
def _keywords_exist(response: str, kw: dict, prompt: str) -> bool:
    text = normalize_for_match(response)
    return all(normalize_for_match(k) in text for k in (kw.get("keywords") or []))


@checker("keywords:frequency", Disposition.NEEDS_LOCALE, locale_keys=("keyword",))
def _keyword_frequency(response: str, kw: dict, prompt: str) -> bool:
    key = normalize_for_match(kw.get("keyword") or "")
    if not key:
        raise ValueError("keywords:frequency requires a keyword")
    count = len(re.findall(re.escape(key), normalize_for_match(response)))
    return _relation_ok(count, kw.get("relation", "at least"), _int(kw, "frequency"))


@checker("keywords:forbidden_words", Disposition.NEEDS_LOCALE, locale_keys=("forbidden_words",),
         note="matches the stem plus any suffix, so inflected forms are caught")
def _forbidden(response: str, kw: dict, prompt: str) -> bool:
    text = normalize_for_match(response)
    for word in (kw.get("forbidden_words") or []):
        stem = normalize_for_match(word)
        if stem and re.search(rf"\b{re.escape(stem)}\w*", text):
            return False
    return True


@checker("startend:end_checker", Disposition.NEEDS_LOCALE, locale_keys=("end_phrase",))
def _ends_with(response: str, kw: dict, prompt: str) -> bool:
    phrase = normalize_for_match(kw.get("end_phrase") or "")
    if not phrase:
        raise ValueError("startend:end_checker requires an end_phrase")
    return normalize_for_match(response).rstrip(" .!?").endswith(phrase.rstrip(" .!?"))


@checker("combination:repeat_prompt", Disposition.NEEDS_LOCALE, locale_keys=("prompt_to_repeat",))
def _repeat_prompt(response: str, kw: dict, prompt: str) -> bool:
    target = normalize_for_match(kw.get("prompt_to_repeat") or "")
    if not target:
        raise ValueError("combination:repeat_prompt requires prompt_to_repeat")
    return normalize_for_match(response).startswith(target)


@checker("detectable_content:postscript", Disposition.NEEDS_LOCALE, locale_keys=("postscript_marker",))
def _postscript(response: str, kw: dict, prompt: str) -> bool:
    marker = (kw.get("postscript_marker") or "").strip()
    if not marker:
        raise ValueError("detectable_content:postscript requires a marker")
    # Dots required: an optional-dot pattern matches "psixolog" and "https".
    pattern = r"\b" + r"\s*".join(re.escape(c) + r"\." for c in marker.replace(".", ""))
    return bool(re.search(pattern, response, re.IGNORECASE))


@checker("detectable_format:multiple_sections", Disposition.NEEDS_LOCALE,
         locale_keys=("section_spliter", "section_splitter"))
def _sections(response: str, kw: dict, prompt: str) -> bool:
    splitter = kw.get("section_spliter") or kw.get("section_splitter") or ""
    if not splitter:
        raise ValueError("detectable_format:multiple_sections requires a splitter")
    pattern = rf"\s?{re.escape(splitter)}\s?\d+\s?"
    return len(re.split(pattern, response, flags=re.IGNORECASE)) - 1 >= _int(kw, "num_sections")


#: Upstream IFEval fixes this triple inside the checker rather than passing it
#: as a kwarg, which is why all ten rows arrive with an empty
#: ``allowed_responses``. Every Uzbek prompt in the dataset renders it the same
#: way, so this is read off the data, not invented.
CONSTRAINED_RESPONSES_UZ = (
    "Mening javobim ha.",
    "Mening javobim yoʻq.",
    "Mening javobim ehtimol.",
)


@checker("detectable_format:constrained_response", Disposition.TRANSFERABLE,
         locale_keys=("allowed_responses",),
         note="the yes/no/maybe triple is a constant of the instruction type, not "
              "a per-row argument; a row may still override it via kwargs_uz")
def _constrained(response: str, kw: dict, prompt: str) -> bool:
    allowed = kw.get("allowed_responses") or CONSTRAINED_RESPONSES_UZ
    # Containment, matching upstream IFEval. Requiring the whole response to
    # equal the phrase is stricter than the reference implementation and fails
    # any model that adds so much as a trailing newline of commentary — which
    # would make the Uzbek numbers look worse than English ones for a reason
    # that has nothing to do with the model.
    text = normalize_for_match(response)
    return any(normalize_for_match(a) in text for a in allowed)


@checker("length_constraints:nth_paragraph_first_word", Disposition.NEEDS_LOCALE,
         locale_keys=("first_word",))
def _nth_first_word(response: str, kw: dict, prompt: str) -> bool:
    want = normalize_for_match(kw.get("first_word") or "")
    if not want:
        raise ValueError("nth_paragraph_first_word requires first_word")
    paragraphs = _paragraphs(response)
    if len(paragraphs) != _int(kw, "num_paragraphs", default=len(paragraphs)):
        return False
    nth = _int(kw, "nth_paragraph", default=1)   # not num_paragraphs
    if not 1 <= nth <= len(paragraphs):
        return False
    words = paragraphs[nth - 1].split()
    return bool(words) and normalize_for_match(words[0]).strip(".,!?;:\"'") == want


@checker("language:response_language", Disposition.TRANSFERABLE,
         note="the kwarg is an ISO 639-1 code, identical in any prompt language; "
              "no item in this dataset requests Uzbek, so the detector never has "
              "to separate Uzbek from Turkish or Azerbaijani")
def _language(response: str, kw: dict, prompt: str) -> bool:
    want = (kw.get("language") or "").lower()
    if not want:
        raise ValueError("language:response_language requires a language")
    try:
        from lingua import LanguageDetectorBuilder
    except ImportError as exc:
        # Never silently pass: an unavailable detector excludes the constraint.
        raise RuntimeError("language:response_language needs `lingua-language-detector`") from exc
    detector = _lingua_detector(LanguageDetectorBuilder)
    detected = detector.detect_language_of(response)
    return bool(detected) and detected.iso_code_639_1.name.lower() == want


_DETECTOR = None


def _lingua_detector(builder):
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = builder.from_all_languages().with_preloaded_language_models().build()
    return _DETECTOR


# -- not meaningful in Uzbek -----------------------------------------------

def _dropped(reason: str) -> Callable[[str, dict, str], bool]:
    def fn(response: str, kw: dict, prompt: str) -> bool:
        raise NotImplementedError(reason)
    return fn


for _iid, _reason in {
    "change_case:english_lowercase":
        "the English original conditions on langdetect=='en', so it can never "
        "pass on Uzbek text; add an uzbek_lowercase variant instead",
    "change_case:english_capital":
        "same as english_lowercase — conditions on the response being English",
    "keywords:letter_frequency":
        "Uzbek Latin uses digraphs (sh, ch, ng, oʻ, gʻ), so a single-letter "
        "count is not a well-formed instruction for a native speaker",
    "change_case:capital_word_frequency":
        "depends on an English capitalisation idiom and an English tokeniser; "
        "Uzbek does not use ALL-CAPS emphasis the same way",
}.items():
    REGISTRY[_iid] = Checker(_dropped(_reason), Disposition.DROPPED, note=_reason)


def loose_variants(response: str) -> list[str]:
    """The eight response transformations of IFEval's official loose scoring."""
    def no_ast(t: str) -> str:
        return re.sub(r"\*+", "", t)

    def no_first(t: str) -> str:
        lines = t.split("\n")
        return "\n".join(lines[1:]) if len(lines) > 1 else t

    def no_last(t: str) -> str:
        lines = t.split("\n")
        return "\n".join(lines[:-1]) if len(lines) > 1 else t

    both = no_first(no_last(response))
    return [response, no_ast(response), no_first(response), no_last(response), both,
            no_ast(no_first(response)), no_ast(no_last(response)), no_ast(both)]
