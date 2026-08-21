# Methodology

How each task is prompted, parsed and scored. Anything that can move a number
is stated here, and anything stated here is recorded in every run manifest.

## Shared rules

**Normalisation.** Every comparison runs on normalised text: NFC, then all
apostrophe variants folded to U+02BB. Uzbek Latin writes `oʻ` and `gʻ` with
U+02BB, a *letter* (Unicode category Lm); models routinely type ASCII `'` or
curly `'` (punctuation). Unnormalised, the same correct sentence scores 100 or
20 BLEU depending on which key was pressed, and `\b[A-J]\b` extracts G from
`to'g'ri` — the Uzbek word for "correct".

**Outcomes.** Every item ends in exactly one state:

| Status | Meaning | In the denominator? |
|---|---|---|
| `ok` | An answer was extracted | yes |
| `unparsed` | Responded, no answer found | **no**, reported as `unparsed_rate` |
| `truncated` | Hit the token limit | **no**, reported as `truncated_rate` |
| `error` | Request failed after retries | **no**, reported as `error_rate` |
| `refusal` | Model declined | yes, scored 0 — a refusal is performance |

The first four exist because a broken extractor and a weak model produce the
same headline number when they are collapsed. Read the rates before the score.

**Sampling.** Temperature 0, single run, no best-of-N. Recorded per run.

**Intervals.** 95% Wilson for accuracy-style metrics; segment bootstrap (500
resamples) for corpus translation metrics. Reported on every cell and every
breakdown.

**Composite.** Each task is normalised against its own random baseline —
`(raw − chance) / (1 − chance)`, clamped at 0 — then averaged with equal
weight. Shown only for models with a complete run over the suite.

---

## `dtm` — Uzbek entrance-exam knowledge

**Data.** 989 four-option items from 2019 State Test Centre preparation
material: ona tili, tarix, matematika, fizika. Natively authored in Uzbek. Held
out — the public release in `data/dtm_public.json` is disjoint.

**Prompt.** Uzbek, direct-answer: the model is asked for a single letter and
nothing else.

**This is a protocol choice and it must travel with the score.** Direct-answer
measures recall; letting the model reason first measures recall plus reasoning.
The two are not comparable, and a column where different models answered under
different protocols is not a comparison at all — so the protocol is set per task
config and applied identically to every model.

It is also what makes the benchmark affordable. Measured on qwen3.5:9b against
DTM items:

| protocol | per item | tokens | outcome |
|---|---|---|---|
| direct answer | **0.4 s** | **2** | answers |
| reason, then commit | 11.5 s | 427 | answers |
| reasoning enabled, 2048 budget | 106 s | 2048 | **truncated, no answer at all** |

The third row is not hypothetical: it is what the old harness did to every
thinking model, and it scored each of those empty responses as a wrong answer.
That is the whole of qwen3.5:9b's "55% unparseable" — the model was never given
room to answer.

For the chain-of-thought variant, set `answer_only: false` in the task config.
It reports under the same task name with a different version, and the two are
never merged into one column.

**Reasoning models.** Ollama's `think` flag is honoured only on its native
`/api/chat` endpoint; sent through the OpenAI-compatible route it is silently
discarded. The provider uses the native endpoint, and `reasoning: off` is
recorded in every run manifest so a thinking and a non-thinking run of the same
model can never be confused.

**Position bias.** Options are permuted with a seeded RNG, and the gold answer
is followed by *index*, not by text. Following it by text picks the first of two
identical options, which turns a correct reading into a coin flip.

**Extraction.** Four strategies, most-committing first: a bare letter; an
explicit cue (`Javob: B`, `**B**`, `\boxed{B}`); a letter anchored at the end of
the last line; a leading option label. Letters beyond the number of options
rendered are rejected — a model cannot choose what it was not shown. Nothing
else matches → `unparsed`. There is deliberately no "first or last letter
anywhere in the response" fallback.

**Score.** Accuracy. Chance 25%. Reported overall and per subject.

## `reasoning_uz` — logic and spatial reasoning

**Data.** 100 LiveBench-derived items translated to Uzbek: zebra puzzles,
spatial reasoning, web of lies. The source release carried a further 100 items
that LiveBench had formally retired — public long enough to be in training data,
so scoring them measures memorisation. Those were removed from the dataset on
2026-08-20 and no local copy remains.

**Precision.** At n = 100 the confidence interval is roughly ±10 points, so
models closer together than that are not separable on this track. Report the
interval alongside the score and do not imply a ranking it cannot support.

**Prompt.** The dataset prompt verbatim. No instruction is prepended: the
prompts themselves say *bosqichma-bosqich o'ylang* ("think step by step"), and
telling a model not to reason on a reasoning benchmark measures something else.

**Ollama's `think` is off here, and that is not the same thing.** The
distinction matters enough to state plainly:

| | what it does | effect |
|---|---|---|
| the old harness | prepended *"do not show your reasoning steps"* | suppressed the reasoning itself |
| `think: false` | moves reasoning from the hidden `thinking` field into `content` | reasoning still happens, and becomes scoreable |

With `think` enabled, a model spends its budget in a field the scorer never
sees. Measured on gemma4:26b at 4096 tokens: **93% of items truncated, and 92 of
those 93 returned an empty string.** Nothing was scored because nothing was
said. With it off, the model reasons in `content` — visible on the page, in the
per-item JSONL, and to anyone checking the work.

The budget is 8192, because the one gemma4:26b item that did reason in `content`
still ran out at 4096. This is the smallest task in the suite (100 items), so
the cost is affordable where it would not be on DTM.

**Score.** LiveBench partial credit, `((all_correct) + n_correct/n_total) / 2`.
Slots are compared by exact match after normalisation. A short answer list is a
parse failure, never left-aligned — padding shifts every remaining slot and
turns one unrecognised token into a near-total loss. A response offering
several different bold candidates is a hedge, not an answer, and is `unparsed`.

A content-free responder scores about 15.6% under this formula. That is the
`chance_level`, so a 12% result is correctly read as below the floor.

## `translation_uz` — uz↔en, uz↔ru

**Data.** FLORES-200 devtest, 200 segments × 4 directions = 800 pairs.
CC BY-SA 4.0 and gated upstream — see the dataset card before redistributing.

**Metrics.** Corpus-level, never a mean of sentence scores:

| Metric | Role |
|---|---|
| **chrF++** (`word_order=2`) | Primary. Tokeniser-free and robust to Uzbek agglutination. |
| spBLEU (`flores200`) | Comparability with FLORES/NLLB numbers. |
| BLEU (`13a`) | Legacy comparability only. Not ranked on. |

sacreBLEU signatures are reported with every number. Scores are given per
direction and macro-averaged across directions: chrF's scale depends on the
target language's morphology, so pooling uz→en with en→uz produces a number on
no scale.

**Extraction.** The full trailing block of the response, after stripping an
echoed `Tarjima:` prefix. Keeping only the first line scores a correct
multi-sentence translation as zero.

**Diagnostic.** `cyrillic_output_rate` — the share of outputs in Cyrillic
against Latin references. That is a real property of the model and is reported
separately rather than folded into the score.

## `ifeval_uz` — verifiable instruction following

**Data.** 541 prompts translated to Uzbek, each with machine-checkable
constraints.

**The coverage problem.** IFEval's constraints name specific strings — required
keywords, forbidden words, end phrases. Translating the prompt without
translating those makes them either unsatisfiable (the prompt asks for
«mushuk», the checker looks for `cat`) or trivially satisfied (English
forbidden words never appear in Uzbek text). Four more constraint types are not
meaningful in Uzbek at all: the two `change_case:english_*` checks condition on
the response being English, `keywords:letter_frequency` is ill-defined where
`sh`, `ch`, `oʻ`, `gʻ` are digraphs, and `change_case:capital_word_frequency`
depends on an English capitalisation idiom.

**The rule.** A constraint that cannot be evaluated is **excluded and counted**,
never passed and never failed. `constraint_coverage` is published beside the
score and currently stands at **73.6%** (614 of 834 constraints).

The remaining 220 split into two kinds, and only one of them is work:

* **122 are dropped by design** — the four types above, which are not meaningful
  in Uzbek. They can never be scored, so the ceiling is 85.4%, not 100%.
* **98 still need Uzbek terms** from a native speaker. `tools/ifeval_worklist.py`
  exports them as a CSV — English term, the Uzbek prompt it belongs to, a blank
  column — and merges the filled file back with `--apply`. List-valued kwargs
  are all-or-nothing: two of three forbidden words would score every model
  against an incomplete set while *looking* localised in the coverage figure.

Localise a row by adding `kwargs_uz`:

```json
{"instruction_id_list": ["keywords:existence"],
 "kwargs":    [{"keywords": ["cat"]}],
 "kwargs_uz": [{"keywords": ["mushuk"]}]}
```

**Metrics.** The four official IFEval numbers — prompt-level and
instruction-level × strict and loose, with the official eight loose response
variants — plus coverage. Per-instruction-type rates are shown only where at
least 15 instances were evaluated.

**Word counts.** Counted with an apostrophe-aware tokeniser, not
`str.split()`. Uzbek is agglutinative and needs materially fewer whitespace
words than English for the same content, so an English `num_words` target is a
different instruction. Measure the ratio on parallel text and set
`options.word_count_factor` before publishing.

## `mmlu_pro_uz` — professional knowledge

**Not publication-ready.** All 174 surviving items are category `business`.
Publishing this as "MMLU-Pro" claims coverage across STEM, humanities and
social sciences that the artifact does not have.

Ten options, chance 10%. Same prompting, permutation and extraction as `dtm`.
26 items with failed machine translation are quarantined; see
`data/quarantine/mmlu_pro_uz.json`.
