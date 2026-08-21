#!/usr/bin/env python3
"""Repair apostrophes that an over-eager fold destroyed in the datasets.

``normalize()`` maps every apostrophe-like codepoint to U+02BB. That is right
for *comparison* — no model distinguishes the Uzbek modifier letters reliably,
so a correct answer must not be marked wrong over a typographic choice — and
wrong for text a human reads, because it silently rewrites three different
things into one:

* **The tutuq belgisi.** U+02BB belongs only to the digraphs ``oʻ`` and ``gʻ``.
  Everywhere else Uzbek uses U+02BC: ``sheʼr``, ``taʼm``, ``maʼno``, ``sanʼat``.
  The fold turned all of those into ``sheʻr``, ``taʻm`` — misspelt.
* **Quotation marks.** ``'uch'`` became ``ʻuchʻ``. This also hides quoted terms
  from ``tools/localise_ifeval.py``, which finds Uzbek constraint arguments by
  matching quoted spans.
* **Mathematical primes.** ``f'(x)`` became ``fʻ(x)`` in DTM calculus questions.
  ``g'(x)`` is worse: it folds to ``gʻ(x)``, which *looks* like a legal Uzbek
  digraph and so hides from any positional check.

Each class is repaired by a different rule, and only where the rule is
unambiguous. Restored quotes use « » and primes use ``^{\\prime}`` because both
survive ``normalize()`` — ASCII ``'`` would simply be folded again.

    python tools/repair_apostrophes.py --check    # report only
    python tools/repair_apostrophes.py            # rewrite the datasets
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from idrockbench.text.normalize import normalize_display  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"

BB = "ʻ"          # U+02BB, correct only in oʻ and gʻ
BC = "ʼ"          # U+02BC, the tutuq belgisi

#: U+02BB following a letter that is not o/g. Unambiguously a tutuq belgisi:
#: no Uzbek word carries the turned comma there. Word-final position counts —
#: Arabic loanwords end in one (``matlaʼ``, ``tarseʼ``, ``jomeʼ``) — which is
#: why this does not require a letter on the right. Quote pairs are consumed
#: before this runs, so a closing quotation mark cannot reach it.
TUTUQ = re.compile(r"(?<=[^\W\d_])(?<![oOgG])" + BB, re.UNICODE)

#: A letter, a turned comma, then an opening bracket: derivative notation.
#: Restricted to single-letter function names so ordinary Uzbek cannot match.
PRIME = re.compile(r"(?<![^\W\d_])([A-Za-z])" + BB + r"(\s*\()")

#: A balanced pair of turned commas around a short span that starts and ends on
#: a non-space, where the opening mark follows a boundary. Quotation marks.
QUOTE = re.compile(r"(?<![^\W\d_])" + BB + r"(\S[^" + BB + r"\n]{0,78}\S|\S)" + BB + r"(?![^\W\d_])")

#: Uzbek text fields only. English source columns are left alone: folding an
#: English "don't" is not this script's business, and rewriting a reference
#: translation's source side would change what is being asked.
FIELDS: dict[str, list[str]] = {
    "dtm_public.json": ["question", "option_A", "option_B", "option_C", "option_D",
                        "topic", "subject"],
    "dtm_heldout.json": ["question", "option_A", "option_B", "option_C", "option_D",
                         "topic", "subject"],
    "ifeval_uz.json": ["prompt_uz", "kwargs_uz"],
    "mmlu_pro_uz.json": ["question_uzb", "options_uzb"],
    "reasoning_uz.json": ["turns_in_uzbek", "ground_truth_uzbek"],
    "translation_flores_devtest.json": ["text_uz"],
}


def repair(text: str) -> tuple[str, dict[str, int]]:
    """Return the repaired string and a count of each class fixed."""
    counts = {"prime": 0, "quote": 0, "tutuq": 0}

    # Primes first: f'( would otherwise be untouched by TUTUQ but must not be
    # mistaken for anything else later.
    text, counts["prime"] = PRIME.subn(r"\1^{\\prime}\2", text)
    # Then quotes, whose marks sit at boundaries.
    text, counts["quote"] = QUOTE.subn(r"«\1»", text)
    # Whatever turned comma is left between two letters is a tutuq belgisi.
    text, counts["tutuq"] = TUTUQ.subn(BC, text)
    return text, counts


#: English and Russian source columns were folded too: "it's" became "itʻs",
#: "O'Flynn" became "OʻFlynn". Those languages use the ASCII apostrophe, so the
#: repair is a different character from the Uzbek one — and the translation task
#: no longer normalises its source, so it survives.
#: English and Russian never use U+02BB for anything, so every occurrence in
#: these columns is damage — an elision ("itʻs"), a name ("OʻFlynn") or a quote
#: ("ʻflat whiteʻ"). Verified: no genuine Uzbek digraph appears in them.
FOREIGN = re.compile(BB)

#: Columns holding English or Russian rather than Uzbek.
FOREIGN_FIELDS: dict[str, list[str]] = {
    "translation_flores_devtest.json": ["text_en", "text_ru"],
}


def repair_foreign(text: str) -> tuple[str, int]:
    return FOREIGN.subn("'", text)


def canonicalise(text: str) -> tuple[str, int]:
    """Put every remaining apostrophe on the right codepoint for its position.

    The DTM source used ASCII throughout — ``O'zbekiston``, ``bo'lgan``,
    ``ma'lumot`` — so the file mixes ASCII with U+02BB for the same digraph.
    ``normalize_display`` resolves each by position: U+02BB after o/g, U+02BC
    otherwise. Guillemets and ``^{\prime}`` are untouched by it.
    """
    out = normalize_display(text)
    if out == text:
        return text, 0
    changed = sum(1 for a, b in zip(text, out) if a != b) or 1
    return out, changed


def walk(value, counts: dict[str, int]):
    if isinstance(value, str):
        out, n = repair(value)
        for k, v in n.items():
            counts[k] += v
        out, n_canon = canonicalise(out)
        counts["canon"] += n_canon
        return out
    if isinstance(value, list):
        return [walk(v, counts) for v in value]
    if isinstance(value, dict):
        return {k: walk(v, counts) for k, v in value.items()}
    return value


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    grand = {"prime": 0, "quote": 0, "tutuq": 0, "canon": 0}
    print(f"{'dataset':<34}{'prime':>7}{'quote':>7}{'tutuq':>7}{'canon':>7}")
    print("-" * 55)
    for name, fields in FIELDS.items():
        path = DATA / name
        if not path.exists():
            print(f"{name:<34}   (absent)")
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        counts = {"prime": 0, "quote": 0, "tutuq": 0, "canon": 0}
        for row in rows:
            for key in fields:
                if key in row:
                    row[key] = walk(row[key], counts)
        for k, v in counts.items():
            grand[k] += v
        foreign = 0
        for row in rows:
            for key in FOREIGN_FIELDS.get(name, []):
                if isinstance(row.get(key), str):
                    row[key], n = repair_foreign(row[key])
                    foreign += n
        suffix = f"   (+{foreign} en/ru)" if foreign else ""
        print(f"{name:<34}{counts['prime']:>7}{counts['quote']:>7}{counts['tutuq']:>7}{counts['canon']:>7}{suffix}")
        if not args.check:
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    print("-" * 55)
    print(f"{'TOTAL':<34}{grand['prime']:>7}{grand['quote']:>7}{grand['tutuq']:>7}{grand['canon']:>7}")
    print("\n--check: nothing written" if args.check else "\ndatasets rewritten")


if __name__ == "__main__":
    main()
