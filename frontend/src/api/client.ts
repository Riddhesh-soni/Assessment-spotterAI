// Minimal typed fetch wrapper. Centralises base URL + error normalisation so
// feature code never touches fetch directly.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function postJson<TResponse, TBody = unknown>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Could not reach the server. Is the backend running?", 0);
  }

  const payload = await resp.json().catch(() => null);

  if (!resp.ok) {
    // Backend shapes errors as { error: { code, detail } } or DRF field errors.
    const detail =
      payload?.error?.detail ??
      payload?.detail ??
      firstFieldError(payload) ??
      `Request failed (${resp.status})`;
    throw new ApiError(detail, resp.status, payload?.error?.code);
  }
  return payload as TResponse;
}

function firstFieldError(payload: unknown): string | null {
  if (payload && typeof payload === "object") {
    for (const value of Object.values(payload)) {
      if (Array.isArray(value) && value.length) return String(value[0]);
    }
  }
  return null;
}
