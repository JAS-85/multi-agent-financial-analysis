import json
import time
from pathlib import Path

import pytest

from utils.cache import get_cached, set_cached, _CACHE_DIR


@pytest.fixture(autouse=True)
def clean_cache(tmp_path, monkeypatch):
    """Redirect cache directory to a temp folder for each test."""
    import utils.cache as cache_module
    monkeypatch.setattr(cache_module, "_CACHE_DIR", tmp_path / ".cache")
    yield


class TestCache:
    def test_set_and_get(self):
        set_cached("test_source", "some data text")
        result = get_cached("test_source", max_age_hours=1.0)
        assert result == "some data text"

    def test_get_missing_returns_none(self):
        result = get_cached("nonexistent", max_age_hours=1.0)
        assert result is None

    def test_expired_cache_returns_none(self, tmp_path, monkeypatch):
        import utils.cache as cache_module
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        # Write a cache entry that is 25 hours old
        path = cache_dir / "old_source.json"
        path.write_text(
            json.dumps({"cached_at": time.time() - 25 * 3600, "text": "stale data"}),
            encoding="utf-8",
        )

        result = get_cached("old_source", max_age_hours=24.0)
        assert result is None

    def test_empty_text_not_cached(self):
        set_cached("empty_source", "")
        result = get_cached("empty_source", max_age_hours=1.0)
        assert result is None
