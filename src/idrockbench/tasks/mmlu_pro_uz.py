"""MMLU-Pro-uz — professional-level knowledge questions, translated to Uzbek.

Ten options rather than four, so chance is 10%. Options are stored as JSON
arrays: the previous CSV kept a NumPy ``repr()`` that only line-wraps past ~75
characters, which collapsed most items to one or two garbled options and put
the correct answer outside what the model was shown for 73.5% of the set.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from ..registry import register_task
from ..text.normalize import normalize, normalize_display
from .mcq import MultipleChoiceTask


def parse_options(raw: Any) -> list[str]:
    """Parse an options cell.

    Accepts a real list, a JSON array, or the legacy NumPy ``repr()`` form, and
    parses the legacy form by quoted span rather than by newline so that
    element count no longer depends on line width.
    """
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, ValueError):
        pass
    import re
    quoted = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", text)
    if quoted:
        return [(a or b).replace("\\'", "'").replace('\\"', '"') for a, b in quoted]
    return [p.strip() for p in text.strip("[]").split("\n") if p.strip()]


@register_task
class MMLUProUzTask(MultipleChoiceTask):
    name = "mmlu_pro_uz"
    version = "2.1"
    description = "Professional-level multitask knowledge in Uzbek, ten options."
    n_options = 10
    default_max_tokens = 4096

    def extract_options(self, row: dict) -> list[str]:
        return parse_options(row.get("options_uzb") or row.get("options"))

    def extract_gold_index(self, row: dict, options: Sequence[str]) -> int | None:
        idx = row.get("answer_index")
        if idx not in (None, ""):
            try:
                return int(idx)
            except (TypeError, ValueError):
                return None
        letter = str(row.get("answer", "")).strip().upper()
        from ..extraction import CHOICE_LETTERS
        return CHOICE_LETTERS.index(letter) if letter in CHOICE_LETTERS else None

    def question_text(self, row: dict) -> str:
        return normalize_display(row.get("question_uzb") or row.get("question", ""))

    def item_meta(self, row: dict) -> dict[str, Any]:
        return {"category": str(row.get("category", "unknown"))}

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("category",)

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems = list(super().validate(records))
        for i, row in enumerate(records):
            rid = row.get("question_id", i)
            en = parse_options(row.get("options"))
            uz = parse_options(row.get("options_uzb"))
            if en and uz and len(en) != len(uz):
                problems.append(
                    f"row {rid}: {len(en)} English options but {len(uz)} Uzbek — "
                    f"answer_index refers to the English list, so the key is shifted"
                )
            q_en = str(row.get("question", ""))
            q_uz = str(row.get("question_uzb", ""))
            if q_en and q_uz and len(q_uz) < 0.35 * len(q_en):
                problems.append(
                    f"row {rid}: Uzbek question is {len(q_uz)} chars against "
                    f"{len(q_en)} English — likely a truncated or failed translation"
                )
        return problems
