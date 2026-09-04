const API_BASE_URL = 'http://localhost:8000';

export interface TraceSpanData {
  id: string;
  task_id: string;
  parent_span_id: string | null;
  span_type: string;
  actor: string;
  subtask_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  latency_ms: number;
  cost_usd: number;
  tokens_in: number | null;
  tokens_out: number | null;
  payload: Record<string, any>;
  children: TraceSpanData[];
}

export interface TaskTraceTree {
  task_id: string;
  request_text: string;
  status: string;
  total_cost_usd: number;
  total_latency_ms: number;
  cost_by_agent: Record<string, number>;
  cost_by_tool: Record<string, number>;
  trace_tree: TraceSpanData[];
}

export interface ReplayRecord {
  id: string;
  original_task_id: string;
  from_checkpoint_id: string;
  input_override: Record<string, any> | null;
  resulting_task_id: string;
  created_at: string;
}

export async function fetchTaskTrace(taskId: string): Promise<TaskTraceTree> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/trace`);
  if (!response.ok) {
    throw new Error(`Failed to fetch trace for task ${taskId}: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerTaskReplay(
  taskId: string,
  checkpointId: string,
  inputOverride?: Record<string, any>
): Promise<{ success: boolean; original_task_id: string; checkpoint_id: string; resulting_task_id: string }> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/replay`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      checkpoint_id: checkpointId,
      input_override: inputOverride || null,
    }),
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to trigger replay');
  }
  return response.json();
}

export async function fetchTaskReplays(taskId: string): Promise<ReplayRecord[]> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/replays`);
  if (!response.ok) {
    throw new Error(`Failed to fetch replays for task ${taskId}`);
  }
  return response.json();
}
