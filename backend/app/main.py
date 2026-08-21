import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schema import SeatingRequest, SeatingResponse
from app import optimiser

app = FastAPI()

# Comma-separated list of allowed frontend origins, e.g.
# "http://localhost:3000,https://your-app.vercel.app"
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

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
def optimise_layout(request: SeatingRequest):
    try:
        return optimiser.solve(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))