export interface ReviewRequest {
  id: string;
  task_id: string;
  subtask_id?: string;
  trigger_reason: string;
  approval_level: string;
  context_snapshot: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected' | 'modified' | 'taken_over';
  decision_payload?: Record<string, any>;
  created_at: string;
  decided_at?: string;
}

export interface DecisionPayload {
  decision: 'approve' | 'modify' | 'reject' | 'take_over';
  feedback?: string;
  modified_input?: Record<string, any>;
  taken_over_output?: Record<string, any>;
}

const API_BASE = 'http://localhost:8000';

export async function fetchReviews(status?: string): Promise<ReviewRequest[]> {
  const url = new URL(`${API_BASE}/reviews`);
  if (status) {
    url.searchParams.append('status', status);
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`Failed to fetch reviews: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchReviewById(id: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/reviews/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch review ${id}: ${res.statusText}`);
  }
  return res.json();
}

export async function submitDecision(id: string, payload: DecisionPayload): Promise<any> {
  const res = await fetch(`${API_BASE}/reviews/${id}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errData.detail || 'Failed to submit decision');
  }
  return res.json();
}

export async function sendChatWithAgent(id: string, message: string): Promise<{ response: string }> {
  const res = await fetch(`${API_BASE}/reviews/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.statusText}`);
  }
  return res.json();
}
