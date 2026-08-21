"""IFEval-UZ — verifiable instruction following in Uzbek.

Reports the four official IFEval numbers (prompt-level and instruction-level ×
strict and loose) plus one this benchmark adds and treats as mandatory:
``coverage`` — the share of constraints actually evaluated.

Coverage exists because a translated IFEval has constraints that cannot be
checked. A prompt asking in Uzbek for the word «mushuk» against an English
kwarg of ``"cat"`` is unsatisfiable; a forbidden-words list in English is
trivially satisfied by any Uzbek text. Both are excluded here and counted,
rather than scored as a failure or a pass. A score whose coverage is not
published is not interpretable.

To localise a row, add ``kwargs_uz`` beside ``kwargs``:

    {"instruction_id_list": ["keywords:existence"],
     "kwargs":    [{"keywords": ["cat"]}],
     "kwargs_uz": [{"keywords": ["mushuk"]}]}
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..core import Item, ItemResult
from ..extraction import Extraction, ParseStatus, strip_reasoning
from ..registry import register_task
from ._ifeval_checkers import REGISTRY, Disposition, loose_variants
from .base import Task


def _clean(kw: dict | None) -> dict:
    """Drop null-valued kwargs.

    The source dataset stores every key on every constraint with ``null`` for
    the inapplicable ones, so ``kw.get("relation", "at least")`` returns
    ``None`` rather than the default — which then falls through a relation
    chain into a free pass.
    """
    return {k: v for k, v in (kw or {}).items() if v is not None}


@register_task
class IFEvalUzTask(Task):
    name = "ifeval_uz"
    version = "2.0"
    description = "Verifiable instruction following in Uzbek (IFEval, localised)."
    primary_metric = "prompt_strict"
    chance_level = 0.0
    default_max_tokens = 2048

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        #: Score constraints whose numeric target was calibrated on English.
        #: On by default with the recalibration factor applied; set to False to
        #: exclude them entirely while the factor is being measured.
        self.score_recalibrated = bool(self.options.get("score_recalibrated", True))
        #: Uzbek needs fewer whitespace words than English for the same content.
        #: Measure on your own parallel data and set it here; 1.0 disables.
        self.word_count_factor = float(self.options.get("word_count_factor", 1.0))

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        items: list[Item] = []
        for i, row in enumerate(records):
            prompt = row.get("prompt_uz") or row.get("prompt")
            if not prompt:
                continue
            ids = list(row.get("instruction_id_list") or [])
            base = [_clean(k) for k in (row.get("kwargs") or [])]
            local = [_clean(k) for k in (row.get("kwargs_uz") or [])]
            merged = []
            for j in range(len(ids)):
                kw = dict(base[j]) if j < len(base) else {}
                if j < len(local) and local[j]:
                    kw.update(local[j])
                    kw["_localised"] = True
                merged.append(kw)
            items.append(Item(
                id=str(row.get("key", i)),
                payload={"prompt": prompt, "instruction_ids": ids, "kwargs": merged},
                gold=ids,
                meta={"n_constraints": len(ids)},
            ))
        return items

    def validate(self, records: Sequence[dict]) -> list[str]:
        problems: list[str] = []
        need_locale: dict[str, int] = {}
        unknown: dict[str, int] = {}
        for i, row in enumerate(records):
            if not row.get("prompt_uz"):
                problems.append(f"row {row.get('key', i)}: no Uzbek prompt")
            ids = row.get("instruction_id_list") or []
            local = row.get("kwargs_uz") or []
            for j, iid in enumerate(ids):
                spec = REGISTRY.get(iid)
                if spec is None:
                    unknown[iid] = unknown.get(iid, 0) + 1
                    continue
                if spec.disposition is Disposition.NEEDS_LOCALE and not (
                    j < len(local) and _clean(local[j])
                ):
                    need_locale[iid] = need_locale.get(iid, 0) + 1
        for iid, n in sorted(unknown.items(), key=lambda kv: -kv[1]):
            problems.append(f"{n} constraints use unregistered instruction id {iid!r}")
        for iid, n in sorted(need_locale.items(), key=lambda kv: -kv[1]):
            problems.append(
                f"{n} × {iid} have no kwargs_uz — the Uzbek prompt asks for one thing "
                f"and the English kwarg checks another, so they are excluded from scoring"
            )
        return problems

    def build_prompt(self, item: Item) -> str:
        return item.payload["prompt"]

    def parse(self, response: str, item: Item) -> Extraction:
        visible, dangling = strip_reasoning(response)
        if not visible.strip():
            status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
            return Extraction(None, status, "empty", response[-160:])
        # The response *is* the answer; compliance is judged by the checkers.
        return Extraction(visible, strategy="response", evidence=visible[:120])

    # -- constraint evaluation ---------------------------------------------

    def _evaluate(self, response: str, item: Item) -> list[dict[str, Any]]:
        """Evaluate every constraint on one prompt.

        Each result is ``pass`` / ``fail`` / ``excluded`` with a reason. A
        checker that raises is *excluded*, never passed — an unevaluable
        constraint carries no evidence either way.
        """
        out: list[dict[str, Any]] = []
        for iid, kw in zip(item.payload["instruction_ids"],
                           item.payload["kwargs"], strict=True):
            spec = REGISTRY.get(iid)
            if spec is None:
                out.append({"id": iid, "outcome": "excluded", "reason": "unregistered"})
                continue
            if spec.disposition is Disposition.DROPPED:
                out.append({"id": iid, "outcome": "excluded", "reason": "not-meaningful-in-uzbek"})
                continue
            if spec.disposition is Disposition.NEEDS_LOCALE and not kw.get("_localised"):
                out.append({"id": iid, "outcome": "excluded", "reason": "kwargs-not-localised"})
                continue
            if spec.disposition is Disposition.RECALIBRATE and not self.score_recalibrated:
                out.append({"id": iid, "outcome": "excluded", "reason": "target-not-recalibrated"})
                continue

            kwargs = dict(kw)
            if spec.disposition is Disposition.RECALIBRATE and "num_words" in kwargs:
                kwargs["num_words"] = round(float(kwargs["num_words"]) * self.word_count_factor)

            try:
                strict = bool(spec.fn(response.strip(), kwargs, item.payload["prompt"]))
                loose = strict or any(
                    bool(spec.fn(v.strip(), kwargs, item.payload["prompt"]))
                    for v in loose_variants(response) if v.strip()
                )
            except (NotImplementedError, RuntimeError, ValueError) as exc:
                out.append({"id": iid, "outcome": "excluded", "reason": str(exc)[:80]})
                continue
            except Exception as exc:  # a checker bug must not be charged to the model
                out.append({"id": iid, "outcome": "excluded",
                            "reason": f"checker error: {type(exc).__name__}"})
                continue
            out.append({"id": iid, "outcome": "pass" if strict else "fail",
                        "strict": strict, "loose": loose})
        return out

    def score(self, extraction: Extraction, item: Item) -> float:
        """Prompt-level strict: 1.0 only if every *evaluated* constraint passes.

        A prompt with no evaluable constraints scores 0 and is excluded from
        the denominator by :meth:`aggregate`.

        The per-constraint detail is stored on ``item.meta`` so the runner
        carries it into the item record: aggregation needs it, and a reviewer
        checking a disputed score needs to see which constraint failed. Items
        are never shared between threads, so this is safe.
        """
        results = self._evaluate(extraction.value or "", item)
        item.meta["constraints"] = results
        scored = [r for r in results if r["outcome"] != "excluded"]
        if not scored:
            return 0.0
        return 1.0 if all(r["strict"] for r in scored) else 0.0

    def aggregate(self, results: Sequence[ItemResult]) -> dict[str, Any]:
        from ..metrics.accuracy import accuracy_with_ci

        prompt_strict: list[float] = []
        prompt_loose: list[float] = []
        inst_strict: list[float] = []
        inst_loose: list[float] = []
        excluded = 0
        total_constraints = 0
        by_type: dict[str, dict[str, int]] = {}
        exclusion_reasons: dict[str, int] = {}

        for r in results:
            if not r.scorable:
                continue
            evaluated = r.meta.get("constraints") or []
            scored = [c for c in evaluated if c["outcome"] != "excluded"]
            total_constraints += len(evaluated)
            for c in evaluated:
                if c["outcome"] == "excluded":
                    excluded += 1
                    reason = c.get("reason", "unknown")
                    exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
                    continue
                bucket = by_type.setdefault(c["id"], {"n": 0, "strict": 0, "loose": 0})
                bucket["n"] += 1
                bucket["strict"] += int(c["strict"])
                bucket["loose"] += int(c["loose"])
                inst_strict.append(float(c["strict"]))
                inst_loose.append(float(c["loose"]))
            if scored:
                prompt_strict.append(float(all(c["strict"] for c in scored)))
                prompt_loose.append(float(all(c["loose"] for c in scored)))

        ps = accuracy_with_ci(prompt_strict)
        return {
            "primary": ps["accuracy"],
            "prompt_strict": ps["accuracy"],
            "ci_low": ps["ci_low"],
            "ci_high": ps["ci_high"],
            "prompt_loose": accuracy_with_ci(prompt_loose)["accuracy"],
            "inst_strict": accuracy_with_ci(inst_strict)["accuracy"],
            "inst_loose": accuracy_with_ci(inst_loose)["accuracy"],
            "n": len(prompt_strict),
            "constraints_evaluated": total_constraints - excluded,
            "constraints_excluded": excluded,
            # Publish this next to the score, always.
            "constraint_coverage": round(
                (total_constraints - excluded) / total_constraints, 4
            ) if total_constraints else 0.0,
            "exclusion_reasons": dict(sorted(exclusion_reasons.items(), key=lambda kv: -kv[1])),
            "by_instruction_type": {
                # Fewer than 15 instances is too few to report a rate for.
                k: {"n": v["n"],
                    "strict": round(v["strict"] / v["n"] * 100, 1),
                    "loose": round(v["loose"] / v["n"] * 100, 1)}
                for k, v in sorted(by_type.items()) if v["n"] >= 15
            },
        }
