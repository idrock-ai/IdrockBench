"""Apostrophe-substitution proxy for the alloma models, in front of Ollama.

The alloma tokenizer has no Uzbek apostrophe. Its vocabulary instead contains
the literal string ``APST`` fused into Uzbek wordpieces -- ``oAPST``,
``ĠOAPSTzbekiston``, 7,357 entries in all -- because the training corpus was
preprocessed to replace every apostrophe variant with that placeholder. The
model card documents this and asks callers to do the same:

    We recommend preprocessing Uzbek input to replace apostrophe (') with
    sequence (APST) to achieve our model's lower tokenizer fertility.

Skipping it is not a neutral choice. Sending `oʻrmon` unsubstituted returns
`oAPSTrmon`: the prompt is out of distribution and every Uzbek word carrying
oʻ or gʻ comes back malformed. That would score the preprocessing step rather
than the model, so this proxy applies the card's own transformation -- the same
regex, the same langid guard, the same reverse mapping -- and the harness talks
to it exactly as it talks to Ollama.

The round trip is scoring-neutral: APST is restored as ASCII "'", and
idrockbench.text.normalize folds every apostrophe variant, ASCII included, to
U+02BB before matching. So this changes what the model receives, not how its
answer is judged.

One deliberate departure from the card's snippet: it prepends a "You are a
helpful assistant" system turn. Every other row on this board is sent a single
user message with no system prompt, so adding one here would be a protocol
difference rather than a fidelity fix. The apostrophe handling is about giving
the model input it was trained on; the system prompt is not.

    python tools/alloma_proxy.py --port 11503 --upstream http://127.0.0.1:11502
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: Verbatim from the model card's usage snippet.
PATTERN = r"[’‘‚‛ʻʼʽʾʿˈˊˋˌˍ'\']"
PLACEHOLDER = "APST"

try:
    import langid
except ImportError:  # pragma: no cover
    langid = None


def to_model(text: str) -> str:
    """Uzbek apostrophes -> APST, skipping English as the card's code does."""
    if langid is not None:
        lang, _ = langid.classify(text)
        if lang == "en":
            return text
    return re.sub(PATTERN, PLACEHOLDER, text)


def from_model(text: str) -> str:
    """APST -> apostrophe. ASCII, matching the card; the scorer folds it."""
    return text.replace(PLACEHOLDER, "'")


def _restore(data: dict) -> dict:
    """Undo the substitution in every response shape Ollama can return.

    Both shapes matter. The harness's Ollama provider deliberately calls the
    native /api/chat, which answers {"message": {"content": ...}}, while the
    OpenAI-compatible route answers {"choices": [{"message": ...}]}. An earlier
    version of this file handled only the latter, so the substitution went in
    and never came back out: responses still carried APST and nothing failed
    loudly. Cover both, and /api/generate's flat "response" too.
    """
    for msg in [data.get("message"), *[c.get("message") for c in
                                       (data.get("choices") or [])]]:
        if isinstance(msg, dict):
            for field in ("content", "thinking"):
                if isinstance(msg.get(field), str):
                    msg[field] = from_model(msg[field])
    if isinstance(data.get("response"), str):
        data["response"] = from_model(data["response"])
    return data


class Handler(BaseHTTPRequestHandler):
    upstream = "http://127.0.0.1:11502"

    def log_message(self, *_):  # keep the harness's output readable
        pass

    def _relay(self, path: str, payload: bytes | None):
        req = urllib.request.Request(
            self.upstream + path, data=payload, method=self.command,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, r.read()

    def do_GET(self):
        try:
            status, body = self._relay(self.path, None)
        except Exception as exc:
            self.send_error(502, str(exc))
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError as exc:
            self.send_error(400, f"bad json: {exc}")
            return

        for m in body.get("messages") or []:
            if isinstance(m.get("content"), str):
                m["content"] = to_model(m["content"])

        try:
            status, raw = self._relay(self.path, json.dumps(body).encode())
        except Exception as exc:
            self.send_error(502, str(exc))
            return

        try:
            data = json.loads(raw)
            raw = json.dumps(_restore(data)).encode()
        except ValueError:
            pass  # not JSON we understand; pass it through untouched

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11503)
    ap.add_argument("--upstream", default="http://127.0.0.1:11502")
    args = ap.parse_args()

    if langid is None:
        print("x langid not installed: every prompt would be treated as Uzbek, "
              "mangling apostrophes in English source text", file=sys.stderr)
        return 1

    probe = "oʻrmon, gʻalaba, koʻcha"
    assert to_model(probe) == "oAPSTrmon, gAPSTalaba, koAPSTcha", to_model(probe)
    assert from_model(to_model(probe)) == "o'rmon, g'alaba, ko'cha"
    assert _restore({"message": {"content": "oAPSTrmon"}})["message"]["content"] \
        == "o'rmon"
    assert _restore({"choices": [{"message": {"content": "oAPSTrmon"}}]}) \
        ["choices"][0]["message"]["content"] == "o'rmon"
    print(f"substitution self-test ok: {probe!r} -> {to_model(probe)!r}", flush=True)

    Handler.upstream = args.upstream
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"alloma proxy on 127.0.0.1:{args.port} -> {args.upstream}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
