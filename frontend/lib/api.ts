import { EvaluateRequest, FeedbackRequest, SeatingRequest, SeatingResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

async function postSeatingRequest(
  path: string,
  request: SeatingRequest
): Promise<SeatingResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Request failed (${response.status})`);
  }

  return response.json();
}

export function optimiseSeating(request: SeatingRequest): Promise<SeatingResponse> {
  return postSeatingRequest("/api/v1/optimise", request);
}

// Re-runs the optimiser on the same request, on the assumption a different
// arrangement is worth seeing -- a normal restart already gives a fresh
// result on the local-search path, but the gradsolver+ls path (cabaret,
// large guest counts) is otherwise fully deterministic, so it needs the
// server's separate shuffle endpoint to produce anything different at all.
export function shuffleSeating(request: SeatingRequest): Promise<SeatingResponse> {
  return postSeatingRequest("/api/v1/optimise/shuffle", request);
}

/**
 * Re-scores an arrangement the user edited by hand, leaving the seating exactly
 * as they left it. The constraint counts can't be recomputed in the browser --
 * must_sit_together depends on each table type's seat adjacency, which lives in
 * the backend -- so the edited plan is scored by the same code that produced it.
 */
export function evaluateSeating(request: EvaluateRequest): Promise<SeatingResponse> {
  return postSeatingRequest("/api/v1/evaluate", request as SeatingRequest);
}

/** Fire-and-forget: a failed send must never block or interrupt the user. */
export async function sendFeedback(feedback: FeedbackRequest): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback),
    });
    return response.ok;
  } catch {
    return false;
  }
}
