# Dataset card - Translation (FLORES-200)

| | |
|---|---|
| **File** | `data/translation_flores_devtest.json` (200 segments) |
| **Languages** | Uzbek (Latin), English, Russian |
| **Directions scored** | uz→en, en→uz, uz→ru, ru→uz - 800 pairs |
| **Upstream** | [facebook/flores](https://huggingface.co/datasets/facebook/flores), devtest split |
| **Licence** | **CC BY-SA 4.0**, plus upstream gate terms |

## Provenance

FLORES-200 devtest, the standard held-out evaluation split from Meta's No
Language Left Behind project. Reference translations passed a human quality gate
of ≥90/100 Translation Quality Score before release.

Applied here: text normalised to the canonical Uzbek apostrophe. The upstream
Uzbek references use ASCII `'` (480 occurrences against a single U+02BB), so
without normalisation a model writing orthographically correct Uzbek is scored
against typos - worth roughly 66 BLEU on affected segments.

## Licence - this one has real constraints

**CC BY-SA 4.0 is viral.** Any adaptation must be licensed under CC BY-SA 4.0 or
a compatible licence. The FLORES-derived portion of this benchmark therefore
**cannot** be MIT, Apache-2.0, or CC BY-NC.

**The upstream repo is now gated**, with three mandatory acceptance terms:

1. Evaluation only - the data and its derivatives may not be used to train
   machine-learning models.
2. Derivatives may only be distributed via a private or crawl-protected
   mechanism that requires accepting these terms.
3. Distributions must retain these terms.

Consequences:

- Redistributing this file publicly and ungated is inconsistent with the gate
  terms accepted at download.
- The benchmark **cannot ship as one permissively-licensed artifact**. Either
  segregate the FLORES-derived subset into its own gated CC BY-SA repository,
  or license the whole benchmark CC BY-SA, or drop FLORES.

There is a genuine tension between CC BY-SA §2(a)(5)(B), which forbids imposing
additional restrictions, and Meta's gate terms, which do. This cannot be
resolved by the lab. The risk-minimising posture is to comply with both.

Required attribution (TASL plus a modification notice):

> This dataset contains material adapted from **FLORES-200**, created by the
> **NLLB Team at Meta AI**, available at
> <https://github.com/facebookresearch/flores>, licensed under
> **CC BY-SA 4.0**. **Changes were made**: text was normalised to the canonical
> Uzbek apostrophe and reformatted as evaluation items. This adaptation is
> likewise licensed under CC BY-SA 4.0.

## Contamination

**High exposure.** FLORES-200 is one of the most widely distributed MT
evaluation sets in existence and appears in many training corpora. Treat these
scores as an upper bound and label them accordingly.

A fresh, never-published uz↔en↔ru test set - news or government text from after
the current model generation's cutoff - would be substantially more informative,
and is the single highest-value addition to this track.

## Known limitations

- Reference quality for Uzbek has not been independently audited. An audit of
  FLORES for four African languages found correction rates from 6.1% to 63.4%,
  so the ≥90 TQS gate is not a guarantee.
- 200 segments per direction is small. The reported bootstrap interval is wide.
  read it rather than the point estimate.
- COMET and other neural metrics have encoders that saw Uzbek pretraining text
  but were never trained or meta-evaluated on Uzbek human judgements. If added,
  they must be labelled zero-shot and never used as the sole ranking signal.

## Citation

```bibtex
@article{nllb2022,
  author = {{NLLB Team} and Costa-juss{\`a}, Marta R. and Cross, James and others},
  title  = {No Language Left Behind: Scaling Human-Centered Machine Translation},
  year   = {2022}, url = {https://arxiv.org/abs/2207.04672}}
```
