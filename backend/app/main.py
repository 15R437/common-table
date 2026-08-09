import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from fastapi import FastAPI
from app.schema import SeatingRequest, SeatingResponse

app = FastAPI()

@app.post("/api/v1/optimize", response_model=SeatingResponse)
def optimize_layout(payload: SeatingRequest):
    # FastAPI automatically validates that 'payload' matches the SeatingRequest schema
    return {"assignments": [], "efficiency_score": 0.0}