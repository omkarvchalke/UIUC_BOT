import pytest

from app.evaluation.topic_regression_set import TOPIC_REGRESSION_SET, TopicCase
from app.retrieval.topic_classifier import TopicClassifier


def test_no_duplicate_messages() -> None:
    messages = [case.message for case in TOPIC_REGRESSION_SET]
    assert len(messages) == len(set(messages))


@pytest.fixture(scope="module")
def classifier() -> TopicClassifier:
    return TopicClassifier()


def _params() -> list[pytest.param]:
    params = []
    for case in TOPIC_REGRESSION_SET:
        marks = (
            pytest.mark.xfail(reason=case.xfail_reason, strict=True) if case.xfail_reason else ()
        )
        params.append(pytest.param(case, marks=marks, id=case.message[:60]))
    return params


@pytest.mark.parametrize("case", _params())
def test_classifies_topic_correctly(case: TopicCase, classifier: TopicClassifier) -> None:
    result = classifier.classify(case.message)
    assert result.topic is case.expected_topic
