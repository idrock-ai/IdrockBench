# Dataset card - Reasoning (LiveBench-derived)

| | |
|---|---|
| **File** | `data/reasoning_uz.json` (100 rows. All scored) |
| **Language** | Uzbek (Latin), translated from English |
| **Tasks** | zebra_puzzle, spatial, web_of_lies_v2 |
| **Upstream** | [LiveBench](https://github.com/LiveBench/LiveBench) reasoning split |
| **Licence** | Apache-2.0 (per the LiveBench datasheet) |

## Provenance

LiveBench reasoning items translated into Uzbek. LiveBench derives web-of-lies
from BIG-Bench Hard, so the chain is Apache → Apache. The datasheet states
"there are no copyrights on the data" and "no fees or restrictions". Note the
HuggingFace cards carry no `license:` field. The datasheet is the authoritative
statement.

## Retired items were removed from the file

The source release carried 200 items, 100 of which LiveBench had formally
retired - zebra_puzzle withdrawn 2024-11-25, web_of_lies_v2 withdrawn
2025-04-02. LiveBench retires items once they have been public long enough to be
plausibly in the training data of newer models.

Those 100 rows, and the `livebench_release_date`, `livebench_removal_date` and
`retired` columns, were deleted from the dataset on 2026-08-20. The file now
holds only the 100 current items, every one of which is scored.

The trade-off, recorded plainly: the track is fixed at **n = 100**, which gives
confidence intervals roughly ±10 points wide. Models within that margin - Gemma
4 12B at 46.1 and Qwen3.5 9B at 42.4 - cannot be ranked against each other on
this track, and the published table should say so rather than implying an order.
Restoring the retired half would need the upstream LiveBench release again. No
local copy remains.

## Known issues

- **22 zebra items still carry the English ground truth** in
  `ground_truth_uzbek`. A model answering correctly in Uzbek cannot match them.
  They are flagged with `_needs_translation` and reported by
  `idrockbench validate`. They need a translator before this track is
  publication-ready.
- Only 50 of 100 zebra prompts retained the `<solution>` instruction through
  translation, so the prompts are not uniform in the output format they request.
  The parser handles both, but the dataset should be made consistent.
- Uzbek translations were machine-produced. No human validation is reported.

## Scoring note

Partial credit means a content-free responder scores about **15.6%**, not 0.
That is the declared `chance_level`. A model at 12% is below the floor, and that
usually indicates a parsing problem rather than poor reasoning.

## Citation

```bibtex
@article{livebench,
  title  = {LiveBench: A Challenging, Contamination-Limited LLM Benchmark},
  author = {White, Colin and Dooley, Samuel and Roberts, Manley and others},
  journal = {arXiv preprint arXiv:2406.19314}, year = {2024}}
```
