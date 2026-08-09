from .schema import SeatingRequest, SeatingResponse, TableAssignment

def solve(request: SeatingRequest) -> SeatingResponse:
    assignments = None
    score = 0.0

    return SeatingResponse(assignments=assignments, score=score)