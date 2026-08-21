# Dataset card — IFEval-UZ

| | |
|---|---|
| **File** | `data/ifeval_uz.json` (541 prompts, 834 constraints) |
| **Language** | Uzbek (Latin), translated from English |
| **Upstream** | [google/IFEval](https://huggingface.co/datasets/google/IFEval) |
| **Licence** | Apache-2.0 |
| **Status** | **Not publication-ready** — constraint coverage ≈ 50% |

## Provenance

Google's IFEval prompts translated into Uzbek (backend `inception/mercury-2`,
with a manual correction pass recorded per row in `translation_meta`; 310 of 541
rows have `manually_corrected: null`).

Apache-2.0 §4 requires that modified files carry prominent notices stating they
were changed. For a translated IFEval that is not optional: state per file that
prompts were translated and that a subset of English-specific constraints was
removed or adapted.

## The coverage problem

IFEval constraints name specific strings — required keywords, forbidden words,
end phrases, section splitters, repeat targets. **The prompts were translated;
the constraint arguments were not.** Measured coverage of Uzbek localisation:

| kwarg | localised |
|---|---|
| `postscript_marker` | 26/26 (100%) |
| `keywords` | 44/86 (51%) |
| `forbidden_words` | 58/117 (50%) |
| `keyword` | 18/42 (43%) |
| `first_word` | 3/12 (25%) |
| `end_phrase` | 1/26 (4%) |
| `section_spliter` | **0/14 (0%)** |

So a prompt asks in Uzbek for «mushuk» while the checker looks for `cat` —
unsatisfiable — and a forbidden-words list in English is trivially satisfied by
any Uzbek text. The inconsistency is worse than a uniform failure: per-instruction
accuracy mixes two populations and measures translation coverage, not
instruction-following.

**The rule here: an unevaluable constraint is excluded and counted, never passed
and never failed.** `constraint_coverage` is published beside the score. Never
publish the score without it.

## Constraint dispositions

| Disposition | Count | Handling |
|---|---|---|
| Transferable | 9 types | Scored as-is — formatting, punctuation, structure |
| Needs localised kwargs | 9 types | Scored only when the row supplies `kwargs_uz` |
| Recalibrate | 2 types | Scored, but the target was set for English |
| Dropped | 4 types | Excluded — not meaningful in Uzbek |

Dropped, with reasons:

- `change_case:english_lowercase`, `change_case:english_capital` — the original
  conditions on the response being detected as English, so they can never pass
  on Uzbek text. Add `uzbek_lowercase`/`uzbek_capital` variants instead.
- `keywords:letter_frequency` — Uzbek Latin uses digraphs (`sh`, `ch`, `ng`,
  `oʻ`, `gʻ`), so a single-letter count is not a well-formed instruction. The
  shipped letters also include `c` and `w`, which are digraph-only in Uzbek, and
  `#` and `!`, which are not letters.
- `change_case:capital_word_frequency` — depends on an English capitalisation
  idiom and an English tokeniser.

## To make this publication-ready

1. **Localise the remaining kwargs**, adding `kwargs_uz` per row. A keyword
   should be the Uzbek *stem* the prompt actually requests — substring matching
   then covers inflected forms naturally.
2. **Measure the word-count factor.** Uzbek needs materially fewer whitespace
   words than English for the same content, so a copied `num_words` target is a
   different instruction. Compute the ratio on ≥500 parallel segments with the
   same tokeniser and set `options.word_count_factor`.
3. **Install `lingua-language-detector`** for `language:response_language`, or
   the constraint stays excluded. It must distinguish Uzbek from Turkish and
   Azerbaijani, which `langdetect` does poorly.
4. Report the empty-response floor alongside every published score.

## Citation

```bibtex
@misc{zhou2023instructionfollowing,
  title  = {Instruction-Following Evaluation for Large Language Models},
  author = {Zhou, Jeffrey and Lu, Tianjian and Mishra, Swaroop and others},
  year   = {2023}, eprint = {2311.07911}, archivePrefix = {arXiv}}
```
