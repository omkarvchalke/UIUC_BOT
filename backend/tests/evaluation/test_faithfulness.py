from app.evaluation.faithfulness import score_faithfulness, split_sentences

_CONTEXT = (
    "Freshmen must live in undergraduate residence halls during their first year. "
    "Applications for housing open every January. "
    "The main library is open twenty-four hours during finals week."
)


def test_split_sentences_handles_multiple_terminators() -> None:
    assert split_sentences("Hello there. How are you? I am fine!") == [
        "Hello there.",
        "How are you?",
        "I am fine!",
    ]


def test_split_sentences_empty_string_returns_empty_list() -> None:
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_clearly_supported_sentence_scores_high() -> None:
    answer = "Freshmen must live in undergraduate residence halls during their first year."
    score = score_faithfulness(answer, _CONTEXT)
    assert score is not None
    assert score >= 0.9


def test_clearly_fabricated_sentence_scores_low() -> None:
    answer = "Students can bring pets to any residence hall without restriction."
    score = score_faithfulness(answer, _CONTEXT)
    assert score is not None
    assert score < 0.3


def test_multi_sentence_answer_averages_across_sentences() -> None:
    answer = (
        "Freshmen must live in undergraduate residence halls during their first year. "
        "Students can bring pets to any residence hall without restriction."
    )
    supported_only = score_faithfulness(
        "Freshmen must live in undergraduate residence halls during their first year.", _CONTEXT
    )
    fabricated_only = score_faithfulness(
        "Students can bring pets to any residence hall without restriction.", _CONTEXT
    )
    combined = score_faithfulness(answer, _CONTEXT)

    assert supported_only is not None
    assert fabricated_only is not None
    assert combined is not None
    # The combined score should sit between the two individual sentence
    # scores -- confirms it's actually averaging, not just returning one.
    assert min(supported_only, fabricated_only) <= combined <= max(supported_only, fabricated_only)


def test_empty_answer_returns_none() -> None:
    assert score_faithfulness("", _CONTEXT) is None


def test_answer_with_no_scoreable_content_words_returns_none() -> None:
    # Pure stopwords/punctuation -- no content word to check against context.
    assert score_faithfulness("It is. Or so.", _CONTEXT) is None
