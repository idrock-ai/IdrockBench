# Benchmark a new model

One YAML file. No code.

## 1. Write the config

Create `configs/models/<name>.yaml`:

```yaml
model: qwen3:32b            # exact id the provider expects
provider: ollama            # openai | anthropic | gemini | ollama | local
name: Qwen3 32B             # how it appears on the leaderboard
organization: Alibaba
license: apache-2.0         # SPDX id, or "proprietary"
weights_url: https://huggingface.co/Qwen/Qwen3-32B
params_b: 32
concurrency: 2
```

`license` is a factual claim about someone else's software, so it is declared here and never guessed. The old harness inferred it by substring-matching the model name, which published two Apache-2.0 models as closed and would have marked any model containing "yi" as open.

### Providers

| `provider` | For | Endpoint |
|---|---|---|
| `openai` | OpenAI API | `OPENAI_API_KEY` |
| `anthropic` | Claude | `ANTHROPIC_API_KEY` |
| `gemini` | Google | `GEMINI_API_KEY` |
| `ollama` | Local Ollama | `http://localhost:11434/v1` |
| `local` | vLLM, TGI, LM Studio, anything OpenAI-compatible | set `base_url` |

For a self-hosted server:

```yaml
model: meta-llama/Llama-3.1-70B-Instruct
provider: local
base_url: http://gpu-node-1:8000/v1
name: Llama 3.1 70B
organization: Meta
license: llama3.1
concurrency: 16
```

### Reasoning models

```yaml
reasoning: off      # Ollama: think=false; gpt-oss: think=low
```

Whatever you choose is recorded in the manifest. A thinking-enabled and a thinking-disabled run of the same model are different measurements, and a leaderboard that does not say which is which is not comparable.

## 2. Check it responds

```bash
idrockbench run --model qwen3-32b --tasks dtm --limit 10
```

Ten items, a few seconds. Look at the diagnostics line:

```
dtm: 60.0  [31.27, 83.18]  n=10/10  unparsed=0.0% truncated=0.0% errors=0.0%
```

- `errors > 0` - endpoint, key or network. Check `runs/<id>/dtm.jsonl` for the message.
- `truncated > 0` - raise `max_tokens` in the task config. A reasoning model needs room to finish.
- `unparsed > 0` - the model is not answering in a recognised format. Read a few responses before assuming the model is weak. A high unparsed rate is usually the harness's problem, not the model's.

## 3. Run the suite

```bash
idrockbench run --model qwen3-32b --suite core
```

Interruptions are safe. Re-running the same command resumes: completed items are skipped, failed ones retried.

```bash
idrockbench run --model qwen3-32b --suite core --run-id qwen3-32b-20260819
```

## 4. Inspect

```bash
idrockbench show runs/qwen3-32b-20260819
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

Before believing any of it, check three things:

1. **Coverage.** `n=989/989` means everything scored. `n=450/989` means over half the responses could not be parsed, and the number is about extraction, not knowledge.
2. **The chance level.** A DTM score near 25% is a coin flip. The runner prints a warning when a score sits at or below chance.
3. **The quantisation.** `Q4_K_M` is a 4-bit build, not the model its name suggests. It is resolved automatically for Ollama and recorded - publish it.

## 5. Publish

```bash
idrockbench report --suite core
```

Rebuilds `site/results.json` from `runs/` entirely. A cell no run produced cannot appear, and deleting a run removes it from the board. Never edit `results.json` by hand - the previous leaderboard was maintained that way and 20 of its 50 cells had no source run.

A model missing any suite task gets its per-task cells and **no composite score**. That is deliberate: a mean over three tasks and a mean over five are not comparable numbers.
