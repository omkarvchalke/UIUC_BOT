from app.models.document import Topic
from app.retrieval.topic_classifier import TopicClassifier


def test_classifies_clear_housing_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("Where do freshmen live on campus? What are the dorms like?")
    assert result.topic is Topic.HOUSING
    assert result.confidence > 0.55


def test_classifies_clear_opt_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How do I apply for optional practical training after graduation?")
    assert result.topic is Topic.OPT


def test_classifies_clear_dining_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What meal plans are available in the dining halls?")
    assert result.topic is Topic.DINING


def test_ambiguous_message_returns_none_topic_with_low_confidence() -> None:
    classifier = TopicClassifier(confidence_threshold=0.99)
    result = classifier.classify("hmm okay")
    assert result.topic is None


def test_higher_threshold_makes_classification_stricter() -> None:
    lenient = TopicClassifier(confidence_threshold=0.01)
    strict = TopicClassifier(confidence_threshold=0.99)
    message = "tell me about stuff"

    lenient_result = lenient.classify(message)
    strict_result = strict.classify(message)

    assert lenient_result.topic is not None
    assert strict_result.topic is None
