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
    order = list(range(len(options)))
    rng.shuffle(order)
    return [options[i] for i in order], order.index(gold_index)


def cyclic_variants(options: Sequence[str], gold_index: int) -> list[tuple[list[str], int]]:
    n = len(options)
    out = []
    for shift in range(n):
        order = [(i + shift) % n for i in range(n)]
        out.append(([options[i] for i in order], order.index(gold_index)))
    return out


class MultipleChoiceTask(Task):
    prompt_template: str = (
        "Quyidagi test savoliga javob bering.\n"
        "Faqat bitta harf yozing (A, B, C yoki D). Hech qanday izoh yozmang.\n\n"
        "Savol: {question}\n\n"
        "{choices}\n\n"
        "Javob:"
    )

    prompt_template_cot: str = (
        "Quyidagi test savoliga javob bering.\n"
        "Javobingizni «Javob: X» ko'rinishida yakunlang, bu yerda X — javob "
        "variantining harfi.\n\n"
        "Savol: {question}\n\n"
        "{choices}\n\n"
        "Javob:"
    )

    answer_only: bool = True

    shuffle_options: bool = True

    n_options: int = 4

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.chance_level = 1.0 / self.n_options
        if "answer_only" in self.options:
            self.answer_only = bool(self.options["answer_only"])
        if "shuffle_options" in self.options:
            self.shuffle_options = bool(self.options["shuffle_options"])

    def extract_options(self, row: dict) -> list[str]:
        raise NotImplementedError

    def extract_gold_index(self, row: dict, options: Sequence[str]) -> int | None:
        raise NotImplementedError

    def question_text(self, row: dict) -> str:
        return normalize_display(row.get("question", ""))

    def item_meta(self, row: dict) -> dict[str, Any]:
        return {}

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items: list[Item] = []
        rng = random.Random(self.seed)
        for i, row in enumerate(records):
            options = [normalize_display(o) for o in self.extract_options(row)]
            gold = self.extract_gold_index(row, options)
            if gold is None or not options or not (0 <= gold < len(options)):
                continue
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
