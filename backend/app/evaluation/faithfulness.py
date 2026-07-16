"""Heuristic Faithfulness / Groundedness scoring: no LLM calls, always
runs in pytest/CI. Given an answer and its cited context, scores whether
each sentence's claims are lexically supported by the context.

RAGAS treats "faithfulness" and "groundedness" as near-synonymous (both
ask "is the answer's content supported by the retrieved context") -- this
module implements one scorer and the eval report labels its output
"Faithfulness / Groundedness" rather than building two thin, duplicate
wrappers around the same computation just to match two separate names.

A separate, opt-in LLM-judge scorer (app/evaluation/llm_judge.py) exists
for an occasional higher-fidelity manual run; this module is the always-on
default specifically because it makes zero extra Groq calls.
"""

import re

from app.ingestion.metadata.keywords import _STOPWORDS

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_MIN_CONTENT_WORD_LENGTH = 3


def split_sentences(text: str) -> list[str]:
    """Splits on sentence-ending punctuation followed by a capitalized/
    numeric/quoted word. Doesn't special-case abbreviations (e.g. "U.S.
    News" could false-split) -- an acceptable limitation for an offline
    heuristic scorer, not a blocker.
    """
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _content_words(text: str) -> set[str]:
    words = _WORD_PATTERN.findall(text.lower())
    return {w for w in words if len(w) >= _MIN_CONTENT_WORD_LENGTH and w not in _STOPWORDS}


def _sentence_score(sentence: str, context_words: set[str]) -> float | None:
    words = _content_words(sentence)
    if not words:
        return None  # no claim to verify (e.g. "OK." or pure punctuation)
    return len(words & context_words) / len(words)


def score_faithfulness(answer: str, context: str) -> float | None:
    """Mean per-sentence lexical-support score, or None if the answer has
    zero scoreable sentences (e.g. empty, or every sentence is stopwords-
    only) -- None, not 0.0, since 0.0 would misleadingly read as "totally
    unfaithful" rather than "nothing to score".
    """
    context_words = _content_words(context)
    scores = [
        score
        for sentence in split_sentences(answer)
        if (score := _sentence_score(sentence, context_words)) is not None
    ]
    if not scores:
        return None
    return sum(scores) / len(scores)
