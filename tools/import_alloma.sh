#!/usr/bin/env bash
# Import the three alloma-Instruct models into Ollama on the DGX Spark, at the
# precision they were released in.
#
# These ship as safetensors only, with no GGUF in the registry, so they have to
# be converted before Ollama can serve them. `ollama create` is left WITHOUT
# --quantize deliberately: the default path preserves the source dtype, and any
# quantisation here would put a 4-bit row on a board where nothing else is
# quantised below the weights its authors published. The precision each model
# ends up at is printed and asserted below rather than assumed.
#
# Stock LlamaForCausalLM (Llama-3 lineage, vocab 128257), so no remote code and
# no shim: these run through the same Ollama path as the other fourteen models.
#
# Takes the sizes to import, so a model whose download has not finished is not
# imported half-complete: config.json lands first and its shards last, so
# presence of the directory proves nothing.
#     bash import_alloma.sh 1B 3B
set -uo pipefail

SIZES=("$@")
[ ${#SIZES[@]} -gt 0 ] || SIZES=(1B 3B 8B)

for s in "${SIZES[@]}"; do
  DIR=~/alloma/$s
  TAG="alloma-${s,,}"          # alloma-1b, alloma-3b, alloma-8b
  echo
  echo "════════ $TAG ════════"
  [ -f "$DIR/config.json" ] || { echo "  x $DIR not downloaded"; continue; }
  if [ -f "$DIR/model.safetensors.index.json" ]; then
    MISSING=$(python3 - "$DIR" <<'PY'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
idx = json.loads((d / "model.safetensors.index.json").read_text())
print(sum(1 for f in set(idx["weight_map"].values()) if not (d / f).exists()))
PY
)
    [ "$MISSING" = "0" ] || { echo "  x $s incomplete: $MISSING shard(s) missing"; continue; }
  fi

  printf 'FROM %s\n' "$DIR" > "$DIR/Modelfile"
  if ! ollama create "$TAG" -f "$DIR/Modelfile" 2>&1 | tail -3; then
    echo "  x create failed"; continue
  fi

  # Refuse to go further if the import silently quantised. A q4 row would be a
  # different model from the one the card describes, and the score would be
  # attributed to the authors' weights.
  PREC=$(ollama show "$TAG" 2>/dev/null | grep -iE "quantization" | awk '{print $NF}')
  echo "  precision: ${PREC:-unknown}"
  case "${PREC^^}" in
    F16|BF16|F32) echo "  ✓ unquantised" ;;
    *) echo "  ✗ $TAG imported as ${PREC:-unknown} — NOT bf16/f16, do not benchmark" ;;
  esac
done

echo
ollama list | grep -E "alloma|NAME"
