# Leaderboard

Uzbek language model benchmark, IDROCK AI Excellence Center, New Uzbekistan University.
Rebuilt from `runs/` by `idrockbench report`; never edited by hand.

**15 models, 3 tracks.** All open weights, all organiser-run. Ordered by DTM, the
flagship track, because it is the one measured for almost every model and the one
with the tightest intervals. Composite is the chance-normalised mean across all
three tracks and exists only where all three were measured.

| # | Model | Composite | DTM | Reasoning | Translation | Licence |
|---:|---|---:|---:|---:|---:|---|
| 1 | Gemma 4 31B | - | **56.96** | - | **54.57** | gemma |
| 2 | Qwen3.5 27B | - | 52.42 | withheld | 51.58 | apache-2.0 |
| 3 | Qwen3.6 27B | **57.1** | 50.34 | **87.70** | 51.98 | apache-2.0 |
| 4 | Gemma 4 26B | - | 48.54 | withheld | 53.32 | gemma |
| 5 | Qwen3.5 35B | - | 47.77 | - | 50.37 | apache-2.0 |
| 6 | Qwen3.8 27B | - | 45.88 | - | 51.01 | apache-2.0 |
| 7 | DiffusionGemma 26B-A4B | - | 43.92 | 44.54 | 49.73 | apache-2.0 |
| 8 | Gemma 4 12B | 34.9 | 37.99 | 46.13 | 51.33 | gemma |
| 9 | Qwen3.5 9B | 31.8 | 36.95 | 42.37 | 47.69 | apache-2.0 |
| 10 | Gemma 4 E4B | 26.5 | 32.83 | 33.93 | 47.39 | gemma |
| 11 | Nemotron 3.5 Lightning 30B | - | 32.51 | - | 26.80 | nvidia-open-model |
| 12 | Qwen3.5 4B | 21.3 | 32.20 | 26.29 | 41.66 | apache-2.0 |
| 13 | Gemma 4 E2B | 15.6 | 29.53 | 14.15 | 40.89 | gemma |
| 14 | Qwen3.5 2B | - | - | 7.88 | - | apache-2.0 |
| 15 | Qwen3.5 0.8B | - | - | 1.42 | - | apache-2.0 |

`-` means not measured. `withheld` means the model answered too few items to score
honestly, not that it scored zero; coverage below 50% is never published. Qwen3.5
27B and Gemma 4 26B were withheld on reasoning at 4% and 7% coverage. Qwen3.5 0.8B
and 2B have DTM and translation on disk but lost those entries from their run
manifests. DiffusionGemma decodes differently from every other row, explained
below. The remaining gaps are tracks that were not run.

Rank is by DTM and is not a claim of overall superiority. Qwen3.6 27B has the
highest composite but sits third on DTM, and the six rows without a composite are
missing a track rather than failing it.

## DiffusionGemma runs a different protocol

Every other row decodes greedily at temperature 0 with thinking disabled.
DiffusionGemma resolves tokens through a temperature schedule (0.8 to 0.4)
intrinsic to denoising, so there is no greedy mode, its output is stochastic, and
thinking is always on. Its figures are the mean of three independent replicates:

| Track | Mean | Observed range |
|---|---:|---|
| DTM | 43.92 | 43.45 to 44.40 |
| Reasoning | 44.54 | 43.38 to 45.62 |
| Translation | 49.73 | 49.68 to 49.80 |

Sampling noise is under one point on DTM and 0.12 on translation, well inside the
item-sampling interval, so the mean is stable despite stochastic decoding. It
activates 3.8B of 25.2B parameters per token and still places seventh.

## Tracks

| Track | Items | Metric | Chance |
|---|---:|---|---:|
| `dtm` | 2,062 | accuracy | 25% |
| `reasoning_uz` | 100 | partial credit | 15.6% |
| `translation_uz` | 800 | chrF++ | 0% |

`dtm` is the flagship: authored natively in Uzbek, not translated. At n=2,062 its
intervals are about +/-2 points. `reasoning_uz` at n=100 carries roughly +/-10, so
models within that margin are reported but not ordered.

Two further tracks exist and are not yet in the published suite: `zarbulmasal`
(331 Uzbek folk riddles, free text and multiple choice) and `ifeval_uz`
(instruction following, 73.6% constraint coverage).

## Reading this table

- **Chance matters.** DTM chance is 25%. A model at 25.8 has not demonstrated
  knowledge, and its interval says so.
- **Coverage matters.** A score is only as good as the share of items it was
  computed on; low-coverage cells are withheld rather than reported.
- **Overlapping intervals are ties.** Qwen3.5 35B (47.77) and Qwen3.8 27B (45.88)
  are not separable on DTM.
