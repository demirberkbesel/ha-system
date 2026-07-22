import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base
from models import Item


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    session.begin()
    yield session
    session.rollback()
    session.close()


class TestItemModel:
    def test_item_creation(self, db_session):
        item = Item(name="test-item")
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.id is not None
        assert isinstance(item.id, uuid.UUID)
        assert item.name == "test-item"
        assert isinstance(item.created_at, datetime)

    def test_item_query(self, db_session):
        item = Item(name="query-test")
        db_session.add(item)
        db_session.commit()

        found = db_session.query(Item).filter_by(name="query-test").first()
        assert found is not None
        assert found.name == "query-test"

    def test_item_delete(self, db_session):
        item = Item(name="delete-test")
        db_session.add(item)
        db_session.commit()

        db_session.delete(item)
        db_session.commit()

        found = db_session.query(Item).filter_by(name="delete-test").first()
        assert found is None


class TestCache:
    def test_cache_get_miss_without_redis(self):
        from cache import cache_get
        result = cache_get("nonexistent-key")
        assert result is None

    def test_cache_set_get_roundtrip(self):
        from cache import cache_get, cache_set, cache_delete

        cache_set("test-key", {"value": 42}, ttl=10)
        result = cache_get("test-key")
        assert result == {"value": 42}

        cache_delete("test-key")
        result = cache_get("test-key")
        assert result is None


class TestRoutes:
    def test_create_item(self):
        from routes import create_item

        with patch("routes.WriteSession") as mock_session_cls, \
             patch("routes.invalidate_items_cache") as mock_invalidate:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session
            mock_session.refresh = lambda obj: setattr(obj, "created_at",
                datetime(2025, 1, 1, tzinfo=timezone.utc))

            result = create_item({"name": "test"})
            assert result["name"] == "test"

    def test_create_item_missing_name(self):
        from routes import create_item
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            create_item({})
        assert exc.value.status_code == 400

    def test_get_item_not_found(self):
        from routes import get_item
        from fastapi import HTTPException

        with patch("routes.ReadSession") as mock_session_cls, \
             patch("routes.cache_get", return_value=None):
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            with pytest.raises(HTTPException) as exc:
                get_item(str(uuid.uuid4()))
            assert exc.value.status_code == 404
