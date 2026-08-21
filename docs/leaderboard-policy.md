# Leaderboard policy

What gets published, and what does not.

## Numbers come from runs

`site/results.json` is rebuilt from `runs/` by `idrockbench report`, entirely,
every time. There is no merge step and no hand-editing.

- A cell no run produced cannot appear.
- Deleting a run removes it from the board.
- The newest run per model wins; earlier runs stay on disk as history.

The previous leaderboard was maintained by hand. Twenty of its fifty cells had
no source run, one cell held a different metric pasted from the wrong column,
and one score sat at a fifth of its own random baseline. None of that is
possible now.

## Every row carries its provenance

Model id and revision, quantisation, licence, weights URL, provider,
temperature, seed, token budget per task, task versions, dataset content
hashes, harness version and commit, run date, and whether reasoning was
enabled. A number without these is not reproducible, and quantisation alone
moves scores by more than most model-to-model differences.

## Missing scores

**Never average over differing subsets.** A model missing any task in the suite
gets its per-task cells and no composite, no rank, and no medal. A mean over
three tasks and a mean over five are not comparable numbers, and presenting
them in one ranked column asserts otherwise.

## Composite score

Each task is normalised against its own random baseline before averaging:

```
normalised = max(0, (raw − chance) / (1 − chance)) × 100
```

Chance is 25% for DTM, 10% for a ten-option MMLU-Pro, 0% for generative tasks,
about 15.6% for partial-credit reasoning. Raw averaging would treat a coin flip
on one task as equal to real signal on another. Tasks are weighted equally, and
any deviation is published as an explicit vector.

## Intervals and ties

Every cell shows a 95% interval and its n. Models whose intervals overlap on
every shared task are marked tied. A rank is an estimate, not a fact — awarding
a medal for a gap inside the noise floor asserts something the data does not
support.

Ranks are computed once from the canonical descending composite and stored.
They are never recomputed from whatever column the reader last clicked.

## Cells that should not be trusted

Two flags, both published:

- **`provisional`** — under 80% of items were scorable. The number says more
  about extraction than about the model.
- **`at_or_below_chance`** — the score is at or below the random baseline. In
  practice this nearly always means a broken extractor, not a weak model, and
  it should be investigated before publication rather than after.

## Provenance tiers

| Badge | Meaning |
|---|---|
| `organiser-run` | We executed it, on our infrastructure, on held-out data |
| `verified` | Submitter ran it; we reproduced a random subset within tolerance |
| `self-reported` | Submitter's number, artefacts attached, not reproduced |

Self-reported rows are visually distinct, excluded from the default sort, and
never used for a "state of the art" claim.

## Versioning

Every published score names its task version and harness commit. Scores from
different task versions are never sorted together.

**A change to a task's scoring means re-scoring every model.** That costs
seconds — `idrockbench rescore runs/<id>` recomputes from stored responses with
no model calls — which is the reason per-item records are kept. A partially
re-scored board is a corrupt board.

Changes go in a dated changelog. Corrections are made in public: a corrected
row keeps its history rather than quietly changing.

## What we publish

- Full methodology, prompts, scoring code, harness version
- Per-model scores with intervals, n, coverage and diagnostics
- Per-item inputs and outputs for public datasets
- The exact command that reproduces each run

## What we withhold

- The held-out DTM items
- Raw responses on held-out items

The public DTM release exists so that anyone can check our work on data we do
not score against. The gap between public and held-out performance is itself a
contamination signal, and is worth publishing as a column.
