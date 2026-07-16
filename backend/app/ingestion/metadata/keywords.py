"""Lightweight, dependency-free keyword extraction: RAKE (Rapid Automatic
Keyword Extraction, Rose et al. 2010).

Deliberately not the `rake-nltk` package: it downloads NLTK's stopwords
corpus from a network resource the first time it runs, which is exactly
the class of "surprise dependency" this project avoids everywhere else in
the ingestion pipeline (local CPU embeddings instead of a paid API,
pinned CPU-only torch wheels, robots.txt fetched once per domain rather
than assumed). RAKE itself is a simple, well-defined algorithm --
reimplementing it keeps the dependency list unchanged and behavior fully
deterministic and unit-testable with no model/network involved.
"""

import re
from collections import defaultdict

_WORD_PATTERN = re.compile(r"^[a-z][a-z'-]*$")
_PHRASE_DELIMITERS = re.compile(r"[.!?,;:()\[\]{}\"\n]+")

_STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
        "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
        "between", "both", "but", "by", "can", "cannot", "could", "couldn't", "did", "didn't",
        "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
        "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he",
        "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
        "into", "is", "isn't", "it", "its", "itself", "let's", "me", "more", "most", "must",
        "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
        "shouldn't", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
        "under", "until", "up", "very", "was", "wasn't", "we", "were", "weren't", "what",
        "when", "where", "which", "while", "who", "whom", "why", "will", "with", "won't",
        "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves",
    }
)  # fmt: skip

# Candidate phrases longer than this are still used to score word
# degree/frequency (a long stopword-free run is real co-occurrence
# signal) but excluded from the final ranked output -- an unbroken run of
# 6+ words is usually glued-together navigation/boilerplate text rather
# than a genuine keyphrase, and reads poorly as a piece of metadata next
# to short, punchy phrases like "registration holds".
_MAX_OUTPUT_PHRASE_WORDS = 4


def extract_keywords(text: str, *, max_keywords: int = 10) -> list[str]:
    """RAKE keyword extraction: splits text into candidate phrases at
    stopword/punctuation boundaries, scores each word by how much it
    co-occurs with other words in its candidate phrases (degree/frequency),
    scores each phrase as the sum of its words' scores, and returns the
    top max_keywords phrases (space-joined, lowercase, at most
    _MAX_OUTPUT_PHRASE_WORDS words each) by score, highest-first.
    """
    phrases = _candidate_phrases(text)
    if not phrases:
        return []

    word_scores = _score_words(phrases)
    best_score_per_phrase: dict[str, float] = {}
    for phrase in phrases:
        if len(phrase) > _MAX_OUTPUT_PHRASE_WORDS:
            continue
        key = " ".join(phrase)
        score = sum(word_scores[word] for word in phrase)
        if key not in best_score_per_phrase or score > best_score_per_phrase[key]:
            best_score_per_phrase[key] = score

    ranked = sorted(best_score_per_phrase.items(), key=lambda pair: pair[1], reverse=True)
    return [phrase for phrase, _ in ranked[:max_keywords]]


def _candidate_phrases(text: str) -> list[list[str]]:
    phrases: list[list[str]] = []
    for chunk in _PHRASE_DELIMITERS.split(text.lower()):
        current: list[str] = []
        for word in chunk.split():
            if word in _STOPWORDS or not _WORD_PATTERN.match(word):
                if current:
                    phrases.append(current)
                    current = []
            else:
                current.append(word)
        if current:
            phrases.append(current)
    return phrases


def _score_words(phrases: list[list[str]]) -> dict[str, float]:
    frequency: dict[str, int] = defaultdict(int)
    co_occurrence: dict[str, int] = defaultdict(int)
    for phrase in phrases:
        # Co-occurrence with every OTHER word in the same candidate phrase
        # -- a word appearing alone in its own phrase contributes 0 here.
        other_words_in_phrase = len(phrase) - 1
        for word in phrase:
            frequency[word] += 1
            co_occurrence[word] += other_words_in_phrase
    # RAKE's canonical word score: degree/frequency, where degree includes
    # the word's own frequency (so a word repeated often, even alone in
    # its own short phrases, still scores above one seen only once).
    return {word: (co_occurrence[word] + frequency[word]) / frequency[word] for word in frequency}
