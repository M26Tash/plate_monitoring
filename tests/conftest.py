import pytest

from app.storage import Sighting, Storage


@pytest.fixture
def storage(tmp_path):
    s = Storage.open(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def make_sighting(storage):
    source = storage.sources.add("cam-test", "file", "video.mp4", fps=30)
    run = storage.runs.start(source.id)
    counter = iter(range(1, 10_000))

    def make(plate=None, final_plate=None, status="confirmed", review=None, path=()):
        s = Sighting(None, run.id, source.id, next(counter), status, plate, final_plate, review,
                     0, 30, "2026-11-20T10:00:00", "2026-11-20T10:00:01")
        return storage.sightings.add(s, path=path)

    return make
