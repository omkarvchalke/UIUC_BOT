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
    assert result.topic is Topic.INTERNATIONAL_STUDENTS_IMMIGRATION


def test_classifies_clear_dining_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What meal plans are available in the dining halls?")
    assert result.topic is Topic.DINING


def test_classifies_career_services_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What career services does UIUC offer, like resume help?")
    assert result.topic is Topic.CAREER_EMPLOYMENT


def test_classifies_academic_advising_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How do I contact my academic advisor?")
    assert result.topic is Topic.ACADEMIC_ADVISING


def test_opt_out_of_health_insurance_is_not_misclassified_as_opt() -> None:
    # Regression test for a real finding from a 200-question sweep: "opt
    # out" surface-overlapped Topic.INTERNATIONAL_STUDENTS_IMMIGRATION's description closely enough to
    # win (0.644 vs 0.637), returning a completely unrelated MTD
    # privacy-policy chunk for a health-insurance question.
    classifier = TopicClassifier()
    result = classifier.classify("Can I opt out of the mandatory health insurance?")
    assert result.topic is Topic.HEALTH_WELLNESS


def test_classifies_illinois_commitment_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What is the Illinois Commitment program?")
    assert result.topic is Topic.FINANCIAL_AID_SCHOLARSHIPS
    assert result.confidence > 0.55


def test_classifies_hire_illini_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What is Hire Illini?")
    assert result.topic is Topic.CAREER_EMPLOYMENT
    assert result.confidence > 0.55


def test_classifies_isss_acronym_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What does ISSS stand for and what do they do?")
    assert result.topic is Topic.INTERNATIONAL_STUDENTS_IMMIGRATION
    assert result.confidence > 0.55


def test_classifies_mtd_bus_pass_question() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How much does an MTD bus pass cost?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_icard_banking_question_as_financial_aid_not_visa() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What banking options are available through the i-card?")
    assert result.topic is Topic.FINANCIAL_AID_SCHOLARSHIPS


def test_classifies_refund_overpayment_question_as_financial_aid_costs() -> None:
    # Was FINANCIAL_AID_SCHOLARSHIPS under the previous taxonomy (where "billing refunds and
    # overpayments" lived in that topic's single description) -- Source Manifest V2 splits
    # registrar billing/refund content into its own narrow FINANCIAL_AID_COSTS topic, and this
    # query is exactly what that split was for.
    classifier = TopicClassifier()
    result = classifier.classify("Are there refund options for overpayment?")
    assert result.topic is Topic.FINANCIAL_AID_COSTS
    assert result.confidence > 0.55


def test_classifies_parking_permit_renewal_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How do I renew my parking permit?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_parking_ticket_appeal_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What's the process to appeal a parking ticket?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_realtime_bus_tracking_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How do I track the campus bus in real time?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_willard_airport_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("Does UIUC have its own airport?")
    assert result.topic is Topic.TRANSPORTATION_PARKING


def test_classifies_ohare_airport_question_as_transportation() -> None:
    # Regression test for a real finding from a retest sweep: a version of
    # Topic.TRANSPORTATION_PARKING's description packed with narrow parking/ticket/
    # bus-tracking phrases lost this query to Topic.ADMISSIONS. Fixed by
    # rewriting the description as one coherent sentence naming Chicago/
    # O'Hare/Midway explicitly instead of relying on "Willard Airport" alone
    # to imply intercity travel.
    classifier = TopicClassifier()
    result = classifier.classify("How do I get from O'Hare Airport to UIUC without a car?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_cheapest_way_from_chicago_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What is the cheapest way to get to campus from Chicago?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_parking_rates_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What are the parking rates on campus?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_airport_shuttle_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("Does UIUC have a shuttle to the airport?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_midway_airport_question_as_transportation() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("What's the fastest way from Midway Airport to campus?")
    assert result.topic is Topic.TRANSPORTATION_PARKING
    assert result.confidence > 0.55


def test_classifies_work_hours_question_as_student_employment() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("How many hours can I work as a student employee?")
    assert result.topic is Topic.CAREER_EMPLOYMENT
    assert result.confidence > 0.55


def test_classifies_buying_textbooks_question_as_campus_services() -> None:
    classifier = TopicClassifier()
    result = classifier.classify("Where do I buy textbooks?")
    assert result.topic is Topic.CAMPUS_SERVICES_FACILITIES
    assert result.confidence > 0.55


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
