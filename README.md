# IdrockBench

**An evaluation suite for Uzbek-language large language models.**
Built by the [IDROCK AI Excellence Center](https://idrock.uz) at [New Uzbekistan University](https://newuu.uz).

Uzbek has around 35 million speakers and almost no serious LLM evaluation. IdrockBench measures what a model can actually do *in Uzbek* - school-subject knowledge from national exam material, logical reasoning, instruction following, and translation - and publishes every number with the interval, the sample size, and the run that produced it.

```bash
pip install -e ".[all]"

idrockbench list                                  # what is available
idrockbench validate                              # check the datasets
idrockbench run --model gpt-4o --suite core       # evaluate a model
idrockbench report                                # rebuild the leaderboard
```

---

## What makes a number here trustworthy

**A parse failure is not a wrong answer.** Responses that cannot be scored are
excluded from the denominator and reported in their own rate, never counted as
zero.

**Correct Uzbek is never penalised.** Uzbek writes `oʻ` and `gʻ` with U+02BB, a
letter, but models often type an ASCII `'`, which is punctuation. Everything
compares through [`text/normalize.py`](src/idrockbench/text/normalize.py) first.

**A thin score is withheld.** Below 50% coverage the reason is published instead
of the number.

**Every score is reproducible.** Each run records the dataset hash, the settings
and one row per item, so a scoring fix costs a re-score rather than a re-run.

**Intervals, not point estimates.** Every cell carries a 95% interval and its n.
Models whose intervals overlap are tied, not ranked.

---

## Tasks

| Task | What it measures | Items | Metric | Chance |
|---|---|---|---|---|
| `dtm` | Uzbek school-subject knowledge from 2019 national entrance-exam material - ona tili, tarix, matematika, fizika | 2,062 public (989 held out) | accuracy | 25% |
| `reasoning_uz` | Zebra puzzles, spatial reasoning, web of lies | 100 | partial credit | ~16% |
| `translation_uz` | uz↔en and uz↔ru translation (FLORES-200 devtest) | 800 pairs | chrF++ | 0% |
| `ifeval_uz` | Verifiable instruction following | 541 | strict pass rate | 0% |
| `mmlu_pro_uz` | Professional-level knowledge, ten options | 174 | accuracy | 10% |
| `zarbulmasal` | Uzbek folk riddles and zarbulmasal - free text, the model must name the answer | 331 | exact match | 0% |
| `zarbulmasal_mc` | The same riddles as four-way multiple choice - recognition rather than recall | 331 | accuracy | 25% |

`dtm` is the flagship: natively authored in Uzbek, not translated, and held out. It is the only track that measures Uzbek knowledge rather than a translated test of someone else's curriculum.

---

## Guides

- **[Benchmark a new model](docs/guides/adding-a-model.md)** - one YAML file
- **[Add a dataset](docs/guides/adding-a-dataset.md)** - point a task at new data
- **[Add a benchmark](docs/guides/adding-a-benchmark.md)** - five methods, worked example
- **[Methodology](docs/methodology.md)** - how each task is prompted and scored
- **[Leaderboard policy](docs/leaderboard-policy.md)** - what gets published, and what does not
- **[Dataset cards](docs/data-cards/)** - provenance, licence and limitations per dataset

---

## Data

Datasets in `data/` are **built, not hand-edited**:

```bash
python tools/build_datasets.py
```

Every repair lives in that script and is described in `data/CHANGELOG.md`. Items that cannot be scored fairly - a missing answer key, two identical options, a failed translation - go to `data/quarantine/` with a reason rather than being guessed at or silently dropped. Several need a subject expert to confirm a key, after which they return to the benchmark.

---

## Citation

```bibtex
@software{idrockbench2026,
  title  = {IdrockBench: An Evaluation Suite for Uzbek Large Language Models},
  author = {{IDROCK AI Excellence Center, New Uzbekistan University}},
  year   = {2026},
  url    = {https://github.com/idrock-ai/IdrockBench}
}
```

The underlying DTM dataset is published separately: [IEEE DataPort, DOI 10.21227/e4h4-kp42](https://ieee-dataport.org/documents/uzbek-multiple-choice-question-dataset-large-language-model-evaluation).

## Licence

Code is MIT. Datasets carry their own licences and constraints - see [`docs/data-cards/`](docs/data-cards/) before redistributing anything. The FLORES-derived translation set is CC BY-SA 4.0 and gated upstream. It cannot be relicensed.
