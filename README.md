# IdrockBench

An evaluation suite for Uzbek large language models.

[Leaderboard](https://eval.idrock.uz) · [Results](LEADERBOARD.md) · [Leaderboard policy](docs/leaderboard-policy.md) · [DTM dataset](https://ieee-dataport.org/documents/uzbek-multiple-choice-question-dataset-large-language-model-evaluation)

IdrockBench measures how well language models work in Uzbek. Its six tasks cover school-subject knowledge, logical reasoning, translation, instruction following and Uzbek folk riddles. The main task, DTM, uses questions written in Uzbek for the national university entrance exam.

Built by the [IDROCK AI Excellence Center](https://idrock.uz) at [New Uzbekistan University](https://newuu.uz).

## Tasks

| Task | Skill | Source | Items 
|---|---|---|---:
| `dtm` | Subject knowledge | DTM 2019 exam preparation materials | 2,062
| `reasoning_uz` | Logical reasoning | LiveBench, translated | 100 |
| `translation_uz` | Translation, uz↔en and uz↔ru | FLORES-200 devtest | 800 |
| `ifeval_uz` | Instruction following | IFEval, translated | 541 | 
| `zarbulmasal` | Riddle recall | Uzbek folk riddles | 331 |
| `zarbulmasal_mc` | Riddle recognition | Same riddles, four options | 331 



## Quick start

```bash
git clone https://github.com/idrock-ai/IdrockBench
cd IdrockBench
pip install -e ".[all]"

idrockbench validate                                  # check every dataset
idrockbench run --model stub --tasks dtm --limit 20   # offline smoke test
```

Then run the published suite and rebuild the leaderboard:

```bash
idrockbench run --model qwen3-32b --suite core
idrockbench report
```

## Repository layout

```text
configs/models/    one YAML file per model
configs/suites/    the task sets behind each leaderboard
data/              datasets
runs/              results
src/idrockbench/   the evaluation harness
site/              the leaderboard website
docs/              methodology
```

## Documentation

- [Adding a model](docs/guides/adding-a-model.md)
- [Adding a benchmark](docs/guides/adding-a-benchmark.md)
- [Leaderboard policy](docs/leaderboard-policy.md)

## Citation

```bibtex
@software{idrockbench2026,
  title  = {IdrockBench: An Evaluation Suite for Uzbek Large Language Models},
  author = {{IDROCK AI Excellence Center, New Uzbekistan University}},
  year   = {2026},
  url    = {https://github.com/idrock-ai/IdrockBench}
}
```

The DTM dataset is published separately on [IEEE DataPort, DOI 10.21227/e4h4-kp42](https://ieee-dataport.org/documents/uzbek-multiple-choice-question-dataset-large-language-model-evaluation).

## Licence

Code is MIT. Each dataset keeps its own licence and constraints, so check them before redistributing it. The FLORES-derived translation set is CC BY-SA 4.0 and cannot be relicensed.

## Contact

idrock@newuu.uz
