import type { DecisionRow, EventRow, MetricsResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${path} failed (${response.status}): ${text}`);
  }
  return response.json();
}

export function runBatch(n: number, seed?: number) {
  return apiFetch<{ decisions_written: number; decisions: DecisionRow[] }>(
    "/api/run-batch",
    {
      method: "POST",
      body: JSON.stringify({ n, seed }),
    }
  );
}

export function getEvents(limit = 100) {
  return apiFetch<EventRow[]>(`/api/events?limit=${limit}`);
}

export function getDecisions(limit = 100) {
  return apiFetch<DecisionRow[]>(`/api/decisions?limit=${limit}`);
}

export function getMetrics() {
  return apiFetch<MetricsResponse>("/api/metrics");
}
