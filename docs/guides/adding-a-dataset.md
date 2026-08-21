# Add a dataset

Two cases: new data for an existing task, or a new dataset format.

## New data for an existing task

Drop the file in `data/` and point a task config at it.

```bash
cp dtm_2020.json data/
```

```yaml
# configs/tasks/dtm_2020.yaml
task: dtm                    # the task implementation to use
dataset: dtm_2020.json       # resolved against data/, then the repo root
max_tokens: 2048
seed: 42
options:
  shuffle_options: true
```

```bash
idrockbench validate dtm_2020
idrockbench run --model gpt-4o --tasks dtm_2020
```

`validate` runs the task's declared invariants against the rows. For a
multiple-choice task that means: options parse, options are distinct and
non-empty, an answer key exists, and the key points at an option the model will
actually be shown. **Fix what it reports before running anything** - a run
against an invalid dataset produces numbers that look fine and mean nothing.

Supported formats: `.json` (array or `{"data": [...]}`), `.jsonl`, `.csv`,
`.tsv`. CSV is read with `utf-8-sig`, so a byte-order mark does not turn the
first column name into something no lookup will match.

## A HuggingFace dataset

```yaml
dataset: idrock/DTM_benchmark
split: test
dataset_revision: 3f9a1c2      # pin it
```

Pin the revision. An unpinned Hub dataset can change under a published number,
and the hash recorded in the manifest will no longer match anything you can
fetch.

## Repairing data

Never hand-edit files in `data/`. Add the repair to `tools/build_datasets.py`
and re-run it:

```bash
python tools/build_datasets.py
```

Hand edits are unreviewable, unreproducible, and lost the moment the source is
corrected upstream. The builder writes `data/CHANGELOG.md` describing every
change, and moves anything unscoreable to `data/quarantine/<dataset>.json` with
a reason.

Quarantine rather than delete. An item with a missing answer key needs a
subject expert, not a guess - and the previous runner's habit of defaulting a
missing key to option A put eight items of pure noise into every published DTM
score.

## A new file format

Register a loader. A new module in `src/idrockbench/data/` is discovered
automatically.

```python
# src/idrockbench/data/parquet.py
from pathlib import Path
from ..registry import register_loader

@register_loader(".parquet")
def load_parquet(path: Path) -> list[dict]:
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()
```

## Dataset cards

Every dataset in `data/` needs a card in `docs/data-cards/`. Copy an existing
one. It must state provenance, licence, what redistribution the licence allows,
known defects, and contamination exposure - whether the data is public enough
that models may have trained on it. A benchmark whose provenance is
undocumented cannot be cited, and cannot be defended.
