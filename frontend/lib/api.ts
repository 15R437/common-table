import { SeatingRequest, SeatingResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

export async function optimiseSeating(
  request: SeatingRequest
): Promise<SeatingResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/optimise`, {
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
