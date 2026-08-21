# Leaderboard policy

## Where the numbers come from

`site/results.json` and the table in `LEADERBOARD.md` are rebuilt from `runs/` by `idrockbench report`. Neither is edited by hand, so a cell that no run produced cannot appear, and deleting a run removes it from the board.

For each model and task the newest run is used. Repeated runs on the same data and task version are averaged, and their range is published.

## Provenance

Every run manifest records the model id and revision, quantisation, licence, weights URL, provider, temperature, seed, token budget per task, task versions, dataset hashes, harness version and commit, run date, and whether reasoning was enabled.

## Composite score

Each task is normalised against its random baseline, and the tasks are averaged with equal weight:

```
normalised = max(0, (raw − chance) / (1 − chance)) × 100
```

Chance is 25% for four-option multiple choice, about 15.6% for partial-credit reasoning, and 0% for generative tasks. A model missing a task gets a composite over the tasks it has, marked as partial with the track count shown.

## Intervals and ranks

Every cell carries a 95% Wilson interval and its n. Models whose intervals overlap share a rank. Ranks are computed once from the composite and do not change when a reader sorts by another column.

## Flagged cells

| Flag | Meaning |
|---|---|
| `provisional` | Under 80% of items were scorable |
| `withheld` | Under 50% of items were scorable, so no score is published |
| `at_or_below_chance` | The score is at or below the random baseline, which usually points to an extraction problem |

## Versioning

Every score names its task version and harness commit, and scores from different task versions are never sorted together. When scoring changes, every model is re-scored from its stored responses:

```bash
idrockbench rescore runs/<model>/<run-id>
```

## What is published

All rows are run by the organisers. Each model is published with its scores, intervals, n, coverage and diagnostics, and with the manifest of the run that produced them.
