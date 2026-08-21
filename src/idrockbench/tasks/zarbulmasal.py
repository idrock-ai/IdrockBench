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

_SUFFIX = re.compile(
    r"^(lar)?"
    r"(imiz|ingiz|lari|im|ing|si|i)?"
    r"(niki|ning|dan|day|dek|ga|ka|qa|da|ni|cha)?$"
)


def _is_inflection(longer: str, stem: str) -> bool:
    if not longer.startswith(stem) or len(longer) <= len(stem):
        return False
    return bool(_SUFFIX.match(longer[len(stem):]))

_LEAD = re.compile(
    r"^\s*(javob|bu|men|menimcha|zarbulmasal(ning)?\s+javobi)\s*[:\-—]?\s*", re.IGNORECASE
)


def accepted_forms(row: dict) -> list[str]:
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
    name = "zarbulmasal"
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
