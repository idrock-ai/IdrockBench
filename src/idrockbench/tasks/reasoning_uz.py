from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from ..core import Item
from ..extraction import Extraction, ParseStatus, extract_bold, extract_tagged, strip_reasoning
from ..registry import register_task
from ..text.normalize import normalize_for_match, strip_apostrophes
from .base import Task

YES = {"ha", "xa", "yes", "ha'", "ҳа"}
NO = {"yoʻq", "yoq", "no", "yuq", "йўқ"}
UNKNOWN = {"nomaʻlum", "nomalum", "unknown", "noaniq", "номаълум"}


def normalize_yes_no(word: str) -> str | None:
    w = normalize_for_match(word).strip(".,;:!?()[]\"'*")
    if not w:
        return None
    for canon, vocab in (("yes", YES), ("no", NO), ("unknown", UNKNOWN)):
        if w in {normalize_for_match(v) for v in vocab}:
            return canon
        if strip_apostrophes(w) in {strip_apostrophes(v) for v in vocab}:
            return canon
    return None


_NEUTRAL = re.compile(r"^[\d\s,.\-/&+]+$")


def _is_language_neutral(gold: str) -> bool:
    return bool(_NEUTRAL.match(gold.strip()))


def score_slots(predicted: Sequence[str], gold: Sequence[str]) -> float:
    total = len(gold)
    if total == 0 or len(predicted) != total:
        return 0.0
    n_correct = sum(1 for p, g in zip(predicted, gold, strict=True) if p == g)
    return ((n_correct == total) + n_correct / total) / 2


@register_task
class ReasoningTask(Task):
    name = "reasoning"
    version = "2.0"
    description = "Logical, spatial and deductive reasoning in Uzbek (LiveBench-style)."
    chance_level = 0.156
    default_max_tokens = 4096

    SUPPORTED = ("zebra_puzzle", "spatial", "web_of_lies_v2")

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items: list[Item] = []
        for i, row in enumerate(records):
            task_type = row.get("task", "")
            if task_type not in self.SUPPORTED:
                continue
            turns = row.get("turns_in_uzbek") or row.get("turns") or []
            question = turns[0] if isinstance(turns, list) and turns else str(turns)
            gold = str(row.get("ground_truth_uzbek") or row.get("ground_truth") or "").strip()
            if not question or not gold:
                continue
            items.append(Item(
                id=str(row.get("question_id", i))[:16],
                payload={"question": question, "task": task_type},
                gold=gold,
                meta={"task": task_type},
            ))
        return items

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems: list[str] = []
        for i, row in enumerate(records):
            rid = str(row.get("question_id", i))[:12]
            gt_uz = str(row.get("ground_truth_uzbek", "") or "").strip()
            gt_en = str(row.get("ground_truth", "") or "").strip()
            if not gt_uz:
                problems.append(f"row {rid}: no Uzbek ground truth")
            elif (
                gt_uz == gt_en
                and row.get("task") == "zebra_puzzle"
                and gt_en
                and not _is_language_neutral(gt_en)
            ):
                problems.append(
                    f"row {rid}: Uzbek ground truth is identical to the English — "
                    f"untranslated, so an Uzbek answer can never match"
                )
            if gt_uz and gt_en and len(gt_uz.split(",")) != len(gt_en.split(",")):
                problems.append(f"row {rid}: Uzbek gold has a different slot count to English")
            if row.get("task") == "web_of_lies_v2" and gt_uz:
                bad = [p for p in gt_uz.split(",") if normalize_yes_no(p) is None]
                if bad:
                    problems.append(f"row {rid}: gold token(s) not yes/no/unknown: {bad}")
        return problems

    def build_prompt(self, item: Item) -> str:
        return item.payload["question"]

    def parse(self, response: str, item: Item) -> Extraction:
        task_type = item.payload["task"]
        n_slots = len(str(item.gold).split(","))

        tagged = extract_tagged(response)
        if tagged.ok:
            return tagged
        if task_type in ("web_of_lies_v2", "spatial") or n_slots == 1:
            bold = extract_bold(response)
            if bold.ok:
                return bold
        visible, dangling = strip_reasoning(response)
        lines = [ln.strip() for ln in visible.splitlines() if ln.strip()]
        if lines and lines[-1].count(",") == n_slots - 1:
            return Extraction(lines[-1], strategy="last-line", evidence=lines[-1][:120])
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "no-match", visible[-160:])

    def score(self, extraction: Extraction, item: Item) -> float:
        task_type = item.payload["task"]
        gold_parts = [p.strip() for p in str(item.gold).split(",")]
        pred_parts = [p.strip() for p in str(extraction.value or "").split(",")]

        if task_type == "web_of_lies_v2":
            gold_slots = [normalize_yes_no(g) for g in gold_parts]
            pred_slots = [normalize_yes_no(p) for p in pred_parts]
            if any(g is None for g in gold_slots):
                return 0.0
            return score_slots(pred_slots, gold_slots)

        if task_type == "spatial":
            gold = normalize_for_match(gold_parts[0])
            pred = normalize_for_match(str(extraction.value or ""))
            if pred == gold:
                return 1.0
            if gold and pred.startswith(gold) and len(pred) <= len(gold) + 4:
                return 1.0
            digits = re.findall(r"-?\d+(?:[.,]\d+)?", pred)
            return 1.0 if digits and digits[-1].replace(",", ".") == gold else 0.0

        return score_slots(
            [normalize_for_match(p) for p in pred_parts],
            [normalize_for_match(g) for g in gold_parts],
        )

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("task",)
