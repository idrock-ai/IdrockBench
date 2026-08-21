# Dataset card — DTM (Uzbek entrance-exam questions)

| | |
|---|---|
| **Files** | `data/dtm_heldout.json` (989, scored) · `data/dtm_public.json` (2,062, open) |
| **Language** | Uzbek (Latin) |
| **Task** | Four-option multiple choice |
| **Subjects** | ona tili, tarix, matematika, fizika |
| **Public release** | [IEEE DataPort, DOI 10.21227/e4h4-kp42](https://ieee-dataport.org/documents/uzbek-multiple-choice-question-dataset-large-language-model-evaluation) |

## Provenance

Extracted from 2019 State Test Centre (DTM) university-entrance **preparation
materials** using Qwen3-VL-30B-A3B-Instruct served with vLLM, from scanned book
pages. Items depending on a figure, graph, table or image were excluded, so
every released record is self-contained as text. Mathematics is encoded in
LaTeX; underlined fragments in ona tili items — a meaning-bearing typographic
cue in Uzbek grammar questions — are preserved as `<u>...</u>`.

The full corpus is 3,066 items. A stratified 1,000-item subset was held out for
evaluation (40% ona tili, 30% tarix, 15% matematika, 15% fizika); the remaining
2,066 form the public release.

## Validation status

**This is the dataset's weakest point and must be addressed before
publication.** Answer keys were verified in an LLM-assisted pass. There is no
human validation, no inter-annotator agreement statistic, and no measured
error rate.

Independent review derived closed-form solutions for a sample of physics items
and found **four incorrect answer keys** (held-out ids 855 and 856; public
qids 748 and 780), using a technique — solving near-duplicate item pairs and
checking key consistency — that found four errors in roughly twenty pairs. Those
four are recorded but **not yet corrected**: each needs a subject teacher to
confirm before the key is changed.

What is required before submission to any data venue:

1. A stratified random sample (n ≈ 385 for ±5% at 95%; n ≈ 100 per subject).
2. **At least two independent human annotators** per sampled item, blinded to
   the machine answer, with a written adjudication rule.
3. Cohen's or Fleiss' κ, human–machine agreement, and an answer-key error rate
   with a confidence interval, per subject.
4. VLM extraction fidelity reported separately (CER/WER against human
   transcription) — extraction errors and key errors are different failure
   modes with different fixes.

No Turkic-language benchmark currently reports an agreement statistic. Doing so
would place this dataset ahead of TUMLU, KazMMLU, TurkishMMLU and ArabicMMLU on
validation rigour, and it is the cheapest credibility available.

## Repairs applied

Performed by `tools/build_datasets.py`; see `data/CHANGELOG.md`.

- Apostrophes normalised to U+02BB; Cyrillic homoglyphs inside Latin words folded.
- **8 items with no answer key quarantined.** The previous runner defaulted a
  missing key to option A, putting eight items of pure noise into every score.
- **2 items with two identical options quarantined** — unanswerable as written.
- 1 duplicate item removed from the held-out set, 2 from the public set.
- **2 items removed from the public release** that also appeared in the
  held-out set, restoring the disjointness the data descriptor claims.
- One question stem repaired where a CSV field shift had prepended the topic string.
- Subject labels unified across the two files; `adabyot` → `adabiyot`.

## Known issues

- Four suspected wrong answer keys, listed above, pending expert confirmation.
- The data descriptor states topics are sampled uniformly within each subject.
  True for ona tili (17–18 per topic) and matematika (7–8), **false** for tarix
  (12–34) and fizika (3–10). Correct the claim or publish the real counts.
- The descriptor claims uniform A/B/C/D balance. Observed: C 260, A 252, D 244,
  B 236. No measurable position bias (χ² = 1.29, 3 df), and options are permuted
  at evaluation time regardless — but state the actual distribution.
- Field-schema mismatch: the descriptor documents `option_a`–`option_d` and
  `correct_answer`; the shipped files use `option_A`–`option_D`, `answer`, and
  an undocumented `test_number`.

## Contamination

Low exposure, and this is a genuine strength worth publishing. The source is
2019 scanned print material that was not on the open web in machine-readable
form. The public/held-out performance gap is a usable contamination signal;
report it as a column.

## Licence and legal status — unresolved

**Read this before any further redistribution.**

The items are extracted from commercial exam-preparation books. Under
Uzbekistan's Law on Copyright and Related Rights (ZRU-42/2006, as amended):

- Individual multiple-choice items with crafted distractors are copyrightable
  literary works. The publisher separately holds a compilation right in the
  selection and arrangement, and DTM may hold rights of its own.
- The Article 8 "official documents" exemption almost certainly does not apply
  — exam questions are not normative acts of a legislative, administrative or
  judicial character.
- Uzbekistan follows the civil-law model: a closed list of free-use exceptions
  bounded by the three-step test. **There is no fair-use defence**, and bulk
  extraction plus public redistribution of a question bank is neither
  "quotation" nor "illustration for teaching".
- Vision-model transcription is a reproduction, not a laundering step, and
  creates no new rights.

The public release is already live on IEEE DataPort. What materially helps, in
order:

1. **A written permission letter** from DTM and from the exam-prep publisher,
   covering reproduction, translation, distribution and sublicensing — routed
   through the university's legal office, not signed by the team. This is the
   only thing that fully resolves it.
2. **Commissioning original items** to the same blueprint. The lab then owns
   the copyright, can validate keys with humans, and gets an uncontaminated
   benchmark. This eliminates the legal question entirely.
3. **A published takedown policy** with a named contact and a stated response
   window, plus a per-item provenance ledger (source ISBN, page, extraction
   date, model version, reviewer) so selective removal is possible.

Do not label this dataset with a licence the lab cannot grant. Use
`license: other` with a file granting only the compilation, annotations and
metadata, and explicitly disclaiming ownership of the underlying items.

## Citation

```bibtex
@data{idrock_dtm2019,
  title     = {Uzbek Multiple-Choice Question Dataset for Large Language Model Evaluation},
  author    = {Hazratov, Mardon and Toshnazarov, Qobiljon and Qayumov, Abduaziz
               and Mansuraliyev, Husanboy and Asadov, Dovud},
  publisher = {IEEE DataPort},
  year      = {2026},
  doi       = {10.21227/e4h4-kp42}
}
```
