from app.ingestion.metadata.keywords import extract_keywords


def test_empty_text_returns_no_keywords() -> None:
    assert extract_keywords("") == []


def test_stopword_only_text_returns_no_keywords() -> None:
    assert extract_keywords("the a an of to in") == []


def test_extracts_a_real_multi_word_domain_phrase() -> None:
    text = (
        "Registration holds prevent students from registering for classes. "
        "Registration holds must be resolved before the student can register."
    )
    keywords = extract_keywords(text, max_keywords=5)
    assert "registration holds" in keywords or any("registration holds" in k for k in keywords)


def test_ranks_more_frequent_relevant_phrase_higher() -> None:
    # "financial aid" appears (as part of a longer phrase each time --
    # RAKE never sees it alone here, since no stopword ever separates it
    # from the next word) three times; "campus tour" appears once. RAKE
    # should rank the more heavily-repeated, more co-occurring phrase
    # first.
    text = (
        "Financial aid applications open in the fall. Financial aid covers tuition. "
        "Financial aid deadlines vary by program. A campus tour is optional."
    )
    keywords = extract_keywords(text, max_keywords=5)
    assert keywords[0].startswith("financial aid")
    assert keywords[0] != "campus tour"


def test_respects_max_keywords_limit() -> None:
    text = (
        "Housing options include residence halls, private certified housing, "
        "fraternity and sorority housing, and off campus apartments near the quad."
    )
    assert len(extract_keywords(text, max_keywords=2)) <= 2


def test_output_phrases_are_capped_at_four_words() -> None:
    # A long, punctuation-free run of non-stopwords (rare in real prose,
    # common in glued-together nav/boilerplate text) shouldn't produce an
    # unreadable multi-clause "keyword".
    text = "financial aid scholarships grants loans work study federal state programs available"
    for keyword in extract_keywords(text, max_keywords=10):
        assert len(keyword.split()) <= 4


def test_is_case_insensitive_and_output_is_lowercase() -> None:
    text = "Financial Aid deadlines. FINANCIAL AID covers tuition. financial aid applications."
    keywords = extract_keywords(text, max_keywords=3)
    assert keywords[0].startswith("financial aid")
    assert all(keyword == keyword.lower() for keyword in keywords)
