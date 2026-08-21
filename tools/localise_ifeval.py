#!/usr/bin/env python3
"""Derive Uzbek IFEval constraint arguments from the Uzbek prompts.

IFEval constraints name specific strings — required keywords, forbidden words,
end phrases, section markers. The prompts were translated into Uzbek; the
arguments were not. A prompt that asks in Uzbek for «mushuk» while the checker
looks for ``cat`` is unsatisfiable, and a forbidden-words list in English is
trivially satisfied by any Uzbek text. Roughly half the constraints could not be
evaluated at all.

The translations exist — inside the prompts. This recovers them.

**The rule is: derive, or leave alone.** A wrong argument is worse than a
missing one. A missing one is excluded from the score and counted in
``constraint_coverage``; a wrong one silently scores every model against a
string nobody asked for. Every derivation here is accepted only when it is
unambiguous, and everything else is left for a human.

    python tools/localise_ifeval.py --check     # report only, write nothing
    python tools/localise_ifeval.py             # write data/ifeval_uz.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from idrockbench.text.normalize import normalize  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "ifeval_uz.json"

#: A quoted span in the Uzbek prompt. Uzbek text uses several quote styles, and
#: the modifier-letter apostrophe must not be mistaken for a closing quote.
QUOTED = re.compile(r'["«“„]([^"»”“„\n]{1,80})["»”]|\'([^\'\n]{2,80})\'')

#: Section markers the prompts actually use, in place of English SECTION.
SECTION_WORDS = re.compile(r"\b(BO[ʻ'‘]?LIM|PARAGRAF|QISM|BOB)\b", re.IGNORECASE)


def quoted_terms(text: str) -> list[str]:
    """Quoted spans in order of appearance."""
    out = []
    for m in QUOTED.finditer(text or ""):
        term = (m.group(1) or m.group(2) or "").strip()
        if term and not term.startswith("\\") and len(term) < 80:
            out.append(term)
    return out


def english_terms_in_order(prompt_en: str, terms: list[str]) -> list[str]:
    """The English terms in the order the English prompt *quotes* them.

    Quote order, not first occurrence. Ordering by first occurrence anywhere in
    the prose gets it wrong whenever a term also appears as an ordinary word:
    in "Explain it to me like I'm a kid ... don't use 'slow', 'like', 'kid'",
    `like` and `kid` occur early as prose, so first-occurrence order yields
    kid, like, slow — and aligning that against the Uzbek quotes maps
    *slow* to *bola* ("child"). Both prompts quote the same terms in the same
    order, so quote-to-quote is the alignment that holds.
    """
    quoted = [q.lower() for q in quoted_terms(prompt_en)]
    if not quoted:
        return []
    ranked = []
    for t in terms:
        try:
            ranked.append((quoted.index(t.lower()), t))
        except ValueError:
            return []      # a term the English prompt never quotes: do not guess
    return [t for _, t in sorted(ranked)]


def localise_row(row: dict) -> tuple[list[dict], list[str]]:
    """Return (kwargs_uz, notes) for one row. Never guesses."""
    prompt_uz = row.get("prompt_uz") or ""
    prompt_en = row.get("prompt") or ""
    ids = row.get("instruction_id_list") or []
    base = [{k: v for k, v in (kw or {}).items() if v is not None}
            for kw in (row.get("kwargs") or [])]
    existing = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
    existing += [{} for _ in range(len(ids) - len(existing))]

    quotes = quoted_terms(prompt_uz)
    notes: list[str] = []

    # Every English term this row's constraints name, in prompt order. If the
    # Uzbek prompt quotes exactly as many terms, the mapping is unambiguous.
    wanted: list[str] = []
    for i, iid in enumerate(ids):
        kw = base[i] if i < len(base) else {}
        if iid == "keywords:existence":
            wanted += list(kw.get("keywords") or [])
        elif iid == "keywords:frequency" and kw.get("keyword"):
            wanted.append(kw["keyword"])
        elif iid == "keywords:forbidden_words":
            wanted += list(kw.get("forbidden_words") or [])
        elif iid == "length_constraints:nth_paragraph_first_word" and kw.get("first_word"):
            wanted.append(kw["first_word"])

    mapping: dict[str, str] = {}
    if wanted:
        ordered = english_terms_in_order(prompt_en, list(dict.fromkeys(wanted)))
        if len(ordered) == len(quotes) and quotes:
            mapping = dict(zip(ordered, quotes, strict=True))
        else:
            notes.append(
                f"term count mismatch: {len(ordered)} English vs {len(quotes)} quoted"
            )

    out: list[dict] = []
    for i, iid in enumerate(ids):
        kw = base[i] if i < len(base) else {}
        loc = dict(existing[i]) if i < len(existing) else {}

        def mapped(term):
            uz = mapping.get(term)
            # Reject a "translation" identical to the English word unless the
            # Uzbek prompt really does use the English term (names like hanson).
            if uz and (uz.lower() != term.lower() or term.lower() in prompt_uz.lower()):
                return normalize(uz)
            return None

        if iid == "keywords:existence" and "keywords" not in loc:
            uz = [mapped(t) for t in (kw.get("keywords") or [])]
            if uz and all(uz):
                loc["keywords"] = uz
        elif iid == "keywords:frequency" and "keyword" not in loc:
            uz = mapped(kw.get("keyword") or "")
            if uz:
                loc["keyword"] = uz
        elif iid == "keywords:forbidden_words" and "forbidden_words" not in loc:
            uz = [mapped(t) for t in (kw.get("forbidden_words") or [])]
            if uz and all(uz):
                loc["forbidden_words"] = uz
        elif iid == "length_constraints:nth_paragraph_first_word" and "first_word" not in loc:
            uz = mapped(kw.get("first_word") or "")
            if uz:
                loc["first_word"] = uz
        elif iid == "detectable_format:multiple_sections" and "section_spliter" not in loc:
            m = SECTION_WORDS.search(prompt_uz)
            if m:
                loc["section_spliter"] = normalize(m.group(1))
        elif iid == "startend:end_checker" and "end_phrase" not in loc:
            # The required phrase is the last quoted span, and only when the
            # prompt actually cues an ending. Anything looser risks pinning the
            # wrong sentence, which every model would then fail forever.
            if quotes and re.search(r"\b(yakunla|tugat|oxirgi|so[ʻ']nggi|bilan tuga)",
                                    prompt_uz, re.IGNORECASE):
                loc["end_phrase"] = normalize(quotes[-1])
        out.append(loc)
    return out, notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--path", type=Path, default=DATA)
    args = ap.parse_args()

    rows = json.loads(args.path.read_text(encoding="utf-8"))

    KEYS = ("keywords", "keyword", "forbidden_words", "end_phrase",
            "first_word", "section_spliter")
    before = Counter()
    after = Counter()
    total = Counter()
    notes_all: list[str] = []
    samples: list[str] = []

    for row in rows:
        ids = row.get("instruction_id_list") or []
        base = [{k: v for k, v in (kw or {}).items() if v is not None}
                for kw in (row.get("kwargs") or [])]
        old = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
        old += [{} for _ in range(len(ids) - len(old))]

        new, notes = localise_row(row)
        for n in notes:
            notes_all.append(f"key {row.get('key')}: {n}")

        for i in range(len(ids)):
            kw = base[i] if i < len(base) else {}
            for k in KEYS:
                if k in kw:
                    total[k] += 1
                    if k in old[i]:
                        before[k] += 1
                    if k in new[i]:
                        after[k] += 1
                        if k in kw and k not in old[i] and len(samples) < 8:
                            samples.append(f"  {k:<16} {kw[k]!s:<34} -> {new[i][k]!s}")
        row["kwargs_uz"] = new

    print(f"{'kwarg':<18}{'before':>9}{'after':>9}{'total':>8}")
    print("-" * 46)
    for k in KEYS:
        if total[k]:
            print(f"{k:<18}{before[k]:>9}{after[k]:>9}{total[k]:>8}")
    b, a, t = sum(before.values()), sum(after.values()), sum(total.values())
    print("-" * 46)
    print(f"{'TOTAL':<18}{b:>9}{a:>9}{t:>8}   {b/t:.0%} -> {a/t:.0%}")

    if samples:
        print("\nderived (sample):")
        print("\n".join(samples))
    if notes_all:
        print(f"\nleft for a human: {len(notes_all)} rows could not be aligned")
        for n in notes_all[:5]:
            print(f"  {n}")

    if args.check:
        print("\n--check: nothing written")
        return
    args.path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print(f"\nwrote {args.path}")


if __name__ == "__main__":
    main()
