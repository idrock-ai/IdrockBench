"""Answer extraction.

Two rules distinguish this from the usual regex-in-the-scorer approach:

1. **An unparseable response is not a wrong answer.** It returns
   :attr:`ParseStatus.UNPARSED` and is reported separately. Collapsing the two
   makes a broken extractor indistinguishable from a weak model — the failure
   mode that put a 10-option benchmark below its own random baseline.

2. **Extraction runs on normalised text, anchored at the end.** Uzbek
   apostrophes split words into fragments that look like option letters
   ("to'g'ri" -> TO, G, RI), so an unanchored ``\\b[A-J]\\b`` scan finds the
   word "correct" before it finds the answer.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass

from .text.normalize import normalize

CHOICE_LETTERS = "ABCDEFGHIJ"


class ParseStatus(enum.StrEnum):
    """Why an item produced (or failed to produce) an answer."""

    OK = "ok"
    """A well-formed answer was extracted."""

    UNPARSED = "unparsed"
    """The model responded, but no answer could be extracted. Excluded from the
    accuracy denominator and reported as ``unparsed_rate``."""

    TRUNCATED = "truncated"
    """The response hit the token limit. Excluded from accuracy; reported as
    ``truncated_rate``. A truncated reasoning trace is not a wrong answer."""

    ERROR = "error"
    """The request failed after retries. Excluded from accuracy; reported as
    ``error_rate``. Infrastructure failure is never model quality."""

    REFUSAL = "refusal"
    """The model declined. Counted as incorrect — a refusal is performance."""


#: Statuses that must not enter the accuracy denominator.
NON_SCORING = frozenset({ParseStatus.UNPARSED, ParseStatus.TRUNCATED, ParseStatus.ERROR})


@dataclass(slots=True)
class Extraction:
    """The result of pulling an answer out of a model response."""

    value: str | None
    status: ParseStatus = ParseStatus.OK
    #: Which strategy matched, for debugging a whole run at once.
    strategy: str = ""
    #: The span the answer came from, so a reviewer can check without the raw log.
    evidence: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ParseStatus.OK and self.value is not None

    @classmethod
    def unparsed(cls, response: str, strategy: str = "") -> Extraction:
        return cls(None, ParseStatus.UNPARSED, strategy, evidence=response[-160:])


# --------------------------------------------------------------------------
# Reasoning-trace handling
# --------------------------------------------------------------------------

_THINK_CLOSED_RE = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_THINK_DANGLING_RE = re.compile(r"<(think|thinking|reasoning)>.*\Z", re.DOTALL | re.IGNORECASE)


def strip_reasoning(response: str) -> tuple[str, bool]:
    """Remove reasoning-trace blocks from a response.

    Handles the *unterminated* case as well as the closed one. A reasoning
    model that hits its token budget mid-trace leaves an open ``<think>`` with
    no closing tag; leaving it in means the scorer reads an answer out of
    unfinished deliberation.

    Returns:
        ``(visible_text, was_truncated_mid_trace)``.
    """
    if not response:
        return "", False
    text = _THINK_CLOSED_RE.sub(" ", response)
    dangling = bool(_THINK_DANGLING_RE.search(text))
    if dangling:
        text = _THINK_DANGLING_RE.sub(" ", text)
    return text.strip(), dangling


# --------------------------------------------------------------------------
# Multiple choice
# --------------------------------------------------------------------------

def _valid_set(num_options: int) -> set[str]:
    n = max(1, min(num_options, len(CHOICE_LETTERS)))
    return set(CHOICE_LETTERS[:n])


def extract_choice(
    response: str,
    num_options: int,
    *,
    answer_words: tuple[str, ...] = ("javob", "answer", "ответ"),
) -> Extraction:
    """Extract a multiple-choice letter.

    Strategies are tried in order of how strongly each implies intent, and the
    first match wins:

    1. The whole (visible) response is a single letter.
    2. An explicit answer cue — "Javob: B", "**B**", "\\boxed{B}".
    3. A letter on its own at the very end of the last line, optionally
       bracketed or followed by ``)`` / ``.``.
    4. A leading ``B)`` style option label on the last line.

    There is deliberately no "scan the whole response and take the first/last
    letter" fallback. That heuristic is what made an Uzbek word for "correct"
    read as answer G, and it fabricates an answer from prose often enough to
    make a refusal look like a guess. When none of the four strategies match,
    the item is :attr:`ParseStatus.UNPARSED`.

    Args:
        response: Raw model output.
        num_options: How many options were actually rendered into the prompt.
            Letters beyond this are rejected — a model cannot have chosen an
            option it was never shown.
        answer_words: Cue words introducing the answer, lowercased.
    """
    if not response or not response.strip():
        return Extraction(None, ParseStatus.UNPARSED, "empty", "")

    visible, dangling = strip_reasoning(response)
    if not visible:
        # The response was nothing but an (unterminated) reasoning trace.
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "reasoning-only", response[-160:])

    valid = _valid_set(num_options)
    text = normalize(visible).strip()
    upper = text.upper()

    # 1. Bare letter.
    if len(text.strip(" .)*")) == 1 and text.strip(" .)*").upper() in valid:
        letter = text.strip(" .)*").upper()
        return Extraction(letter, strategy="bare-letter", evidence=text[:80])

    # 2. Explicit cue. Search from the end: models often restate the question
    #    before answering, and the final cue is the committed answer.
    cues = "|".join(re.escape(w) for w in answer_words)
    cue_re = re.compile(
        rf"(?:{cues})\s*(?:hisoblanadi|bo\S*lardi)?\s*[:\-—]?\s*\**\(?([A-J])\)?\**",
        re.IGNORECASE,
    )
    matches = list(cue_re.finditer(upper))
    if matches and matches[-1].group(1) in valid:
        m = matches[-1]
        return Extraction(m.group(1), strategy="answer-cue", evidence=m.group(0)[:80])

    boxed = list(re.finditer(r"\\boxed\s*\{\s*([A-J])\s*\}", upper, re.IGNORECASE))
    if boxed and boxed[-1].group(1) in valid:
        return Extraction(boxed[-1].group(1), strategy="boxed", evidence=boxed[-1].group(0))

    bold = list(re.finditer(r"\*\*\s*\(?([A-J])\)?\s*\**", upper))
    if bold and bold[-1].group(1) in valid:
        return Extraction(bold[-1].group(1), strategy="bold", evidence=bold[-1].group(0))

    # 3 & 4. Last non-empty line, anchored.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        last = lines[-1].upper()
        tail = re.search(r"\(?([A-J])\)?\s*[.):]?\s*$", last)
        if tail and tail.group(1) in valid:
            return Extraction(tail.group(1), strategy="line-tail", evidence=last[-60:])
        head = re.match(r"^\**\(?([A-J])\)?\s*[.):]\s+\S", last)
        if head and head.group(1) in valid:
            return Extraction(head.group(1), strategy="option-label", evidence=last[:60])

    status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
    return Extraction(None, status, "no-match", visible[-160:])


# --------------------------------------------------------------------------
# Free text
# --------------------------------------------------------------------------

_TAG_RE = re.compile(r"<solution>(.*?)</solution>", re.IGNORECASE | re.DOTALL)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def extract_tagged(response: str, tag: str = "solution") -> Extraction:
    """Extract the content of the last ``<tag>...</tag>`` block."""
    visible, dangling = strip_reasoning(response)
    pattern = re.compile(rf"<{tag}>(.*?)</{tag}>", re.IGNORECASE | re.DOTALL)
    found = pattern.findall(visible)
    if found:
        return Extraction(found[-1].strip(), strategy=f"<{tag}>", evidence=found[-1][:120])
    status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
    return Extraction(None, status, f"<{tag}>", visible[-160:])


def extract_bold(response: str, *, reject_ambiguous: bool = True) -> Extraction:
    """Extract the content of the last ``**bold**`` span.

    Only the *last* span: accepting any of the last N spans lets a model hedge
    with several candidates and be credited for whichever happens to be right.

    With ``reject_ambiguous``, a final line offering several *different* bold
    candidates ("**2**, **3** yoki **4**") is UNPARSED rather than resolved to
    the last one. A hedge is not an answer, and crediting it rewards models that
    decline to commit.
    """
    visible, dangling = strip_reasoning(response)
    found = _BOLD_RE.findall(visible)
    if not found:
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "bold", visible[-160:])

    if reject_ambiguous:
        lines = [ln for ln in visible.splitlines() if ln.strip()]
        last_line = lines[-1] if lines else visible
        on_last = {b.strip().casefold() for b in _BOLD_RE.findall(last_line)}
        if len(on_last) > 1:
            return Extraction(
                None, ParseStatus.UNPARSED, "bold-ambiguous", last_line[:160]
            )
    return Extraction(found[-1].strip(), strategy="bold", evidence=found[-1][:120])


def extract_last_line(response: str, *, strip_prefixes: tuple[str, ...] = ()) -> Extraction:
    """Extract the full trailing block of a response.

    Keeps *all* trailing lines rather than only the first, so a model that
    writes a preamble followed by a multi-line answer is scored on its answer.
    Taking only the first line is how a correct multi-sentence translation
    scores BLEU 0.
    """
    visible, dangling = strip_reasoning(response)
    if not visible.strip():
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "last-line", response[-160:])

    text = visible.strip()
    for prefix in strip_prefixes:
        pattern = re.compile(rf"^\s*{re.escape(prefix)}\s*[:\-—]?\s*", re.IGNORECASE)
        text = pattern.sub("", text, count=1)

    # A preamble ending in ":" on its own line is a lead-in, not the answer.
    lines = [ln for ln in text.splitlines()]
    while lines and (not lines[0].strip() or lines[0].rstrip().endswith(":")):
        lines.pop(0)
    text = "\n".join(lines).strip().strip('"“”')

    if not text:
        return Extraction(None, ParseStatus.UNPARSED, "last-line", visible[-160:])
    return Extraction(text, strategy="last-line", evidence=text[:120])


def extract_json(response: str) -> Extraction:
    """Extract a JSON document that constitutes the whole response.

    Markdown fences are stripped first. There is deliberately no "find a JSON
    object somewhere inside the prose" fallback: the constraint being tested is
    that the *entire* response is JSON.
    """
    visible, dangling = strip_reasoning(response)
    text = visible.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text).strip()
    if not text:
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "json", visible[-160:])
    try:
        json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return Extraction(None, ParseStatus.UNPARSED, "json", text[:160])
    return Extraction(text, strategy="json", evidence=text[:120])
