import { SeatingRequest, SeatingResponse } from "./types";

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
