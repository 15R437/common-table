import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schema import SeatingRequest, SeatingResponse
from app import optimiser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/optimize", response_model=SeatingResponse)
def optimize_layout(payload: SeatingRequest):
    # FastAPI automatically validates that 'payload' matches the SeatingRequest schema
    try:
        return optimiser.solve(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))