from app.aggregation.voting import PlateVoter
from app.core.models import PlateRead, PlateStatus


def read(text, confidence=0.95):
    return PlateRead(raw=text, text=text, confidence=confidence)


def foreign(raw, confidence=0.95):
    return PlateRead(raw=raw, text=None, confidence=confidence)


def test_three_agreeing_reads_confirm():
    voter = PlateVoter()
    for _ in range(3):
        voter.add(1, read("34ABC123"), plate_width=200)
    vote = voter.final(1)
    assert vote.status == PlateStatus.CONFIRMED
    assert vote.text == "34ABC123"
    assert vote.reads == 3


def test_too_few_reads_need_review():
    voter = PlateVoter()
    voter.add(1, read("34ABC123"), plate_width=200)
    voter.add(1, read("34ABC123"), plate_width=200)
    vote = voter.final(1)
    assert vote.status == PlateStatus.REVIEW_UNSURE
    assert vote.text == "34ABC123"


def test_voting_fixes_a_single_wrong_character():
    voter = PlateVoter()
    for text in ("34ABC123", "34ABC123", "34ABC128", "34ABC123"):
        voter.add(1, read(text), plate_width=200)
    assert voter.final(1).text == "34ABC123"


def test_small_plates_count_less():
    voter = PlateVoter()
    for _ in range(3):
        voter.add(1, read("34ABC123"), plate_width=40)
    assert voter.final(1).status != PlateStatus.CONFIRMED


def test_two_confirmed_plates_on_one_track_is_a_conflict():
    voter = PlateVoter()
    for _ in range(3):
        voter.add(1, read("34ABC123"), plate_width=200)
    for _ in range(4):
        voter.add(1, read("34ABD123"), plate_width=200)
    vote = voter.final(1)
    assert vote.status == PlateStatus.REVIEW_CONFLICT
    assert set(vote.alternatives) == {"34ABC123", "34ABD123"}


def test_confident_non_turkish_plate_is_foreign():
    voter = PlateVoter()
    for _ in range(3):
        voter.add(1, foreign("B AB 1234"), plate_width=200)
    vote = voter.final(1)
    assert vote.status == PlateStatus.REVIEW_FOREIGN
    assert vote.text == "BAB1234"


def test_tracks_are_independent():
    voter = PlateVoter()
    for _ in range(3):
        voter.add(1, read("34ABC123"), plate_width=200)
        voter.add(2, read("06XYZ99"), plate_width=200)
    assert voter.final(1).text == "34ABC123"
    assert voter.final(2).text == "06XYZ99"
