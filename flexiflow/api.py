from __future__ import annotations

from typing import Any, Dict

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # optional dependency
    FastAPI = None
    HTTPException = Exception


def create_app(engine: Any):
    if FastAPI is None:
        raise RuntimeError("fastapi is not installed. Install with: pip install -e '.[api]'")

    app = FastAPI()

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/components/{name}/message")
    async def send_message(name: str, message: Dict[str, Any]):
        component = engine.get(name)
        if component is None:
            raise HTTPException(status_code=404, detail="Component not found")
        await component.handle_message(message)
        return {"status": "sent"}

    return app
