"""End-to-end: dataset -> items -> model -> per-item records -> metrics."""

import json

from idrockbench.core import ModelResponse
from idrockbench.runner import evaluate_task, rescore_task
from idrockbench.tasks.dtm import DTMTask

ROWS = [
    {"id": 1, "question": "Ikki karra ikki necha?", "option_A": "3", "option_B": "4",
     "option_C": "5", "option_D": "6", "answer": "B", "subject": "matematika"},
    {"id": 2, "question": "Poytaxt qayer?", "option_A": "Toshkent", "option_B": "Samarqand",
     "option_C": "Buxoro", "option_D": "Xiva", "answer": "A", "subject": "tarix"},
    {"id": 3, "question": "Suvning formulasi?", "option_A": "CO2", "option_B": "H2O",
     "option_C": "O2", "option_D": "NaCl", "answer": "B", "subject": "fizika"},
]


def _run(tmp_path, provider, rows=ROWS):
    task = DTMTask(seed=1)
    items = task.prepare(rows)
    result = evaluate_task(
        task, items, provider, dataset_id="test.json", dataset_sha256="deadbeef",
        output_dir=tmp_path, concurrency=1,
    )
    return task, items, result


def test_perfect_model_scores_100(tmp_path, stub):
    task = DTMTask(seed=1)
    items = task.prepare(ROWS)
    # Answer each item with its own (post-shuffle) gold letter.
    replies = {it.payload["question"]: f"Javob: {it.gold}" for it in items}
    result = evaluate_task(task, items, stub(replies), dataset_id="d", dataset_sha256="x",
                           output_dir=tmp_path, concurrency=1)
    assert result.metrics["accuracy"] == 100.0
    assert result.diagnostics["coverage"] == 1.0


def test_api_errors_are_excluded_not_scored_zero(tmp_path, stub):
    # The old harness scored a network failure as a wrong answer, mixing
    # infrastructure into model quality.
    provider = stub({"Poytaxt": ConnectionError("connection reset")})
    task, items, result = _run(tmp_path, provider)
    assert result.diagnostics["error_rate"] > 0
    assert result.n_scored == 2                      # the failed item is excluded
    assert result.diagnostics["n_items"] == 3


def test_unparseable_responses_are_excluded_and_reported(tmp_path, stub):
    provider = stub({q: "Bilmayman." for q in ["Ikki", "Poytaxt", "Suvning"]})
    provider.default = "Bilmayman."
    task, items, result = _run(tmp_path, provider)
    assert result.diagnostics["unparsed_rate"] == 1.0
    assert result.n_scored == 0
    assert result.metrics["accuracy"] == 0.0


def test_per_item_records_are_written(tmp_path, stub):
    _run(tmp_path, stub())
    lines = (tmp_path / "dtm.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert len(rows) == 3
    for row in rows:
        assert {"item_id", "prompt", "response", "status", "extracted",
                "gold", "score", "meta"} <= set(row)


def test_resume_skips_completed_items(tmp_path, stub):
    provider = stub()
    _run(tmp_path, provider)
    first = len(provider.calls)
    provider2 = stub()
    _run(tmp_path, provider2)
    assert first == 3 and len(provider2.calls) == 0   # nothing re-queried


def test_resume_retries_failures(tmp_path, stub):
    provider = stub({"Poytaxt": ConnectionError("connection reset")})
    _run(tmp_path, provider)
    provider2 = stub()
    _run(tmp_path, provider2)
    # Only the failed item is retried, never the successful ones.
    assert len(provider2.calls) == 1 and "Poytaxt" in provider2.calls[0]


def test_rescore_recomputes_without_calling_the_model(tmp_path, stub):
    task, items, result = _run(tmp_path, stub())
    again = rescore_task(task, items, tmp_path / "dtm.jsonl",
                         dataset_id="d", dataset_sha256="x")
    assert again.metrics["accuracy"] == result.metrics["accuracy"]
    assert again.n_items == result.n_items


def test_breakdown_reports_each_subject_with_its_own_n(tmp_path, stub):
    task, items, result = _run(tmp_path, stub())
    assert set(result.breakdown["subject"]) == {"matematika", "tarix", "fizika"}
    for stats in result.breakdown["subject"].values():
        assert {"accuracy", "ci_low", "ci_high", "n", "coverage"} <= set(stats)


def test_truncation_is_distinct_from_a_wrong_answer(tmp_path, stub):
    class Truncating(type(stub())):
        def _complete(self, prompt, max_tokens):
            return ModelResponse(text="<think>Men o'ylayapman", finish_reason="length")

    task, items, result = _run(tmp_path, Truncating())
    assert result.diagnostics["truncated_rate"] == 1.0
    assert result.n_scored == 0


def test_items_with_no_answer_key_are_dropped_not_keyed_to_A(tmp_path):
    rows = ROWS + [{"id": 4, "question": "Nomalum", "option_A": "a", "option_B": "b",
                    "option_C": "c", "option_D": "d", "answer": None, "subject": "x"}]
    task = DTMTask(seed=1)
    assert len(task.prepare(rows)) == 3
    assert any("answer key" in p for p in task.validate(rows))


def test_output_file_is_named_by_config_not_task_class(tmp_path, stub):
    """One task implementation can be driven by several configs. If the
    per-item file were named by the class, rescore would look for a file the
    run never wrote and silently skip the task."""
    task = DTMTask(seed=1)
    items = task.prepare(ROWS)
    evaluate_task(task, items, stub(), dataset_id="d", dataset_sha256="x",
                  output_dir=tmp_path, name="dtm_2020", concurrency=1)
    assert (tmp_path / "dtm_2020.jsonl").exists()
    assert not (tmp_path / "dtm.jsonl").exists()


def test_yaml_off_is_not_parsed_as_a_boolean(tmp_path, monkeypatch):
    """YAML 1.1 turns a bare `off` into False. Unnoticed, a config that says
    `reasoning: off` leaves thinking enabled — which on a hard item burns the
    whole token budget and returns nothing."""
    import yaml

    from idrockbench.config import ModelConfig

    raw = yaml.safe_load("model: m\nprovider: ollama\nreasoning: off\n")
    assert raw["reasoning"] is False, "yaml really does do this"
    assert ModelConfig(**raw).reasoning == "off"


def test_run_ids_are_shell_safe():
    """A display name like "Llama 3.1 8B" must not become a directory with
    spaces in it — every downstream script then needs quoting to survive."""
    from idrockbench.cli import _slug

    assert _slug("DeepSeek-R1-Distill-Qwen 32B") == "deepseek-r1-distill-qwen-32b"
    assert _slug("qwen3.5:9b") == "qwen3.5-9b"
    assert _slug("kmamaroziqov/alloma-8b-q4") == "kmamaroziqov-alloma-8b-q4"
    assert _slug("!!!") == "run"


def test_a_task_can_override_the_model_reasoning_setting():
    """A task must be able to pin its own reasoning mode rather than inherit
    whatever a model config happens to set. Which mode a task needs is an
    empirical question, not a preference: with Ollama's `think` enabled,
    gemma4:26b spent its whole budget in the hidden thinking field and returned
    empty content on 92 of 93 truncated reasoning items."""
    from idrockbench.config import ModelConfig, TaskConfig

    model = ModelConfig(model="m", provider="ollama", reasoning="default")

    def resolve(task):
        return task.reasoning if task.reasoning is not None else model.reasoning

    # A task that pins its mode wins over the model default...
    reasoning = TaskConfig.load("reasoning_uz")
    assert reasoning.reasoning is not None, "reasoning task must pin its mode"
    assert resolve(reasoning) == reasoning.reasoning

    # ...and a task that does not pin one defers to the model.
    dtm = TaskConfig.load("dtm")
    assert dtm.reasoning is None, "knowledge task defers to the model"
    assert resolve(dtm) == "default"


def test_task_can_override_concurrency_and_timeout():
    """Concurrency and timeout follow generation length, which is a task
    property. A direct-answer task wants many short requests in flight; a
    reasoning task wants few long ones and a high ceiling. Sharing one setting
    cost 26 of 100 items to read timeouts on a single model."""
    from idrockbench.config import ModelConfig, TaskConfig

    model = ModelConfig(model="m", provider="ollama", concurrency=16, timeout=300)
    dtm, reasoning = TaskConfig.load("dtm"), TaskConfig.load("reasoning_uz")

    def resolve(task, attr):
        return getattr(task, attr) or getattr(model, attr)

    assert resolve(dtm, "concurrency") == 16, "short answers inherit the model's"
    assert resolve(reasoning, "concurrency") == 4, "long generations cap it"
    assert resolve(reasoning, "timeout") >= 900, "long generations need headroom"


def test_rescore_honours_only_the_latest_record_per_item(tmp_path, stub):
    """The per-item file is append-only, so a retried item appears twice — the
    `error` row and the `ok` row that replaced it. Reading line by line would
    score the superseded attempt as well, re-counting failures that were fixed
    and dragging the number back down."""
    provider = stub({"Poytaxt": ConnectionError("connection reset")})
    task, items, first = _run(tmp_path, provider)
    assert first.diagnostics["error_rate"] > 0

    _run(tmp_path, stub())          # resume retries the failure, appending a row

    lines = (tmp_path / "dtm.jsonl").read_text().splitlines()
    assert len(lines) > len(items), "the retry appended rather than replaced"

    again = rescore_task(task, items, tmp_path / "dtm.jsonl",
                         dataset_id="d", dataset_sha256="x")
    assert again.n_items == len(items), "one result per item, not one per line"
    assert again.diagnostics["error_rate"] == 0.0, "the superseded error must not count"
