from app.storage import Storage
from app.storage.database import SCHEMA_VERSION


def test_new_database_gets_schema_version(storage):
    assert storage.db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_reopen_keeps_data(tmp_path):
    s = Storage.open(tmp_path / "a.db")
    s.sources.add("cam", "file", "v.mp4")
    s.close()
    s = Storage.open(tmp_path / "a.db")
    assert [x.name for x in s.sources.all()] == ["cam"]
    s.close()


def test_sighting_is_normalized_and_keeps_its_path(storage, make_sighting):
    s = make_sighting(plate="34 abc 123", final_plate="34abc123", path=[(0, 10, 20), (1, 12, 22)])
    loaded = storage.sightings.get(s.id)
    assert loaded.plate == "34ABC123"
    assert loaded.final_plate == "34ABC123"
    assert storage.sightings.path(s.id) == [(0, 10, 20), (1, 12, 22)]


def test_search_by_plate_and_status(storage, make_sighting):
    make_sighting(plate="34ABC123", final_plate="34ABC123")
    make_sighting(plate="06XYZ99", status="review_unsure", review="pending")
    assert [s.plate for s in storage.sightings.search(plate="abc")] == ["34ABC123"]
    assert [s.plate for s in storage.sightings.search(status="review_unsure")] == ["06XYZ99"]
    assert storage.sightings.pending_reviews() == 1


def test_review_decision_updates_sighting(storage, make_sighting):
    s = make_sighting(plate="34ABC128", status="review_unsure", review="pending")
    storage.reviews.decide(s.id, "corrected", "34ABC123", "tester")
    loaded = storage.sightings.get(s.id)
    assert loaded.final_plate == "34ABC123"
    assert loaded.review == "done"
    assert storage.sightings.pending_reviews() == 0


def test_rejected_review_clears_final_plate(storage, make_sighting):
    s = make_sighting(plate="34ABC128", status="review_unsure", review="pending")
    storage.reviews.decide(s.id, "rejected", None, "tester")
    assert storage.sightings.get(s.id).final_plate is None


def test_wanted_active_filter(storage):
    a = storage.wanted.add("34ABC123", "stolen", "high")
    storage.wanted.add("06XYZ99")
    a.active = False
    storage.wanted.update(a)
    assert [w.plate for w in storage.wanted.all(active_only=True)] == ["06XYZ99"]
    assert len(storage.wanted.all()) == 2
