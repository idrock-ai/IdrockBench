# Leaderboard

Uzbek language model benchmark, IDROCK AI Excellence Center, New Uzbekistan University.
Rebuilt from `runs/` by `idrockbench report`; never edited by hand.

**14 models, 3 tracks.** All open weights, all organiser-run, all at temperature 0
with thinking disabled. Every score is the mean over its items; brackets are 95%
Wilson intervals. Models whose intervals overlap are not separable.

## Overall

Composite is the chance-normalised mean across all three tracks. A model missing
a track has no composite: a row is ranked only when every cell was measured.

| # | Model | Composite | DTM | Reasoning | Translation | Licence |
|---|---|---|---|---|---|---|
| 1 | Qwen3.6 27B | **57.1** | 50.34 | 87.70 | 51.98 | apache-2.0 |
| 2 | Gemma 4 12B | 34.9 | 37.99 | 46.13 | 51.33 | gemma |
| 3 | Qwen3.5 9B | 31.8 | 36.95 | 42.37 | 47.69 | apache-2.0 |
| 4 | Gemma 4 E4B | 26.5 | 32.83 | 33.93 | 47.39 | gemma |
| 5 | Qwen3.5 4B | 21.3 | 32.20 | 26.29 | 41.66 | apache-2.0 |
| 6 | Gemma 4 E2B | 15.6 | 29.53 | 14.15 | 40.89 | gemma |

## Measured but incomplete

Not ranked, because a composite over a missing track would be a different
quantity from the one above it. The cells that exist are real.

| Model | DTM | Reasoning | Translation | Why incomplete |
|---|---|---|---|---|
| Gemma 4 31B | **56.96** | - | **54.57** | reasoning not run |
| Qwen3.5 27B | 52.42 | withheld | 51.58 | reasoning coverage 4% |
| Gemma 4 26B | 48.54 | withheld | 53.32 | reasoning coverage 7% |
| Qwen3.5 35B | 47.77 | - | 50.37 | reasoning not run |
| Qwen3.8 27B | 45.88 | - | 51.01 | reasoning not run |
| Nemotron 3.5 Lightning 30B | 32.51 | - | 26.80 | reasoning not run |
| Qwen3.5 2B | - | 7.88 | - | manifest lost two task entries |
| Qwen3.5 0.8B | - | 1.42 | - | manifest lost two task entries |

A withheld cell means the model answered too few items to score honestly, not
that it scored zero. Coverage below 50% is never published.

## Different decoding protocol

Reported separately because it did not run the protocol above and cannot be
ranked against it. Denoising resolves tokens through a temperature schedule
(0.8 to 0.4) intrinsic to the method, so there is no greedy mode, output is
stochastic, and thinking is always on. Three independent replicates were run;
the figure is the mean and the spread is the observed range.

| Model | Active params | DTM | Reasoning | Translation |
|---|---|---|---|---|
| DiffusionGemma 26B-A4B | 3.8B of 25.2B | **43.92** (43.45-44.40) | **44.54** (43.38-45.62) | **49.75** (49.70-49.80) |

Sampling noise across replicates is under 1 point on DTM and 0.1 on translation,
well inside the item-sampling interval, so the mean is stable despite the
stochastic decoding. Notable on efficiency: it activates 3.8B parameters per
token and lands between Gemma 4 12B and the 27B tier.

## Tracks

| Track | Items | Metric | Chance |
|---|---|---|---|
| `dtm` | 2,062 | accuracy | 25% |
| `reasoning_uz` | 100 | partial credit | 15.6% |
| `translation_uz` | 800 | chrF++ | 0% |

`dtm` is the flagship: authored natively in Uzbek, not translated. At n=2,062 its
intervals are about +/-2 points. `reasoning_uz` at n=100 carries roughly +/-10,
so models within that margin are reported but not ordered.

Two further tracks exist and are not in the published suite: `zarbulmasal`
(331 Uzbek folk riddles, free text and multiple choice) and `ifeval_uz`
(instruction following, 73.6% constraint coverage).

## Reading this table

- **Chance matters.** DTM chance is 25%. A model at 25.8 has not demonstrated
  knowledge, and its interval says so.
- **Coverage matters.** A score is only as good as the share of items it was
  computed on; low-coverage cells are withheld rather than reported.
- **Overlapping intervals are ties.** Qwen3.5 35B (47.77) and Qwen3.8 27B (45.88)
  are not separable on DTM.
