import api.database as database


class DummySession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_get_db_yields_and_closes_session(monkeypatch):
    session = DummySession()

    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    dependency = database.get_db()
    yielded = next(dependency)

    assert yielded is session

    try:
        next(dependency)
    except StopIteration:
        pass

    assert session.closed is True
