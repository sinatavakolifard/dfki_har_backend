from fastapi import FastAPI

from app.routes import sessions, users

app = FastAPI(
    title="HAR Backend",
    description="Backend for the DFKI Human Activity Recognition Flutter app.",
    version="0.1.0",
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(users.router)
app.include_router(sessions.router)
