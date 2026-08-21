"""UzDTM — Uzbek university-entrance exam questions.

The flagship track: natively authored Uzbek items from 2019 State Test Centre
(DTM) preparation materials, across ona tili, tarix, matematika and fizika.
Native authorship is what makes this a test of Uzbek knowledge rather than a
translated test of Western knowledge.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..registry import register_task
from ..text.normalize import normalize
from .mcq import MultipleChoiceTask

_LETTERS = "ABCD"


@register_task
class DTMTask(MultipleChoiceTask):
    name = "dtm"
    version = "2.1"
    description = "Uzbek university-entrance exam questions (DTM 2019), four options."
    n_options = 4
    default_max_tokens = 2048

    def extract_options(self, row: dict) -> list[str]:
        return [str(row.get(f"option_{c}", "") or "") for c in _LETTERS]

    def extract_gold_index(self, row: dict, options: Sequence[str]) -> int | None:
        raw = row.get("answer", row.get("correct_answer"))
        if raw is None:
            return None
        letter = str(raw).strip().upper()
        return _LETTERS.index(letter) if letter in _LETTERS else None

    def item_meta(self, row: dict) -> dict[str, Any]:
        return {
            "subject": normalize(str(row.get("subject", "unknown"))),
            "topic": normalize(str(row.get("topic", ""))),
        }

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("subject",)
