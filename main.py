
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_ORIGIN = "https://dash-cpu0ve.example.com"
EMAIL = os.environ.get("EMAIL", "").strip()

app = FastAPI(title="Descriptive Statistics API")


class RequestMetricsMiddleware:
    """Attach request ID and elapsed processing time to every response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        async def send_with_metrics(message):
            if message["type"] == "http.response.start":
                elapsed = max(0.0, time.perf_counter() - started)
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-request-id", request_id.encode("ascii")),
                    (b"x-process-time", f"{elapsed:.9f}".encode("ascii")),
                ])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_metrics)


# Add CORS inside the metrics middleware so even CORS preflight
# responses receive the required metrics headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
    max_age=600,
)
app.add_middleware(RequestMetricsMiddleware)


@app.get("/stats")
async def stats(
    values: str = Query(..., description="Comma-separated integers")
):
    if not EMAIL:
        raise HTTPException(status_code=500, detail="EMAIL is not configured")

    try:
        numbers = [int(item.strip()) for item in values.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="values must contain comma-separated integers",
        )

    if not numbers or any(not item.strip() for item in values.split(",")):
        raise HTTPException(
            status_code=400, detail="At least one integer is required"
        )

    total = sum(numbers)
    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": total,
        "min": min(numbers),
        "max": max(numbers),
        "mean": total / len(numbers),
    }


@app.get("/")
async def health():
    return {"status": "ok"}
