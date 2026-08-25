import type {
  ActionType,
  AuditVerifyResponse,
  BatchStatus,
  CounterfactualResponse,
  CustomerTimelineResponse,
  DecisionRow,
  EventRow,
  EvalComparisonResponse,
  FairnessReport,
  MetricsResponse,
} from "./types";

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

export function startBatch(n: number, seed?: number) {
  return apiFetch<{ batch_id: string; n: number }>("/api/run-batch", {
    method: "POST",
    body: JSON.stringify({ n, seed }),
  });
}

export function getBatchStatus(batchId: string) {
  return apiFetch<BatchStatus>(`/api/batches/${batchId}/status`);
}

export function pauseBatch(batchId: string) {
  return apiFetch<BatchStatus>(`/api/batches/${batchId}/pause`, { method: "POST" });
}

export function resumeBatch(batchId: string) {
  return apiFetch<BatchStatus>(`/api/batches/${batchId}/resume`, { method: "POST" });
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

export function getAuditVerify() {
  return apiFetch<AuditVerifyResponse>("/api/audit/verify");
}

export function getEvalComparison(cases = 300, seed = 42) {
  return apiFetch<EvalComparisonResponse>(`/api/eval/comparison?cases=${cases}&seed=${seed}`);
}

export function getCustomerTimeline(customerId: string) {
  return apiFetch<CustomerTimelineResponse>(
    `/api/customers/${encodeURIComponent(customerId)}/timeline`
  );
}

export function runCounterfactual(eventId: string, action: ActionType) {
  return apiFetch<CounterfactualResponse>(
    `/api/events/${encodeURIComponent(eventId)}/counterfactual`,
    { method: "POST", body: JSON.stringify({ action }) }
  );
}

export function getFairnessReport() {
  return apiFetch<FairnessReport>("/api/eval/fairness");
}
