const API_BASE_URL = 'http://localhost:8000';

export interface Task {
  id: string;
  request_text: string;
  status: string;
  confidence: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  total_cost_usd: number;
  plan: any;
}

export async function submitTask(request_text: string): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_text }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || 'Failed to submit task');
  }
  return response.json();
}

export async function getTask(taskId: string): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch task ${taskId}`);
  }
  return response.json();
}
