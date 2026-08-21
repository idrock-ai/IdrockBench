#!/usr/bin/env python3
"""Export the IFEval constraints that still need Uzbek terms, as a CSV a native
speaker can fill in.

``tools/localise_ifeval.py`` recovers every argument it can derive unambiguously
by matching quoted terms between the English and Uzbek prompts. What is left
over cannot be aligned automatically — the two prompts quote different numbers
of terms, so any mapping would be a guess. A wrong argument is worse than a
missing one: a missing one is excluded and counted in ``constraint_coverage``,
while a wrong one silently scores every model against a word nobody asked for.

So the remainder goes to a human. This writes one row per missing term with the
English word, the constraint that needs it and the Uzbek prompt it belongs to,
plus an empty ``uz`` column to fill in.

    python tools/ifeval_worklist.py                  # -> ifeval_todo.csv
    python tools/ifeval_worklist.py --apply FILE     # merge a filled-in CSV back

Nothing is written into the dataset until ``--apply``, and a row whose ``uz``
cell is still blank is skipped rather than guessed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from idrockbench.tasks._ifeval_checkers import REGISTRY, Disposition  # noqa: E402
from idrockbench.text.normalize import normalize  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "ifeval_uz.json"
OUT = Path(__file__).resolve().parents[1] / "ifeval_todo.csv"

#: Which kwarg holds the term(s) each constraint needs, and whether it is a list.
TERM_KEYS = {
    "keywords:existence": ("keywords", True),
    "keywords:frequency": ("keyword", False),
    "keywords:forbidden_words": ("forbidden_words", True),
    "startend:end_checker": ("end_phrase", False),
    "length_constraints:nth_paragraph_first_word": ("first_word", False),
    "detectable_format:multiple_sections": ("section_spliter", False),
}
FIELDS = ("key", "constraint", "kwarg", "index", "en", "uz", "prompt_uz")


def missing_rows(rows: list[dict]) -> list[dict]:
    """Every term still needed, in dataset order."""
    out: list[dict] = []
    for row in rows:
        ids = row.get("instruction_id_list") or []
        base = [{k: v for k, v in (kw or {}).items() if v is not None}
                for kw in (row.get("kwargs") or [])]
        uz = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
        uz += [{} for _ in range(len(ids) - len(uz))]
        for i, iid in enumerate(ids):
            checker = REGISTRY.get(iid)
            if checker is None or checker.disposition is not Disposition.NEEDS_LOCALE:
                continue
            if uz[i]:
                continue                      # already localised
            spec = TERM_KEYS.get(iid)
            if spec is None:
                continue
            key, is_list = spec
            kw = base[i] if i < len(base) else {}
            if key not in kw:
                continue
            terms = kw[key] if is_list else [kw[key]]
            for n, term in enumerate(terms):
                out.append({
                    "key": row.get("key"), "constraint": iid, "kwarg": key,
                    "index": f"{i}.{n}", "en": term, "uz": "",
                    "prompt_uz": " ".join(str(row.get("prompt_uz") or "").split())[:300],
                })
    return out


def apply(rows: list[dict], filled: Path) -> tuple[int, int]:
    """Merge a filled-in CSV back into the dataset. Blank cells are skipped."""
    by_key = {str(r.get("key")): r for r in rows}
    done = skipped = 0
    grouped: dict[tuple[str, int, str, bool], list[tuple[int, str]]] = {}
    with open(filled, encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            uz = (rec.get("uz") or "").strip()
            if not uz:
                skipped += 1
                continue
            i, n = (int(x) for x in rec["index"].split("."))
            _, is_list = TERM_KEYS[rec["constraint"]]
            grouped.setdefault((rec["key"], i, rec["kwarg"], is_list), []).append((n, uz))
            done += 1

    partial = 0
    for (key, i, kwarg, is_list), terms in grouped.items():
        row = by_key.get(str(key))
        if row is None:
            continue
        ids = row.get("instruction_id_list") or []
        base = [{k: v for k, v in (kw or {}).items() if v is not None}
                for kw in (row.get("kwargs") or [])]
        # A list kwarg is all-or-nothing. Writing two of three forbidden words
        # scores every model against an incomplete set — it looks localised in
        # the coverage figure while checking something nobody asked for. Half a
        # constraint is not a constraint.
        if is_list:
            expected = len((base[i] if i < len(base) else {}).get(kwarg) or [])
            if len(terms) < expected:
                partial += len(terms)
                done -= len(terms)
                skipped += len(terms)
                continue
        loc = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
        loc += [{} for _ in range(len(ids) - len(loc))]
        values = [normalize(v) for _, v in sorted(terms)]
        loc[i][kwarg] = values if is_list else values[0]
        row["kwargs_uz"] = loc
    if partial:
        print(f"note: {partial} term(s) belong to partly-filled lists and were "
              f"left out — fill every term of a constraint or none")
    return done, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", type=Path, help="merge a filled-in CSV into the dataset")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--path", type=Path, default=DATA)
    args = ap.parse_args()

    rows = json.loads(args.path.read_text(encoding="utf-8"))

    if args.apply:
        done, skipped = apply(rows, args.apply)
        args.path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print(f"applied {done} term(s); {skipped} row(s) still blank -> {args.path}")
        return

    todo = missing_rows(rows)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(todo)

    by_constraint: dict[str, int] = {}
    for r in todo:
        by_constraint[r["constraint"]] = by_constraint.get(r["constraint"], 0) + 1
    print(f"{len(todo)} term(s) need an Uzbek equivalent -> {args.out}\n")
    for iid, n in sorted(by_constraint.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>3}  {iid}")
    print("\nFill the `uz` column, then:")
    print(f"  python tools/ifeval_worklist.py --apply {args.out}")


if __name__ == "__main__":
    main()
