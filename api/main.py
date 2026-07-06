from fastapi import FastAPI

app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution.",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}