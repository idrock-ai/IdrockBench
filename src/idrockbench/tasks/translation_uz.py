"""Translation between Uzbek, Russian and English.

One item per (segment, direction). Directions are configured, not hard-coded,
so adding uz->tr means one line in the task config rather than a code change.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..core import Item, ItemResult
from ..extraction import Extraction, extract_last_line
from ..metrics.translation import bootstrap_ci, corpus_scores, sentence_chrf
from ..registry import register_task
from ..text.normalize import normalize, normalize_display
from .base import Task

LANGUAGE_NAMES = {
    "uz": ("O'zbek", "Uzbek"),
    "en": ("Ingliz", "English"),
    "ru": ("Rus", "Russian"),
    "tr": ("Turk", "Turkish"),
    "kk": ("Qozoq", "Kazakh"),
}

#: Prefixes a model may echo before its translation.
ANSWER_PREFIXES = ("Tarjima", "Translation", "Перевод")


@register_task
class TranslationTask(Task):
    name = "translation"
    version = "2.0"
    description = "Bidirectional translation quality between Uzbek, Russian and English."
    primary_metric = "chrf2pp"
    chance_level = 0.0
    default_max_tokens = 1024

    #: Ordered language pairs to evaluate. Override in the task config.
    directions: tuple[str, ...] = ("uz_en", "en_uz", "uz_ru", "ru_uz")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if "directions" in self.options:
            self.directions = tuple(self.options["directions"])
        #: Only score rows in the held-out split.
        self.eval_splits = tuple(self.options.get("eval_splits", ("devtest", "test")))

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items: list[Item] = []
        for i, row in enumerate(records):
            split = str(row.get("split", "")).strip().lower()
            if self.eval_splits and split and split not in self.eval_splits:
                continue
            rid = row.get("id", i)
            for direction in self.directions:
                src_lang, tgt_lang = direction.split("_")
                source = row.get(f"text_{src_lang}") or (
                    row.get("source") if row.get("direction") == direction else None
                )
                target = row.get(f"text_{tgt_lang}") or (
                    row.get("reference") if row.get("direction") == direction else None
                )
                if not source or not target:
                    continue
                items.append(Item(
                    id=f"{rid}:{direction}",
                    # The source is passed through verbatim. Two of the three
                    # directions hand the model English or Russian, and folding
                    # their apostrophes damages the very text it is asked to
                    # translate — "it's" became "itʻs" in 41 devtest sentences.
                    # The dataset itself is the place to be correct; see
                    # tools/repair_apostrophes.py.
                    payload={"source": source, "direction": direction},
                    # The reference is normalised only for storage symmetry; the
                    # metric normalises both sides again before scoring.
                    gold=normalize(target),
                    meta={"direction": direction, "split": split or "unknown"},
                ))
        return items

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems: list[str] = []
        needed = {f"text_{lang}" for d in self.directions for lang in d.split("_")}
        for i, row in enumerate(records):
            rid = row.get("id", i)
            missing = [k for k in needed if not str(row.get(k, "") or "").strip()]
            if missing and not (row.get("source") and row.get("reference")):
                problems.append(f"row {rid}: missing {', '.join(sorted(missing))}")
        return problems

    def build_prompt(self, item: Item) -> str:
        src, tgt = item.payload["direction"].split("_")
        src_uz = LANGUAGE_NAMES.get(src, (src, src))[0]
        tgt_uz = LANGUAGE_NAMES.get(tgt, (tgt, tgt))[0]
        return (
            f"Quyidagi matnni {src_uz} tilidan {tgt_uz} tiliga tarjima qiling.\n"
            f"Faqat tarjimani yozing, izoh bermang.\n\n"
            f"Matn: {item.payload['source']}\n\n"
            f"Tarjima:"
        )

    def parse(self, response: str, item: Item) -> Extraction:
        return extract_last_line(response, strip_prefixes=ANSWER_PREFIXES)

    def score(self, extraction: Extraction, item: Item) -> float:
        # Per-item chrF++ for inspection only; the headline is corpus-level.
        try:
            return round(sentence_chrf(extraction.value or "", item.gold) / 100.0, 4)
        except ImportError:
            return 0.0

    def aggregate(self, results: Sequence[ItemResult]) -> dict[str, Any]:
        scorable = [r for r in results if r.scorable]
        if not scorable:
            return {"primary": 0.0, "n": 0}

        hyps = [r.extracted or "" for r in scorable]
        refs = [str(r.gold) for r in scorable]
        overall = corpus_scores(hyps, refs)
        n_boot = int(self.options.get("bootstrap_samples", 500))
        ci_low, ci_high = bootstrap_ci(hyps, refs, n_samples=n_boot) if n_boot else (None, None)
        metrics: dict[str, Any] = {
            "primary": overall.get("chrf2pp", 0.0),
            **overall,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "ci_method": f"segment bootstrap, {n_boot} resamples" if n_boot else "none",
            "n": len(scorable),
        }

        # Per direction, because chrF's scale depends on the target language's
        # morphology: pooling uz->en and en->uz produces a number on no scale.
        by_dir: dict[str, list[ItemResult]] = {}
        for r in scorable:
            by_dir.setdefault(str(r.meta.get("direction", "unknown")), []).append(r)
        metrics["by_direction"] = {
            d: corpus_scores([r.extracted or "" for r in rows], [str(r.gold) for r in rows])
            for d, rows in sorted(by_dir.items())
        }
        # Macro-average over directions: each direction weighs equally,
        # regardless of how many segments it happens to contain.
        per_dir = [v.get("chrf2pp", 0.0) for v in metrics["by_direction"].values()]
        metrics["chrf2pp_macro"] = round(sum(per_dir) / len(per_dir), 2) if per_dir else 0.0
        return metrics

    def breakdown_keys(self) -> tuple[str, ...]:
        return ("direction",)
