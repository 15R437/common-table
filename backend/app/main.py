import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

from app.schema import SeatingRequest, SeatingResponse, EvaluateRequest, FeedbackRequest
from app import optimiser

app = FastAPI()

logger = logging.getLogger("commontable")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
    )

# Comma-separated list of allowed frontend origins, e.g.
# "http://localhost:3000,https://your-app.vercel.app"
# Whitespace around each entry is stripped -- CORS matches the Origin header
# exactly, so "a.com, b.com" (space after the comma) would otherwise silently
# turn " b.com" into an origin that can never match anything a browser sends.
allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/api/v1/optimise", response_model=SeatingResponse)
@limiter.limit("10/minute")
def optimise_layout(request: Request, payload: SeatingRequest):
    try:
        return optimiser.solve(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/optimise/shuffle", response_model=SeatingResponse)
@limiter.limit("10/minute")
def shuffle_layout(request: Request, payload: SeatingRequest):
    try:
        return optimiser.solve(payload, shuffle=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Scoring an arrangement runs no search, so it is far cheaper than /optimise and
# is called once per hand-edit -- a tighter limit here would break dragging
# guests around, which is the whole point of the endpoint.
@app.post("/api/v1/evaluate", response_model=SeatingResponse)
@limiter.limit("120/minute")
def evaluate_layout(request: Request, payload: EvaluateRequest):
    try:
        return optimiser.evaluate(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/feedback")
@limiter.limit("5/minute")
def submit_feedback(request: Request, payload: FeedbackRequest):
    # Written to the application log rather than a database: there is no store
    # to put it in yet, and losing the ability to collect any feedback at all
    # while one is chosen is the worse trade. Swap this line for a write to a
    # table or a form service when somewhere durable exists.
    logger.warning(
        "FEEDBACK verdict=%s guests=%s tables=%s constraints=%s message=%r",
        payload.verdict,
        payload.guest_count,
        payload.table_count,
        payload.constraint_count,
        (payload.message or "").strip(),
    )
    return {"status": "received"}