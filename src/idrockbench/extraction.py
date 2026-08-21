from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass

from .text.normalize import normalize

CHOICE_LETTERS = "ABCDEFGHIJ"


class ParseStatus(enum.StrEnum):
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


NON_SCORING = frozenset({ParseStatus.UNPARSED, ParseStatus.TRUNCATED, ParseStatus.ERROR})


@dataclass(slots=True)
class Extraction:
    value: str | None
    status: ParseStatus = ParseStatus.OK
    strategy: str = ""
    evidence: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ParseStatus.OK and self.value is not None

    @classmethod
    def unparsed(cls, response: str, strategy: str = "") -> Extraction:
        return cls(None, ParseStatus.UNPARSED, strategy, evidence=response[-160:])


_THINK_CLOSED_RE = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_THINK_DANGLING_RE = re.compile(r"<(think|thinking|reasoning)>.*\Z", re.DOTALL | re.IGNORECASE)


def strip_reasoning(response: str) -> tuple[str, bool]:
    if not response:
        return "", False
    text = _THINK_CLOSED_RE.sub(" ", response)
    dangling = bool(_THINK_DANGLING_RE.search(text))
    if dangling:
        text = _THINK_DANGLING_RE.sub(" ", text)
    return text.strip(), dangling


def _valid_set(num_options: int) -> set[str]:
    n = max(1, min(num_options, len(CHOICE_LETTERS)))
    return set(CHOICE_LETTERS[:n])


def extract_choice(
    response: str,
    num_options: int,
    *,
    answer_words: tuple[str, ...] = ("javob", "answer", "ответ"),
) -> Extraction:
    if not response or not response.strip():
        return Extraction(None, ParseStatus.UNPARSED, "empty", "")

    visible, dangling = strip_reasoning(response)
    if not visible:
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "reasoning-only", response[-160:])

    valid = _valid_set(num_options)
    text = normalize(visible).strip()
    upper = text.upper()

    if len(text.strip(" .)*")) == 1 and text.strip(" .)*").upper() in valid:
        letter = text.strip(" .)*").upper()
        return Extraction(letter, strategy="bare-letter", evidence=text[:80])

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


_TAG_RE = re.compile(r"<solution>(.*?)</solution>", re.IGNORECASE | re.DOTALL)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def extract_tagged(response: str, tag: str = "solution") -> Extraction:
    visible, dangling = strip_reasoning(response)
    pattern = re.compile(rf"<{tag}>(.*?)</{tag}>", re.IGNORECASE | re.DOTALL)
    found = pattern.findall(visible)
    if found:
        return Extraction(found[-1].strip(), strategy=f"<{tag}>", evidence=found[-1][:120])
    status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
    return Extraction(None, status, f"<{tag}>", visible[-160:])


def extract_bold(response: str, *, reject_ambiguous: bool = True) -> Extraction:
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
    visible, dangling = strip_reasoning(response)
    if not visible.strip():
        status = ParseStatus.TRUNCATED if dangling else ParseStatus.UNPARSED
        return Extraction(None, status, "last-line", response[-160:])

    text = visible.strip()
    for prefix in strip_prefixes:
        pattern = re.compile(rf"^\s*{re.escape(prefix)}\s*[:\-—]?\s*", re.IGNORECASE)
        text = pattern.sub("", text, count=1)

    lines = [ln for ln in text.splitlines()]
    while lines and (not lines[0].strip() or lines[0].rstrip().endswith(":")):
        lines.pop(0)
    text = "\n".join(lines).strip().strip('"“”')

    if not text:
        return Extraction(None, ParseStatus.UNPARSED, "last-line", visible[-160:])
    return Extraction(text, strategy="last-line", evidence=text[:120])


def extract_json(response: str) -> Extraction:
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
