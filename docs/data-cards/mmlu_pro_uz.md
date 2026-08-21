# Dataset card - MMLU-Pro-uz

| | |
|---|---|
| **File** | `data/mmlu_pro_uz.json` (174 items) |
| **Language** | Uzbek (Latin), machine-translated from English |
| **Upstream** | [TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro) |
| **Licence** | MIT (upstream chain is clean) |
| **Status** | **Not publication-ready** |

## Why it is not publication-ready

**Every surviving item is category `business`.** MMLU-Pro covers fourteen
categories across STEM, humanities, law and social sciences. Publishing a
174-item business quiz under that name claims coverage the artifact does not
have, and it is the kind of claim an outside reader checks in five minutes.

Either translate the other categories, or rename the track to what it measures.

## The defect that made it unmeasurable

Options were stored as a NumPy `repr()`, which only inserts line breaks past
~75 characters. The previous parser split on newlines, so short option lists
collapsed into one or two garbled strings:

```
A) $50,200' '$45,100' '$60,400' '$56,300' '$58,800' '$54,400' '$65,500
B) $62,900' '$48,700' '$52,600
```

Result: **147 of 200 items (73.5%) had the correct answer outside what the model
was shown.** Maximum achievable accuracy was about 26%, and published scores of
6.5–15.5% were noise around the 10% random baseline - not a hard benchmark, a
broken one.

Now stored as JSON arrays and parsed by quoted span. Zero items have an
out-of-range key, and `idrockbench validate` fails the dataset if any appear.

## Repairs applied

- Options re-serialised as JSON arrays.
- **25 items quarantined for failed machine translation.** Examples: item 263's
  options are `'A q s.' 'O b h.' 'P m d.' 'P d k.'`. Item 259's Uzbek question
  is `"Bu nima"` (7 characters) against a 324-character English original.
- 1 item quarantined for mismatched English/Uzbek option counts, which would
  have shifted the answer key.
- Apostrophes normalised.

See `data/quarantine/mmlu_pro_uz.json`.

## Known limitations

- Machine-translated with no human validation. The field has converged on
  native authorship as the credibility standard, and translated benchmarks are
  expected to justify their validity - post-editing, back-translation, or
  native-speaker QA with a reported agreement statistic.
- 174 items gives a ±7pp interval at best. Too small for confident ranking.

## Citation

```bibtex
@article{wang2024mmlupro,
  title   = {MMLU-Pro: A More Robust and Challenging Multi-Task Language Understanding Benchmark},
  author  = {Wang, Yubo and Ma, Xueguang and Zhang, Ge and others},
  journal = {arXiv preprint arXiv:2406.01574}, year = {2024}}
```
