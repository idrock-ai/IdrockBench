# Leaderboard

Uzbek language model benchmark, IDROCK AI Excellence Center, New Uzbekistan University.
Built from `runs/`. The first three tracks come from `idrockbench report`
over the `core` suite. The riddle columns come from the `zarb-*` runs, which
sit outside that suite and so outside the composite.

All open weights, all organiser-run. Ordered by DTM, the
flagship track, because it is the one measured for almost every model and the one
with the tightest intervals. Composite is the chance-normalised mean across all
three tracks and exists only where all three were measured.

| # | Model | Composite | DTM | Reasoning | Translation | Instructions | Riddle (recall) | Riddle (choice) | Licence |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Gemma 4 31B | 53.0 | 56.96 | 67.80 | 54.57 | 75.51 | 25.68 | 76.44 | gemma |
| 2 | Qwen3.5 27B | 52.4 | 52.42 | 73.78 | 51.58 | 75.96 | 9.37 | 70.69 | apache-2.0 |
| 3 | Qwen3.6 27B | 57.1 | 50.34 | 87.70 | 51.98 | 73.48 | 16.92 | 75.53 | apache-2.0 |
| 4 | Gemma 4 26B | 42.6 | 48.54 | 52.00 | 53.32 | 70.56 | 12.69 | 60.73 | gemma |
| 5 | Qwen3.5 35B | 47.2 | 47.77 | 66.89 | 50.37 | 65.17 | 6.95 | 61.63 | apache-2.0 |
| 6 | Qwen3.8 27B | 49.2 | 45.88 | 73.56 | 51.01 | 70.34 | 10.57 | 64.35 | apache-2.0 |
| 7 | DiffusionGemma 26B-A4B | 36.4 | 43.92 | 44.54 | 49.73 | - | 11.11 | 60.73 | apache-2.0 |
| 8 | Gemma 4 12B | 34.9 | 37.99 | 46.13 | 51.33 | 66.67 | 5.14 | 56.50 | gemma |
| 9 | Qwen3.5 9B | 31.8 | 36.95 | 42.37 | 47.69 | 56.18 | 1.81 | 48.34 | apache-2.0 |
| 10 | Gemma 4 E4B | 26.5 | 32.83 | 33.93 | 47.39 | 64.49 | 3.32 | 45.62 | gemma |
| 11 | Nemotron 3.5 Lightning 30B | 12.3 | 32.51 | 11.61 | 26.80 | 27.87 | 0.00 | 27.79 | nvidia-open-model |
| 12 | Qwen3.5 4B | 21.3 | 32.20 | 26.29 | 41.66 | 47.64 | 0.30 | 38.97 | apache-2.0 |
| 13 | Gemma 4 E2B | 15.6 | 29.53 | 14.15 | 40.89 | 52.81 | 0.00 | 36.86 | gemma |
| 14 | Qwen3.5 0.8B | 5.4 | 25.86 | 1.42 | 14.92 | 29.66 | 0.00 | 25.69 | apache-2.0 |
| 15 | Qwen3.5 2B | 10.4 | 25.80 | 7.88 | 30.07 | 34.83 | 0.00 | 21.75 | apache-2.0 |

`-` means not measured. `withheld` means the model answered too few items to score
honestly, not that it scored zero. Coverage below 50% is never published.

**Instructions** is IFEval prompt-level strict: the share of prompts where every
constraint was satisfied. Three further official figures are recorded per run
and omitted here for width. Every score is computed on the 605 constraints that
can be checked, out of 822. The other 217 still carry English arguments against
Uzbek prompts and are excluded rather than guessed at, identically for every
model, so the column compares fairly even though it is not a full measure of the
set. DiffusionGemma has no cell because it was not run on this track. Qwen3.5
Every model now has a reasoning cell. The six that were missing or withheld
were re-run once the context and GPU placement were corrected, including
Qwen3.5 27B, whose earlier 100.00 rested on 4 scored items and is now 73.78 on
82 of them. Qwen3.5 0.8B
and 2B have DTM and translation on disk but lost those entries from their run
manifests. DiffusionGemma decodes differently from every other row, explained
below. The remaining gaps are tracks that were not run.

DiffusionGemma's composite is computed the same way as the others, from the
mean of its three replicates, and places it seventh. Read it as a measure of
capability rather than a like-for-like ranking: it is the only row that decodes
stochastically with thinking always on, so a place or two either way is not
meaningful against the rows next to it.

Rank is by DTM and is not a claim of overall superiority. Qwen3.6 27B has the
highest composite but sits third on DTM, and the six rows without a composite are
missing a track rather than failing it.

## Instructions transfer, knowledge does not

The instruction column runs 20 to 40 points above DTM for almost every model.
Gemma 4 12B satisfies two-thirds of multi-constraint Uzbek prompts completely
while scoring 37.99 on Uzbek exam knowledge and 5.14 on riddles. Format
compliance is largely language-independent, so a model carries it into Uzbek
from wherever it learned it. Knowledge and cultural grounding do not travel the
same way.

Two orderings differ from the rest of the table. Qwen3.5 27B leads instructions
at 75.96 and Gemma 4 31B follows at 75.51, close enough to be a tie. Gemma 4 E4B
at 64.49 beats Qwen3.5 9B at 56.18 on less than half the parameters, the widest
family gap on any track here.

## Recognition is not recall

The two riddle columns run over the same 331 items. **Recall** gives the model
the riddle and asks it to name the answer, so chance is 0%. **Choice** gives it
four options, so chance is 25%.

The gap is the largest effect measured anywhere in this benchmark:

| Model | Recall | Choice | Gap |
|---|---:|---:|---:|
| Gemma 4 31B | 25.68 | 76.44 | 50.8 |
| Qwen3.6 27B | 16.92 | 75.53 | 58.6 |
| DiffusionGemma 26B-A4B | 11.11 | 60.73 | 49.6 |
| Qwen3.5 27B | 9.37 | 70.69 | 61.3 |
| Gemma 4 12B | 5.14 | 56.50 | 51.4 |
| Qwen3.5 4B | 0.30 | 38.97 | 38.7 |
| Qwen3.5 2B | 0.00 | 21.75 | 21.8 |

Four models score exactly zero on 331 riddles while scoring 22 to 37 percent on
the same items as multiple choice, which at a 25% chance level is close to
guessing. The best model available produces the right answer to about one riddle
in four.

The gap widens with capability rather than closing: 50.8 points at 31B against
21.8 at 2B, because recognition improves faster than recall does.

This is the one track with no English source to carry knowledge over from. A
translated benchmark measures what a model learned in English and kept through
translation. A riddle has to be known in Uzbek or not at all, and on this
evidence these models have shallow, recognition-only exposure to Uzbek folk
material.

Its riddle recall cell is computed on 297 of 331 items. A tenth of its
free-text responses could not be extracted, against zero for every
autoregressive model, which is a property of the channel-framed output rather
than of the answers. Those items are excluded rather than scored zero, so the
figure is not deflated by them, but it rests on a smaller sample than the rows
around it.

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
  computed on. Low-coverage cells are withheld rather than reported.
- **Overlapping intervals are ties.** Qwen3.5 35B (47.77) and Qwen3.8 27B (45.88)
  are not separable on DTM.
