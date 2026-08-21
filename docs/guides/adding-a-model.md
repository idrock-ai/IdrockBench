# Adding a model

A model is one YAML file. No code is needed.

## 1. Write the config

Create `configs/models/<name>.yaml`:

```yaml
model: qwen3:32b            # id the provider expects
provider: ollama            # openai | anthropic | gemini | ollama | local
name: Qwen3 32B             # name shown on the leaderboard
organization: Alibaba
license: apache-2.0         # SPDX id, or "proprietary"
weights_url: https://huggingface.co/Qwen/Qwen3-32B
params_b: 32
concurrency: 2
```

The licence is always declared, never inferred from the model name.

| `provider` | For | Credentials or endpoint |
|---|---|---|
| `openai` | OpenAI API | `OPENAI_API_KEY` |
| `anthropic` | Claude | `ANTHROPIC_API_KEY` |
| `gemini` | Google | `GEMINI_API_KEY` |
| `ollama` | Local Ollama | `http://localhost:11434/v1` |
| `local` | vLLM, TGI, LM Studio or any OpenAI-compatible server | set `base_url` |

For reasoning models, `reasoning: off` disables thinking (Ollama `think=false`, gpt-oss `think=low`). The setting is recorded in the manifest, because runs with and without thinking are different measurements.

## 2. Check that it responds

```bash
idrockbench run --model qwen3-32b --tasks dtm --limit 10
```

```
dtm: 60.0  [31.27, 83.18]  n=10/10  unparsed=0.0% truncated=0.0% errors=0.0%
```

| Diagnostic | Cause |
|---|---|
| `errors` | Endpoint, key or network. Messages are in `runs/<model>/<run-id>/dtm.jsonl` |
| `truncated` | `max_tokens` is too low for this model |
| `unparsed` | The answer format was not recognised. Read a few responses before blaming the model |

## 3. Run the suite

```bash
idrockbench run --model qwen3-32b --suite core --run-id qwen3-32b-20260819
```

Running the same command again resumes the run: finished items are skipped and failed ones retried.

## 4. Inspect

```bash
idrockbench show runs/qwen3-32b/qwen3-32b-20260819
```

```
Run      qwen3-32b-20260819
Model    Qwen3 32B  (ollama)
Licence  apache-2.0   Quant Q4_K_M
Harness  2.0.0 @ a1b2c3d4e5f6

  dtm              58.3  [55.2, 61.4]  n=989/989  unparsed=0.0%  trunc=0.0%  err=0.0%
  reasoning_uz     41.2  [31.7, 51.4]  n=100/100  unparsed=0.0%  trunc=0.0%  err=0.0%
  translation_uz   54.1  [52.8, 55.3]  n=800/800  unparsed=0.0%  trunc=0.0%  err=0.0%
```

Check the coverage (`n=989/989` means every item was scored), the chance level (a DTM score near 25% is guessing) and the quantisation (`Q4_K_M` is a 4-bit build, recorded automatically for Ollama).

## 5. Publish

```bash
idrockbench report --suite core
```

This rebuilds `site/results.json` and the table in `LEADERBOARD.md` from `runs/`. A model missing a task gets a partial composite over the tasks it has.
