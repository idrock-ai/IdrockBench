# Dataset card - Zarbulmasal (Uzbek folk riddles)

| | |
|---|---|
| **File** | `data/zarbulmasal.json` (331 riddles) |
| **Provenance** | `data/zarbulmasal_provenance.json` (331 records, verbatim source quotes) |
| **Language** | Uzbek (Latin) |
| **Tasks** | `zarbulmasal` (free text), `zarbulmasal_mc` (4-way multiple choice) |
| **Built** | 2026-08-20 |

## Why this track exists

Every other track here can be reached by translating English ability. A riddle
cannot. It needs Uzbek metaphor, Uzbek objects and Uzbek daily life, so it
measures cultural grounding rather than curriculum recall - the gap regional
benchmarks are most often criticised for leaving open.

Both formats run over the same items on purpose. A model that recognises *olma*
in a list of four but cannot produce it from the clues has memorised nothing
useful, and only running both reveals that.

## How it was collected

Two rounds of automated harvesting from **101 distinct published sources** -
Uzbek folklore collections, digitised books, Cyrillic archives, school material -
followed by adversarial verification.

```
round 1    661 harvested -> 339 unique -> 195 approved   (42% rejected)
round 2    515 harvested -> 248 unique -> 137 approved   (45% rejected)
merged     332 -> 331 after a final answer-leak check
```

Every riddle carries the verbatim text of its source page. No riddle was written
for this dataset. Anything that could not be traced to a page that was actually
fetched was dropped.

## Verification

Each candidate was judged by three independent auditors, and **all three had to
approve** - a majority vote would have let roughly one item in twenty through.

* **Provenance** - re-fetched source pages to confirm the riddle really appears
  there, and rejected accepted-answer variants absent from the source.
* **Logic** - solved each riddle from the clues alone, rejecting any whose answer
  did not follow or where another common object fitted equally well.
* **Language** - checked grammar, orthography, cultural authenticity, and that
  every accepted form is a real Uzbek word for the answer.

Defects this caught, each of which would have silently corrupted a score:

* **A fabricated synonym.** `hosila` ("derivative") listed as an accepted answer
  for *rainbow*. The auditor fetched the cited page and grepped it: the word was
  not there. An agent had invented it.
* **Two items contradicting each other.** The same uncuttability motif appeared
  twice with different answers (`suv` and `soya`). Either would have marked a
  correct native answer wrong.
* **Answer leaks.** `koʻk` accepted for a riddle whose text opens *"Koʻk kosani…"*
  - a model could score by copying the question.
* **A wrong species.** `xachir` (mule) accepted for `eshak` (donkey), in a riddle
  that says *"Ot emas"*.
* **Foreign contamination.** `sis` accepted for fog - Turkish, where Uzbek has
  `tuman`.
* **A translated Russian riddle** from a "Yangi zarbulmasal" section, a
  line-for-line calque of the well-known репа riddle.

The answer-leak rule is now enforced in `ZarbulmasalTask.validate`, so it cannot
return through new data.

## Orthography

Uzbek uses two modifier letters and the rule between them is positional:

* `ʻ` U+02BB only in the digraphs `oʻ` and `gʻ`
* `ʼ` U+02BC everywhere else - the *tutuq belgisi* in `sheʼr`, `taʼm`, `maʼno`

`normalize()` folds both to U+02BB, which is correct for comparison - no model
distinguishes them reliably - and wrong for text a human reads. Prompts are
therefore built with `normalize_display()`, which restores each mark to whichever
its position calls for. A test asserts no prompt in this dataset carries a
misplaced U+02BB.

## Composition

- **16 themes**, largest `uy-roʻzgʻor` (63), `tabiat` (48), `hayvonlar` (32)
- **Difficulty** - oson 78, oʻrtacha 178, qiyin 75
- **144 riddles accept more than one answer form** (1.56 on average). Uzbek is
  agglutinative, and one riddle can have two legitimate solutions. A single gold
  string would mark correct answers wrong.

## Scoring

Free text is exact match after normalisation, allowing a bounded set of Uzbek
inflectional suffixes on an accepted stem. The suffix set is closed rather than a
length cap: "any short ending" accepts `koʻzoynak` (spectacles) as an inflection
of `koʻz` (eye).

Chance level is **0** for free text and **0.25** for multiple choice.

## Known limits

- Sources are online collections. Nothing here is transcribed from a physical
  volume, so riddles that exist only in print are absent.
- Theme labels were assigned by the harvesters against a fixed 16-term
  vocabulary, not by a folklorist.
- Distractors are model-generated, then checked against the accepted-answer set
  by `validate`. They have not been reviewed by a native speaker.
