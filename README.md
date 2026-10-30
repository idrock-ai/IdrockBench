# IdrockBench

Evaluation harness and datasets for Uzbek-language LLMs, from the
[IDROCK AI Excellence Center](https://idrock.uz) at
[New Uzbekistan University](https://newuu.uz).

It covers school-subject questions from the national entrance exam (DTM),
logic puzzles, instruction following, translation, and Uzbek folk riddles.
Results for the models we have run so far are in [LEADERBOARD.md](LEADERBOARD.md).

## Quick start

```bash
pip install -e ".[all]"

idrockbench list                                 # tasks, providers and model configs
idrockbench validate                             # check the datasets
idrockbench run --model qwen35-9b --limit 10     # first 10 items per task
idrockbench run --model qwen35-9b --suite core   # full run
idrockbench report                               # rebuild LEADERBOARD.md from runs/
```

---

## Tasks

The baseline models are evaluated based on the following tasks:

| Task | What it measures | Items | Metric | Chance |
|---|---|---|---|---|
| `dtm` | School-subject knowledge from 2019 DTM entrance-exam material: ona tili, tarix, matematika, fizika | 2,062 public, 989 held out | accuracy | 25% |
| `reasoning_uz` | Zebra puzzles, spatial reasoning, web of lies | 100 | partial credit | ~16% |
| `translation_uz` | uz↔en and uz↔ru translation (FLORES-200 devtest) | 800 pairs | chrF++ | 0% |
| `ifeval_uz` | Verifiable instruction following | 541 | strict pass rate | 0% |
| `zarbulmasal` | Folk riddles and proverbs; the model writes the answer | 331 | exact match | 0% |
| `zarbulmasal_mc` | The same riddles as four-option multiple choice | 331 | accuracy | 25% |

The DTM and riddle items were written in Uzbek. `reasoning_uz` (LiveBench) and
`ifeval_uz` (IFEval) are translated from English.

## Scoring

[docs/methodology.md](docs/methodology.md) describes how each task is prompted
and scored. Three rules affect how the numbers read:

- If no answer can be extracted from a response, the item is marked `unparsed`.
  It is left out of the accuracy denominator and reported as `unparsed_rate`.
- `oʻ` and `gʻ` are written with U+02BB. Responses and references go through
  [`text/normalize.py`](src/idrockbench/text/normalize.py) first, so an ASCII
  `'` in their place is not marked wrong.
- Scores come with a 95% interval and n. If fewer than half the items of a task
  could be scored, the cell shows "withheld" and the reason.

## Runs

`idrockbench run` writes to `runs/<run-id>/`: a `manifest.json` with the model
settings, dataset SHA-256 and metrics, and a JSONL file with one row per item.
Manifests are committed; JSONL files are not. `idrockbench rescore runs/<run-id>`
recomputes the metrics from stored responses without calling the model again,
and `idrockbench show runs/<run-id>` prints a summary.

## Documentation

- [Benchmark a new model](docs/guides/adding-a-model.md)
- [Add a dataset](docs/guides/adding-a-dataset.md)
- [Add a benchmark](docs/guides/adding-a-benchmark.md)
- [Methodology](docs/methodology.md)
- [Leaderboard policy](docs/leaderboard-policy.md)
- [Dataset cards](docs/data-cards/): source, licence and known problems for each dataset

Changes to the datasets in `data/` are logged in
[`data/CHANGELOG.md`](data/CHANGELOG.md).

## Citation

```bibtex
@software{idrockbench2026,
  title  = {IdrockBench: An Evaluation Suite for Uzbek Large Language Models},
  author = {{IDROCK AI Excellence Center, New Uzbekistan University}},
  year   = {2026},
  url    = {https://github.com/idrock-ai/IdrockBench}
}
```

The DTM dataset is also published on
[IEEE DataPort, DOI 10.21227/e4h4-kp42](https://ieee-dataport.org/documents/uzbek-multiple-choice-question-dataset-large-language-model-evaluation).

## Licence

Code is MIT. Each dataset has its own licence; check
[`docs/data-cards/`](docs/data-cards/) before redistributing. The translation
set is derived from FLORES-200, which is CC BY-SA 4.0 and gated upstream, so it
cannot be relicensed.
