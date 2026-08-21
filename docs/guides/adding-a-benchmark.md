# Adding a benchmark

A task defines what to ask and how to score it. The runner handles concurrency, retries, checkpointing, per-item records and diagnostics.

## Example

A reading-comprehension task with a passage, a question and a free-text answer:

```python
# src/idrockbench/tasks/reading_uz.py
from __future__ import annotations

from typing import Sequence

from ..core import Item
from ..extraction import Extraction, extract_last_line
from ..registry import register_task
from ..text.normalize import normalize, normalize_for_match
from .base import Task


@register_task
class ReadingTask(Task):
    name = "reading_uz"
    version = "1.0"          # bump on any change that can move a score
    description = "Reading comprehension in Uzbek."
    primary_metric = "accuracy"
    chance_level = 0.0
    default_max_tokens = 512

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        return [
            Item(
                id=str(row.get("id", i)),
                payload={"passage": normalize(row["passage"]),
                         "question": normalize(row["question"])},
                gold=normalize(row["answer"]),
                meta={"topic": row.get("topic", "unknown")},
            )
            for i, row in enumerate(records)
            if row.get("passage") and row.get("question") and row.get("answer")
        ]

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems = []
        for i, row in enumerate(records):
            if str(row.get("answer", "")) not in str(row.get("passage", "")):
                problems.append(f"row {row.get('id', i)}: answer not in passage")
        return problems

    def build_prompt(self, item: Item) -> str:
        return (
            f"Matnni o'qing va savolga javob bering.\n"
            f"Faqat javobni yozing.\n\n"
            f"Matn: {item.payload['passage']}\n\n"
            f"Savol: {item.payload['question']}\n\n"
            f"Javob:"
        )

    def parse(self, response: str, item: Item) -> Extraction:
        return extract_last_line(response, strip_prefixes=("Javob",))

    def score(self, extraction: Extraction, item: Item) -> float:
        return 1.0 if normalize_for_match(extraction.value or "") == \
                      normalize_for_match(item.gold) else 0.0

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("topic",)
```

`parse` should return an unparsed extraction rather than a guess. `aggregate()` is inherited and gives mean accuracy with a Wilson interval. Override it only for corpus-level metrics, as in `translation_uz.py`, or a multi-metric grid, as in `ifeval_uz.py`.

## Wire it up

```yaml
# configs/tasks/reading_uz.yaml
task: reading_uz
dataset: reading_uz.json
max_tokens: 512
```

```bash
idrockbench validate reading_uz
idrockbench run --model stub --tasks reading_uz --limit 5
```

`@register_task` in a module under `src/idrockbench/tasks/` is all the registration needed.

## Before it joins the published suite

Add a task to `configs/suites/core.yaml` only when:

1. `idrockbench validate` is clean.
2. Scoring handles every apostrophe variant, `<think>` blocks, and truncated, empty and refused responses.
3. `chance_level` is right: `1 / n_options` for multiple choice, `0.0` for free text, and for partial credit the score of a content-free responder. It drives the below-chance warning and the composite.

## Multiple choice

For letter-answer tasks, subclass `MultipleChoiceTask` to get option shuffling, extraction, scoring and validation:

```python
from .mcq import MultipleChoiceTask

@register_task
class MyMCQ(MultipleChoiceTask):
    name = "my_mcq"
    version = "1.0"
    n_options = 4

    def extract_options(self, row):
        return [row[f"option_{c}"] for c in "ABCD"]

    def extract_gold_index(self, row, options):
        letter = str(row.get("answer", "")).strip().upper()
        return "ABCD".index(letter) if letter in "ABCD" else None
```

Returning `None` from `extract_gold_index` drops the row and reports it. Never default to index 0.

## Versioning

Bump `version` whenever a change can move a score: prompt wording, extraction, scoring or the default dataset. Scores from different versions are never sorted together. After a bump, re-score the affected runs from their stored responses:

```bash
idrockbench rescore runs/<model>/<run-id>
```
