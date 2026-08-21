"""Zarbulmasal — Uzbek traditional riddles.

The only track here that cannot be reached by translating English knowledge. A
riddle needs Uzbek metaphor, Uzbek objects and Uzbek daily life, so it measures
cultural grounding rather than curriculum recall — the gap every regional
benchmark is criticised for leaving open.

Two formats over the same items, and the difference between them is the point:

* **free text** — the model names the answer. The real task.
* **multiple choice** — the model picks from four. Recognition, not generation.

A model that recognises *olma* in a list but cannot produce it has memorised
nothing useful, and only running both reveals that.

Scoring free-text Uzbek is where this task can quietly break. Uzbek is
agglutinative, so one answer has many surface forms — ``olma``, ``olmani``,
``olmalar``, ``olma daraxti``. Each item therefore carries a set of accepted
answers rather than one gold string, and matching allows a bounded inflectional
suffix on top of an accepted stem. Everything runs through the shared
apostrophe normalisation first; without it ``yoʻq`` and ``yo'q`` are different
strings, which is exactly how the old reasoning scorer scored correct Uzbek
below random.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from ..core import Item
from ..extraction import CHOICE_LETTERS, Extraction, extract_choice, extract_last_line
from ..registry import register_task
from ..text.normalize import (
    normalize,
    normalize_display,
    normalize_for_match,
    strip_apostrophes,
    words,
)
from .base import Task
from .mcq import permute

#: Uzbek inflectional suffixes a correct answer may carry, as a closed set:
#: optional plural, then possessive, then case.
#:
#: A length cap will not do. Allowing "any short ending" accepts `ko'zoynak`
#: (spectacles) as an inflection of `ko'z` (eye) — a different word, credited as
#: correct. That is the substring-matching flaw that let the old reasoning
#: scorer award full marks to an answer negating every slot. The suffix must be
#: a suffix, not merely short.
_SUFFIX = re.compile(
    r"^(lar)?"
    r"(imiz|ingiz|lari|im|ing|si|i)?"
    r"(niki|ning|dan|day|dek|ga|ka|qa|da|ni|cha)?$"
)


def _is_inflection(longer: str, stem: str) -> bool:
    """True if ``longer`` is ``stem`` plus Uzbek inflectional endings."""
    if not longer.startswith(stem) or len(longer) <= len(stem):
        return False
    return bool(_SUFFIX.match(longer[len(stem):]))

#: Filler a model wraps around a one-word answer.
_LEAD = re.compile(
    r"^\s*(javob|bu|men|menimcha|zarbulmasal(ning)?\s+javobi)\s*[:\-—]?\s*", re.IGNORECASE
)


def accepted_forms(row: dict) -> list[str]:
    """Every answer form an item accepts.

    ``accepted`` is the authority; ``answer`` is the canonical form shown in
    reports. A single gold string cannot express a riddle with two legitimate
    solutions, and forcing one would mark correct answers wrong.
    """
    forms = list(row.get("accepted") or [])
    if row.get("answer"):
        forms.append(row["answer"])
    seen, out = set(), []
    for f in forms:
        key = normalize_for_match(f)
        if key and key not in seen:
            seen.add(key)
            out.append(normalize(f))
    return out


def matches(answer: str, accepted: Sequence[str]) -> bool:
    """Whether a free-text answer counts as correct.

    Exact match after normalisation, or an accepted form plus a short
    inflectional suffix. Apostrophe-stripped forms are compared too, so a model
    writing ``yoq`` for ``yoʻq`` is not punished for an orthographic slip.
    """
    got = normalize_for_match(_LEAD.sub("", answer or "")).strip(" .!?\"'«»")
    if not got:
        return False
    bare_got = strip_apostrophes(got)
    for form in accepted:
        want = normalize_for_match(form)
        if got == want or bare_got == strip_apostrophes(want):
            return True
        for a, b in ((got, want), (bare_got, strip_apostrophes(want))):
            if _is_inflection(a, b):
                return True
    return False


class _ZarbulmasalBase(Task):
    name = ""
    version = "1.0"
    description = "Uzbek traditional riddles (zarbulmasal)."

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems: list[str] = []
        seen: dict[str, Any] = {}
        for i, row in enumerate(records):
            rid = row.get("id", i)
            if not str(row.get("riddle", "")).strip():
                problems.append(f"row {rid}: no riddle text")
            if not accepted_forms(row):
                problems.append(f"row {rid}: no accepted answer")
            key = normalize_for_match(row.get("riddle", ""))
            if key in seen:
                problems.append(f"row {rid}: duplicate of {seen[key]}")
            seen[key] = rid
            for d in row.get("distractors") or []:
                if matches(d, accepted_forms(row)):
                    problems.append(
                        f"row {rid}: distractor {d!r} matches the accepted answer"
                    )
            # An accepted answer that already appears as a word in the riddle
            # lets a model score by copying the prompt, which measures nothing.
            # Real example caught in the harvest: "Koʻk kosani toʻntardim"
            # (answer osmon) accepted "koʻk" — a word sitting in the question.
            riddle_words = {normalize_for_match(w) for w in words(row.get("riddle", ""))}
            for a in accepted_forms(row):
                if normalize_for_match(a) in riddle_words:
                    problems.append(
                        f"row {rid}: accepted answer {a!r} appears in the riddle "
                        f"text, so it can be scored correct by copying"
                    )
                    break
        return problems

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("theme", "difficulty")


@register_task
class ZarbulmasalTask(_ZarbulmasalBase):
    """Free-text: the model must name the answer itself."""

    name = "zarbulmasal"
    #: Guessing a specific Uzbek noun from nothing is not a strategy, so the
    #: floor is zero rather than 1/n.
    chance_level = 0.0
    default_max_tokens = 256

    PROMPT = (
        "Quyidagi o'zbek zarbulmasalini yeching.\n"
        "Faqat javobni bir yoki ikki so'z bilan yozing. Izoh bermang.\n\n"
        "Zarbulmasal: {riddle}\n\n"
        "Javob:"
    )

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items = []
        for i, row in enumerate(records):
            accepted = accepted_forms(row)
            if not accepted or not str(row.get("riddle", "")).strip():
                continue
            items.append(Item(
                id=str(row.get("id", i)),
                payload={"riddle": normalize_display(row["riddle"])},
                gold=accepted,
                meta={"theme": row.get("theme", "unknown"),
                      "difficulty": row.get("difficulty", "unknown"),
                      "canonical": accepted[0]},
            ))
        return items

    def build_prompt(self, item: Item) -> str:
        return self.PROMPT.format(riddle=item.payload["riddle"])

    def parse(self, response: str, item: Item) -> Extraction:
        return extract_last_line(response, strip_prefixes=("Javob", "Answer"))

    def score(self, extraction: Extraction, item: Item) -> float:
        return 1.0 if matches(extraction.value or "", item.gold) else 0.0


@register_task
class ZarbulmasalChoiceTask(_ZarbulmasalBase):
    """Multiple choice over the same riddles: recognition rather than recall.

    Scored beside the free-text task deliberately. The gap between them
    separates a model that knows the answer from one that merely recognises it.
    """

    name = "zarbulmasal_mc"
    chance_level = 0.25
    default_max_tokens = 256

    PROMPT = (
        "Quyidagi o'zbek zarbulmasalining javobini toping.\n"
        "Faqat bitta harf yozing (A, B, C yoki D). Hech qanday izoh yozmang.\n\n"
        "Zarbulmasal: {riddle}\n\n"
        "{choices}\n\n"
        "Javob:"
    )

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        import random

        rng = random.Random(self.seed)
        items = []
        for i, row in enumerate(records):
            accepted = accepted_forms(row)
            distractors = [normalize_display(d) for d in (row.get("distractors") or [])]
            # Needs three distinct, plausible wrong answers. A row without them
            # is skipped rather than padded — a made-up distractor makes the
            # item easier in a way that never shows up in the score.
            if not accepted or len(distractors) < 3:
                continue
            options = [normalize_display(accepted[0]), *distractors[:3]]
            if len({normalize_for_match(o) for o in options}) < 4:
                continue
            options, gold = permute(options, 0, rng)
            items.append(Item(
                id=str(row.get("id", i)),
                payload={"riddle": normalize_display(row["riddle"]), "options": options},
                gold=CHOICE_LETTERS[gold],
                meta={"theme": row.get("theme", "unknown"),
                      "difficulty": row.get("difficulty", "unknown"),
                      "n_options": len(options)},
            ))
        return items

    def build_prompt(self, item: Item) -> str:
        choices = "\n".join(
            f"{CHOICE_LETTERS[i]}) {o}" for i, o in enumerate(item.payload["options"])
        )
        return self.PROMPT.format(riddle=item.payload["riddle"], choices=choices)

    def parse(self, response: str, item: Item) -> Extraction:
        return extract_choice(response, len(item.payload["options"]))

    def score(self, extraction: Extraction, item: Item) -> float:
        return 1.0 if extraction.value == item.gold else 0.0
