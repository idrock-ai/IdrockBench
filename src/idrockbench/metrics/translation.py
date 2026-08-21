"""Machine-translation metrics.

Two rules that the previous implementation broke:

* **Corpus-level, never a mean of sentence scores.** BLEU accumulates clipped
  n-gram counts and lengths across the whole test set before taking one ratio
  and one brevity penalty. Averaging per-sentence BLEU is a different statistic
  that matches no published number.
* **Normalise before scoring.** With the Uzbek modifier letter, the same
  correct sentence scores ~100 or ~20 BLEU depending on which apostrophe
  codepoint the model typed. Hypothesis and reference go through the same
  normalisation, and the report says so.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..text.normalize import cyrillic_ratio, normalize


def _sacrebleu():
    try:
        import sacrebleu
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Translation metrics need sacrebleu: pip install sacrebleu") from exc
    return sacrebleu


def corpus_scores(
    hypotheses: Sequence[str],
    references: Sequence[str],
    *,
    normalize_uz: bool = True,
) -> dict[str, object]:
    """Corpus chrF++, spBLEU and BLEU with their sacreBLEU signatures.

    chrF++ is the primary metric: it is tokeniser-free and robust to Uzbek
    agglutination, where a correct translation differing by one suffix is
    heavily punished by n-gram overlap. spBLEU keeps the numbers comparable to
    FLORES/NLLB. BLEU-13a is reported for legacy comparability only.

    The signature strings are part of the result, not decoration — a BLEU
    number without one is not reproducible.
    """
    sb = _sacrebleu()
    if len(hypotheses) != len(references):
        raise ValueError("hypotheses and references must be aligned and equal length")
    if not hypotheses:
        return {}

    prep = (lambda t: normalize(t)) if normalize_uz else (lambda t: t)
    hyps = [prep(h or "") for h in hypotheses]
    refs = [[prep(r or "") for r in references]]

    out: dict[str, object] = {"n_segments": len(hyps)}

    chrf = sb.CHRF(word_order=2)  # word_order=2 is what makes it chrF++
    res = chrf.corpus_score(hyps, refs)
    out["chrf2pp"] = round(res.score, 2)
    out["chrf2pp_signature"] = str(chrf.get_signature())

    bleu = sb.BLEU()
    res = bleu.corpus_score(hyps, refs)
    out["bleu"] = round(res.score, 2)
    out["bleu_signature"] = str(bleu.get_signature())

    try:
        spbleu = sb.BLEU(tokenize="flores200")
        res = spbleu.corpus_score(hyps, refs)
        out["spbleu"] = round(res.score, 2)
        out["spbleu_signature"] = str(spbleu.get_signature())
    except Exception:
        out["spbleu"] = None  # needs sentencepiece; optional

    # Script mismatch is a real property of the model and must not be folded
    # into the score: a correct Cyrillic answer against a Latin reference looks
    # like a translation failure when it is a script choice.
    mismatched = sum(1 for h in hyps if cyrillic_ratio(h) > 0.5)
    out["cyrillic_output_rate"] = round(mismatched / len(hyps), 4)
    out["normalization"] = "NFC; apostrophes folded to U+02BB" if normalize_uz else "none"
    return out


def bootstrap_ci(
    hypotheses: Sequence[str],
    references: Sequence[str],
    *,
    metric: str = "chrf2pp",
    n_samples: int = 500,
    seed: int = 12345,
) -> tuple[float, float]:
    """95% interval for a corpus metric, by resampling segments.

    Corpus BLEU and chrF have no closed-form interval, so a bare point estimate
    invites readers to rank differences that are inside the noise. Resampling
    the segment set with replacement gives a defensible one.
    """
    import random

    n = len(hypotheses)
    if n < 2:
        return (0.0, 0.0)
    rng = random.Random(seed)
    scores = []
    for _ in range(n_samples):
        idx = [rng.randrange(n) for _ in range(n)]
        sample = corpus_scores([hypotheses[i] for i in idx], [references[i] for i in idx])
        value = sample.get(metric)
        if value is not None:
            scores.append(value)
    if not scores:
        return (0.0, 0.0)
    scores.sort()
    lo = scores[int(0.025 * len(scores))]
    hi = scores[min(len(scores) - 1, int(0.975 * len(scores)))]
    return (round(lo, 2), round(hi, 2))


def sentence_chrf(hypothesis: str, reference: str) -> float:
    """Per-segment chrF++, for diagnostics and per-item inspection only.

    Never aggregate these into a headline number — use :func:`corpus_scores`.
    """
    sb = _sacrebleu()
    return sb.CHRF(word_order=2).sentence_score(
        normalize(hypothesis or ""), [normalize(reference or "")]
    ).score
