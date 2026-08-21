# Add a benchmark

A task is five methods. The runner handles concurrency, retries, checkpointing,
per-item records and diagnostics - a task only says *what to ask* and *how to
score it*.

## Worked example

A reading-comprehension benchmark: a passage, a question, a free-text answer.

```python
# src/idrockbench/tasks/reading_uz.py
"""Uzbek reading comprehension: answer a question about a passage."""

from __future__ import annotations

from typing import Any, Sequence

from ..core import Item
from ..extraction import Extraction, extract_last_line
from ..registry import register_task
from ..text.normalize import normalize, normalize_for_match
from .base import Task


@register_task
class ReadingTask(Task):
    name = "reading_uz"
    version = "1.0"          # bump on ANY change that can move a score
    description = "Reading comprehension in Uzbek."
    primary_metric = "accuracy"
    chance_level = 0.0       # free text: guessing gets you nothing
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
        """Invariants. Checked by `idrockbench validate` and in CI."""
        problems = []
        for i, row in enumerate(records):
            rid = row.get("id", i)
            if not str(row.get("answer", "")).strip():
                problems.append(f"row {rid}: no answer")
            if str(row.get("answer", "")) not in str(row.get("passage", "")):
                problems.append(f"row {rid}: answer does not appear in the passage")
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
        # Return an UNPARSED extraction rather than guessing. A fabricated
        # answer is worse than a recorded parse failure: it is indistinguishable
        # from a real one in the aggregate.
        return extract_last_line(response, strip_prefixes=("Javob",))

    def score(self, extraction: Extraction, item: Item) -> float:
        # normalize_for_match folds apostrophes and case, so a correct answer
        # is not marked wrong for typing ' instead of ʻ.
        return 1.0 if normalize_for_match(extraction.value or "") == \
                      normalize_for_match(item.gold) else 0.0

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("topic",)     # per-topic scores, each with its own n and CI
```

That is the whole task. `aggregate()` is inherited and gives mean accuracy with
a Wilson interval. Override it only for corpus-level metrics (see
`translation_uz.py`) or a multi-metric grid (see `ifeval_uz.py`).

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

No registration list to edit - `@register_task` plus a module in
`src/idrockbench/tasks/` is enough.

## Before it joins the published suite

Add it to `configs/suites/core.yaml` only when all of these hold:

1. **`idrockbench validate` is clean.**
2. **Golden tests exist** in `tests/`, covering: a correct answer in every
   apostrophe variant. A reasoning-model response with a `<think>` block.
   a truncated response. An empty response. A refusal. Each must assert the
   *status*, not only the score.
3. **`chance_level` is right.** It sets the below-chance warning and the
   normalisation used by the composite. Multiple choice: `1 / n_options`.
   Free text: `0.0`. Partial credit: measure what a content-free responder
   scores and use that.
4. **A dataset card exists** in `docs/data-cards/`.
5. **The scoring is documented** in `docs/methodology.md`.

## Multiple-choice shortcut

For a letter-answer benchmark, subclass `MultipleChoiceTask` and get
permutation, extraction, scoring and validation for free:

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

Returning `None` from `extract_gold_index` drops the row and reports it. Never
default to index 0 - that converts an annotation gap into silent noise that
still counts in the denominator.

## Versioning

`version` is not decoration. Bump it whenever a change can move a score -
prompt wording, extraction rules, scoring, the default dataset. Published
numbers name their task version, and numbers from different versions are never
sorted together. When you bump it, re-score the affected runs:

```bash
idrockbench rescore runs/<run-id>
```

That recomputes from stored responses with no model calls, so a scoring fix
costs seconds and old runs stay comparable instead of being abandoned.
