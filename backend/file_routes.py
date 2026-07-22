import uuid
import time
from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select, delete
from starlette.responses import Response
from db import WriteSession, ReadSession
from models import File
from storage import upload_file, download_file as minio_download, delete_file as minio_delete

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", status_code=201)
async def create_file(upload: UploadFile):
    if not upload.filename:
        raise HTTPException(status_code=400, detail="filename required")

    data = await upload.read()
    file_id = uuid.uuid4()
    minio_key = f"{file_id}-{upload.filename}"

    uploaded = upload_file(minio_key, data, upload.content_type or "application/octet-stream")
    if not uploaded:
        raise HTTPException(status_code=503, detail="storage unavailable")

    record = File(
        id=file_id,
        filename=upload.filename,
        size=len(data),
        content_type=upload.content_type or "application/octet-stream",
        minio_key=minio_key,
    )

    def _save():
        with WriteSession() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return {
            "id": str(record.id),
            "filename": record.filename,
            "size": record.size,
            "content_type": record.content_type,
            "created_at": record.created_at.isoformat(),
        }

    try:
        for attempt in range(3):
            try:
                result = _save()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5)
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")

    return result


@router.get("")
def list_files():
    def _list():
        with ReadSession() as session:
            return session.execute(select(File).order_by(File.created_at.desc())).scalars().all()

    try:
        for attempt in range(2):
            try:
                rows = _list()
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.5)
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")

    return [
        {
            "id": str(r.id),
            "filename": r.filename,
            "size": r.size,
            "content_type": r.content_type,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/{file_id}")
def download_file(file_id: str):
    def _get():
        with ReadSession() as session:
            return session.execute(select(File).where(File.id == file_id)).scalar_one_or_none()

    try:
        for attempt in range(2):
            try:
                record = _get()
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.5)
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")

    if record is None:
        raise HTTPException(status_code=404, detail="file not found")

    data = minio_download(record.minio_key)
    if data is None:
        raise HTTPException(status_code=503, detail="storage unavailable")

    return Response(content=data, media_type=record.content_type,
                    headers={"Content-Disposition": f"attachment; filename={record.filename}"})


@router.delete("/{file_id}")
def delete_file(file_id: str):
    def _get_and_del():
        with WriteSession() as session:
            rec = session.execute(select(File).where(File.id == file_id)).scalar_one_or_none()
            if rec is None:
                raise HTTPException(status_code=404, detail="file not found")
            minio_key = rec.minio_key
            session.execute(delete(File).where(File.id == file_id))
            session.commit()
        return minio_key

    try:
        for attempt in range(3):
            try:
                minio_key = _get_and_del()
                break
            except HTTPException:
                raise
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")

    minio_delete(minio_key)
    return {"detail": "deleted"}
