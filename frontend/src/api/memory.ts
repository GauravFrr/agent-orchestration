const API_BASE_URL = 'http://localhost:8000';

export interface MemoryRecord {
  id: string;
  source_task_id: string;
  memory_type: 'plan' | 'fact' | 'preference' | string;
  summary: string;
  importance_score: number;
  retrieval_count: number;
  last_retrieved_at: string | null;
  created_at: string;
}

export async function fetchMemories(): Promise<MemoryRecord[]> {
  const response = await fetch(`${API_BASE_URL}/memory`);
  if (!response.ok) {
    throw new Error(`Failed to fetch memories: ${response.statusText}`);
  }
  return response.json();
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/memory/${memoryId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete memory ${memoryId}`);
  }
}
