#!/usr/bin/env python3
"""Report how each model behaves before spending hours evaluating it.

Answers three questions per model, on one real benchmark item:

* Does it produce an answer at all within a small budget?
* Does it emit a reasoning trace, and is that trace suppressible?
* How many tokens does it actually need?

Run this whenever a model is added. A model that returns an empty string under
the configured budget will score zero on every item, and the failure looks
exactly like a weak model unless you check first.

    python tools/probe_models.py --host http://localhost:11434
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from idrockbench.config import ModelConfig, list_configs  # noqa: E402

PROMPT = (
    "Quyidagi test savoliga javob bering.\n"
    "Faqat bitta harf yozing (A, B, C yoki D). Hech qanday izoh yozmang.\n\n"
    "Savol: Qaysi gapda ega vazifasida kelgan so'z tarkibida jarangli undosh qatnashgan?\n\n"
    "A) Kitob keldi\nB) Bola yugurdi\nC) Ona keldi\nD) Dala keng\n\nJavob:"
)


def ask(host: str, model: str, num_predict: int, think=None, timeout: int = 400):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "keep_alive": "5m",
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    if think is not None:
        body["think"] = think
    req = urllib.request.Request(
        f"{host}/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    msg = d.get("message") or {}
    return {
        "secs": round(time.monotonic() - t0, 1),
        "tokens": d.get("eval_count", 0),
        "done": d.get("done_reason", "?"),
        "content": (msg.get("content") or "").strip(),
        "thinking": len(msg.get("thinking") or ""),
    }


def probe(host: str, cfg: ModelConfig) -> dict:
    out = {"config": cfg.name, "model": cfg.model}
    try:
        base = ask(host, cfg.model, 256)
    except Exception as exc:
        return {**out, "verdict": f"unreachable: {type(exc).__name__}"}

    out["thinks"] = base["thinking"] > 0 or (not base["content"] and base["done"] == "length")

    if base["content"] and base["done"] != "length":
        out.update(needs=256, reasoning="default", secs=base["secs"],
                   verdict="answers directly")
        return out

    # It did not answer in 256 tokens. Can thinking be turned off?
    try:
        off = ask(host, cfg.model, 256, think=False)
    except Exception:
        off = {"content": "", "done": "error", "secs": 0, "tokens": 0, "thinking": 0}
    if off["content"] and off["done"] != "length":
        out.update(needs=256, reasoning="off", secs=off["secs"],
                   verdict="answers with think=false")
        return out

    # Still nothing: find the budget at which it commits.
    for budget in (1024, 4096):
        try:
            r = ask(host, cfg.model, budget, think=False)
        except Exception:
            continue
        if r["content"] and r["done"] != "length":
            out.update(needs=budget, reasoning="off", secs=r["secs"],
                       verdict=f"needs {budget} tokens")
            return out
    out.update(needs=None, reasoning="off", secs=0,
               verdict="no answer even at 4096 — exclude or investigate")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--out", default="probe.json")
    args = ap.parse_args()

    names = args.models or [n for n in list_configs("models") if n != "stub"]
    results = []
    print(f"{'config':<22} {'thinks':<7} {'budget':>7} {'secs':>6}  verdict")
    print("-" * 78)
    for n in names:
        cfg = ModelConfig.load(n)
        if cfg.provider != "ollama":
            continue
        r = probe(args.host, cfg)
        results.append(r)
        print(f"{r['config']:<22} {str(r.get('thinks','?')):<7} "
              f"{str(r.get('needs') or '—'):>7} {r.get('secs', 0):>6}  {r['verdict']}")
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
