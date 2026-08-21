"""The shipped datasets must satisfy their task's invariants.

These run in CI. A dataset defect caught here cannot become a published number
— which is exactly how 147 unanswerable MMLU items and 8 keyless DTM items
reached a public leaderboard.
"""

import pytest

from idrockbench.config import TaskConfig, list_configs
from idrockbench.data.loader import load
from idrockbench.registry import get_task

TASKS = list_configs("tasks")

# Tracks with known, documented gaps. They stay out of the publishable suite
# until the gap closes; the reason is asserted so it cannot be forgotten.
KNOWN_GAPS = {
    "ifeval_uz": "98 constraints still need Uzbek terms from a native speaker; "
                 "excluded constraints are counted, never silently passed",
}


@pytest.fixture(scope="module", params=TASKS)
def task_and_rows(request):
    cfg = TaskConfig.load(request.param)
    task = get_task(cfg.task)(seed=cfg.seed, options=cfg.options)
    return request.param, task, load(cfg.dataset, split=cfg.split).rows


def test_dataset_loads_and_produces_items(task_and_rows):
    name, task, rows = task_and_rows
    assert rows, f"{name}: dataset is empty"
    assert task.prepare(rows), f"{name}: no items survived prepare()"


def test_dataset_validates_clean(task_and_rows):
    name, task, rows = task_and_rows
    problems = task.validate(rows)
    if name in KNOWN_GAPS:
        pytest.xfail(KNOWN_GAPS[name])
    assert not problems, f"{name}:\n" + "\n".join(f"  - {p}" for p in problems[:10])


def test_every_item_has_a_gold_answer(task_and_rows):
    name, task, rows = task_and_rows
    for item in task.prepare(rows):
        assert item.gold not in (None, ""), f"{name}: item {item.id} has no gold answer"


def test_prompts_are_non_empty_and_stable(task_and_rows):
    name, task, rows = task_and_rows
    items = task.prepare(rows)[:25]
    for item in items:
        prompt = task.build_prompt(item)
        assert prompt.strip(), f"{name}: item {item.id} produced an empty prompt"
        assert task.build_prompt(item) == prompt, f"{name}: prompt is not deterministic"


def test_task_declares_a_version(task_and_rows):
    _, task, _ = task_and_rows
    assert task.version, "every task must declare a version so scores stay comparable"


def test_multiple_choice_gold_is_always_shown_to_the_model(task_and_rows):
    """The defect that made MMLU-Pro unmeasurable: the correct answer was not
    among the options rendered into the prompt for 73.5% of items."""
    name, task, rows = task_and_rows
    from idrockbench.extraction import CHOICE_LETTERS
    for item in task.prepare(rows):
        options = item.payload.get("options")
        if not options:
            continue
        assert item.gold in CHOICE_LETTERS[: len(options)], (
            f"{name}: item {item.id} keys answer {item.gold} but renders "
            f"only {len(options)} options"
        )


def test_ifeval_localisation_is_grounded_and_consistent():
    """Derived Uzbek constraint arguments must appear in the Uzbek prompt, and
    one English term must never map to two different Uzbek terms.

    A wrong argument is worse than a missing one: a missing one is excluded and
    counted in `constraint_coverage`, a wrong one silently scores every model
    against a string nobody asked for. Aligning by first occurrence in the
    English prose once mapped `slow` to `bola` ("child"), because `like` and
    `kid` appeared earlier as ordinary words.
    """
    import collections

    from idrockbench.data.loader import load

    rows = load("ifeval_uz.json").rows
    mapping = collections.defaultdict(set)
    ungrounded = []

    for row in rows:
        prompt_uz = (row.get("prompt_uz") or "").lower()
        ids = row.get("instruction_id_list") or []
        base = [{k: v for k, v in (kw or {}).items() if v is not None}
                for kw in (row.get("kwargs") or [])]
        loc = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
        loc += [{}] * (len(ids) - len(loc))

        for i in range(len(ids)):
            kw = base[i] if i < len(base) else {}
            pairs = []
            for key in ("keywords", "forbidden_words"):
                if key in loc[i] and key in kw:
                    pairs += list(zip(kw[key], loc[i][key], strict=False))
            for key in ("keyword", "first_word"):
                if key in loc[i] and key in kw:
                    pairs.append((kw[key], loc[i][key]))
            for en, uz in pairs:
                if not en or not uz:
                    continue
                mapping[en.lower()].add(uz.lower())
                if uz.lower() not in prompt_uz:
                    ungrounded.append((row.get("key"), en, uz))

    assert not ungrounded, f"derived terms absent from their prompt: {ungrounded[:5]}"
    conflicts = {k: v for k, v in mapping.items() if len(v) > 1}
    assert not conflicts, f"one English term mapped to several Uzbek terms: {conflicts}"


def test_ifeval_reports_its_own_constraint_coverage():
    """The score must never travel without the share of constraints it covers.
    Roughly a third still cannot be evaluated in Uzbek."""
    from idrockbench.core import ItemResult
    from idrockbench.data.loader import load
    from idrockbench.extraction import ParseStatus
    from idrockbench.tasks.ifeval_uz import IFEvalUzTask

    task = IFEvalUzTask()
    items = task.prepare(load("ifeval_uz.json").rows)
    results = []
    for item in items[:120]:
        extraction = task.parse("Salom.", item)
        results.append(ItemResult(
            item_id=item.id, prompt="", response="Salom.", status=ParseStatus.OK,
            extracted="Salom.", gold=item.gold, score=task.score(extraction, item),
            meta=dict(item.meta)))
    metrics = task.aggregate(results)
    assert "constraint_coverage" in metrics
    assert 0.0 < metrics["constraint_coverage"] <= 1.0
    assert metrics["constraints_excluded"] > 0, "exclusions must be counted, not hidden"


def test_response_language_scores_without_localised_kwargs():
    """The kwarg is an ISO 639-1 code — `hi` means Hindi whatever language the
    prompt is written in. Requiring an Uzbek "translation" of it excluded 31
    constraints that needed no translation at all."""
    from idrockbench.tasks._ifeval_checkers import Disposition, REGISTRY

    checker = REGISTRY["language:response_language"]
    assert checker.disposition is not Disposition.NEEDS_LOCALE

    pytest.importorskip("lingua")
    assert checker.fn("नमस्ते, मैं ठीक हूँ। आज मौसम अच्छा है।", {"language": "hi"}, "")
    assert not checker.fn("Salom, men yaxshiman. Bugun havo yaxshi.",
                          {"language": "hi"}, "")


def test_constrained_response_uses_the_canonical_uzbek_triple():
    """Upstream IFEval holds the yes/no/maybe phrases inside the checker rather
    than passing them as a kwarg, so all ten rows arrive with an empty
    `allowed_responses`. Treating that as "not localised" excluded every one of
    them."""
    from idrockbench.tasks._ifeval_checkers import REGISTRY

    fn = REGISTRY["detectable_format:constrained_response"].fn
    assert fn("Mening javobim ha.", {}, "")
    # Apostrophe variants are one string after normalisation.
    assert fn("Mening javobim yo'q.", {}, "")
    # Containment, as upstream does it: requiring the whole response to equal
    # the phrase fails any model that adds a word of commentary.
    assert fn("Mening javobim ehtimol. Chunki maʻlumot yetarli emas.", {}, "")
    assert not fn("Ha, albatta.", {}, "")


def test_ifeval_coverage_does_not_regress():
    """Coverage is the number that decides whether the track is publishable, so
    a change that quietly excludes more constraints must fail here."""
    from idrockbench.data.loader import load
    from idrockbench.tasks._ifeval_checkers import Disposition, REGISTRY

    rows = load("ifeval_uz.json").rows
    total = scored = 0
    for row in rows:
        ids = row.get("instruction_id_list") or []
        uz = [dict(k or {}) for k in (row.get("kwargs_uz") or [])]
        uz += [{} for _ in range(len(ids) - len(uz))]
        for i, iid in enumerate(ids):
            total += 1
            checker = REGISTRY.get(iid)
            if checker is None or checker.disposition is Disposition.DROPPED:
                continue
            if checker.disposition is Disposition.NEEDS_LOCALE and not uz[i]:
                continue
            scored += 1
    assert total == 834
    assert scored / total >= 0.736, f"coverage regressed to {scored / total:.1%}"
