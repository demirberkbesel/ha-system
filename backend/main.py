from fastapi import FastAPI
from db import init_db
from routes import router

app = FastAPI(title="HA System Backend")

app.include_router(router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
