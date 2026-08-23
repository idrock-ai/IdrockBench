"""Shared multiple-choice machinery.

Every MCQ benchmark in this repo builds on :class:`MultipleChoiceTask`, so the
position-bias handling, validation and extraction rules are written once and
cannot drift apart between tasks.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any

from ..core import Item
from ..extraction import CHOICE_LETTERS, Extraction, extract_choice
from ..text.normalize import normalize_display
from .base import Task


def permute(
    options: Sequence[str],
    gold_index: int,
    rng: random.Random,
) -> tuple[list[str], int]:
    """Shuffle options and follow the gold answer to its new position.

    The remap tracks the gold *index*, never the gold *text*. Matching on text
    picks the first occurrence, so an item with two identical options gets an
    arbitrary one of them as gold and a correct reader is marked wrong on a
    coin flip.
    """
    order = list(range(len(options)))
    rng.shuffle(order)
    return [options[i] for i in order], order.index(gold_index)


def cyclic_variants(options: Sequence[str], gold_index: int) -> list[tuple[list[str], int]]:
    """All cyclic rotations of the options, with the gold index followed.

    Evaluating every rotation and averaging removes position bias exactly
    rather than in expectation, at N× the cost. Worth it for a small
    high-stakes set; use the seeded single shuffle for a large one.
    """
    n = len(options)
    out = []
    for shift in range(n):
        order = [(i + shift) % n for i in range(n)]
        out.append(([options[i] for i in order], order.index(gold_index)))
    return out


class MultipleChoiceTask(Task):
    """Base for letter-answer multiple-choice benchmarks.

    Subclasses supply :meth:`extract_options` and the prompt wording; this
    class handles permutation, extraction, scoring and validation.
    """

    #: Prompt template used when ``answer_only`` is set. ``{question}`` and
    #: ``{choices}`` are substituted.
    prompt_template: str = (
        "Quyidagi test savoliga javob bering.\n"
        "Faqat bitta harf yozing (A, B, C yoki D). Hech qanday izoh yozmang.\n\n"
        "Savol: {question}\n\n"
        "{choices}\n\n"
        "Javob:"
    )

    #: Prompt used when ``answer_only`` is disabled: the model may reason first
    #: and must commit at the end.
    prompt_template_cot: str = (
        "Quyidagi test savoliga javob bering.\n"
        "Javobingizni «Javob: X» ko'rinishida yakunlang, bu yerda X — javob "
        "variantining harfi.\n\n"
        "Savol: {question}\n\n"
        "{choices}\n\n"
        "Javob:"
    )

    #: Direct-answer protocol: the model replies with a letter and nothing else.
    #:
    #: This is a protocol choice, not a tuning knob, and it must be stated
    #: wherever the score is published — it measures recall rather than recall
    #: plus reasoning, and the two are not comparable. Set it per task config,
    #: never per model: applying different protocols to different models on the
    #: same leaderboard column is the thing that makes a column meaningless.
    #:
    #: It is also what makes the benchmark affordable. Measured on qwen3.5:9b,
    #: a DTM item costs 2 tokens and 0.4s direct, against 427 tokens and 11.5s
    #: when the model reasons first — the difference between minutes and a day
    #: per model.
    answer_only: bool = True

    #: Permute options to neutralise position bias. Seeded, so reproducible.
    shuffle_options: bool = True

    #: Number of options, used for the chance level and to bound extraction.
    n_options: int = 4

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.chance_level = 1.0 / self.n_options
        if "answer_only" in self.options:
            self.answer_only = bool(self.options["answer_only"])
        if "shuffle_options" in self.options:
            self.shuffle_options = bool(self.options["shuffle_options"])

    # -- subclass hooks -----------------------------------------------------

    def extract_options(self, row: dict) -> list[str]:
        """Return the option texts for a raw dataset row."""
        raise NotImplementedError

    def extract_gold_index(self, row: dict, options: Sequence[str]) -> int | None:
        """Return the 0-based index of the correct option, or ``None`` if the
        row has no usable key. Returning ``None`` drops the row — it must never
        default to option A, which turns an annotation gap into silent noise."""
        raise NotImplementedError

    def question_text(self, row: dict) -> str:
        return normalize_display(row.get("question", ""))

    def item_meta(self, row: dict) -> dict[str, Any]:
        return {}

    # -- Task interface -----------------------------------------------------

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items: list[Item] = []
        rng = random.Random(self.seed)
        for i, row in enumerate(records):
            options = [normalize_display(o) for o in self.extract_options(row)]
            gold = self.extract_gold_index(row, options)
            if gold is None or not options or not (0 <= gold < len(options)):
                continue  # reported by validate(); never silently mis-keyed
            if self.shuffle_options:
                options, gold = permute(options, gold, rng)
            items.append(Item(
                id=str(row.get("id", row.get("question_id", i))),
                payload={"question": self.question_text(row), "options": options},
                gold=CHOICE_LETTERS[gold],
                meta={**self.item_meta(row), "n_options": len(options)},
            ))
        return items

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems: list[str] = []
        for i, row in enumerate(records):
            rid = row.get("id", row.get("question_id", i))
            try:
                options = [normalize_display(o) for o in self.extract_options(row)]
            except Exception as exc:  # noqa: BLE001
                problems.append(f"row {rid}: options unparseable ({exc})")
                continue
            if not options:
                problems.append(f"row {rid}: no options")
                continue
            if any(not o.strip() for o in options):
                problems.append(f"row {rid}: empty option text")
            if len(set(options)) != len(options):
                problems.append(
                    f"row {rid}: duplicate option text — the item is unanswerable "
                    f"because two choices are the same"
                )
            gold = self.extract_gold_index(row, options)
            if gold is None:
                problems.append(f"row {rid}: missing or invalid answer key")
            elif not 0 <= gold < len(options):
                problems.append(
                    f"row {rid}: answer index {gold} is outside the {len(options)} "
                    f"options — the correct answer would never be shown to the model"
                )
        return problems

    def build_prompt(self, item: Item) -> str:
        choices = "\n".join(
            f"{CHOICE_LETTERS[i]}) {opt}" for i, opt in enumerate(item.payload["options"])
        )
        template = self.prompt_template if self.answer_only else self.prompt_template_cot
        return template.format(question=item.payload["question"], choices=choices)

    def parse(self, response: str, item: Item) -> Extraction:
        return extract_choice(response, len(item.payload["options"]))

    def score(self, extraction: Extraction, item: Item) -> float:
        return 1.0 if extraction.value == item.gold else 0.0
