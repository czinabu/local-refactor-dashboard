from refactor_dashboard.history import HistoryStore


def _add(store, **overrides):
    fields = dict(
        source="web",
        language="python",
        instruction="tidy",
        original_code="x=1",
        refactored_code="x = 1",
        summary="- Added spaces.",
    )
    fields.update(overrides)
    return store.add(**fields)


def test_add_get_list_delete(tmp_path):
    store = HistoryStore(tmp_path / "nested" / "history.db")
    first = _add(store, filename="a.py")
    second = _add(store, instruction="add types")

    rows = store.list()
    assert [r["id"] for r in rows] == [second, first]  # newest first
    assert "original_code" not in rows[0]

    entry = store.get(first)
    assert entry.filename == "a.py"
    assert entry.refactored_code == "x = 1"
    assert entry.summary == "- Added spaces."

    assert store.delete(first) is True
    assert store.delete(first) is False
    assert store.get(first) is None
    assert store.clear() == 1
    assert store.list() == []


def test_list_paging(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    ids = [_add(store) for _ in range(5)]
    assert [r["id"] for r in store.list(limit=2, offset=1)] == [ids[3], ids[2]]
