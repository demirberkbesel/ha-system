import time
import uuid
import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.exc import OperationalError
from db import WriteSession, ReadSession
from models import Item
from cache import cache_get, cache_set, cache_delete, invalidate_items_cache

logger = logging.getLogger("routes")
router = APIRouter(prefix="/items", tags=["items"])


def retry_on_db_error(fn, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return fn()
        except OperationalError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise


@router.post("", status_code=201)
def create_item(payload: dict):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    item = Item(name=name)

    def _create():
        with WriteSession() as session:
            session.add(item)
            session.commit()
            session.refresh(item)

    try:
        retry_on_db_error(_create)
    except OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")

    invalidate_items_cache()
    return {"id": str(item.id), "name": item.name, "created_at": item.created_at.isoformat()}


@router.get("")
def list_items():
    cached = cache_get("items:all")
    if cached is not None:
        return cached

    def _list():
        with ReadSession() as session:
            items = session.execute(select(Item).order_by(Item.created_at.desc())).scalars().all()
        return items

    try:
        items = retry_on_db_error(_list)
    except OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")

    result = [{"id": str(i.id), "name": i.name, "created_at": i.created_at.isoformat()} for i in items]
    cache_set("items:all", result)
    return result


@router.get("/{item_id}")
def get_item(item_id: str):
    cached = cache_get(f"item:{item_id}")
    if cached is not None:
        return cached

    def _get():
        with ReadSession() as session:
            item = session.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()
        return item

    try:
        item = retry_on_db_error(_get)
    except OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")

    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    result = {"id": str(item.id), "name": item.name, "created_at": item.created_at.isoformat()}
    cache_set(f"item:{item_id}", result)
    return result


@router.delete("/{item_id}")
def delete_item(item_id: str):
    def _delete():
        with WriteSession() as session:
            result = session.execute(delete(Item).where(Item.id == item_id))
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="item not found")
            session.commit()

    try:
        retry_on_db_error(_delete)
    except OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")

    cache_delete(f"item:{item_id}")
    invalidate_items_cache()
    return {"detail": "deleted"}
