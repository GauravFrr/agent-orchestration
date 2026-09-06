import React, { useState } from 'react';
import { submitTask, getTask, Task } from '../api/tasks';

interface HomeProps {
  navigate: (path: string) => void;
}

export const Home: React.FC<HomeProps> = ({ navigate }) => {
  const [requestText, setRequestText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [searchId, setSearchId] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!requestText.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const task = await submitTask(requestText.trim());
      setActiveTask(task);
      setRequestText('');
    } catch (err: any) {
      setError(err.message || 'Error submitting task');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchId.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const task = await getTask(searchId.trim());
      setActiveTask(task);
    } catch (err: any) {
      setError(err.message || 'Task not found');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto', color: '#cdd6f4' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#89b4fa', marginBottom: '8px' }}>
          Task Operations & Dispatch
        </h1>
        <p style={{ color: '#a6adc8', fontSize: '14px' }}>
          Submit natural language prompts to trigger the multi-agent orchestrator, or lookup existing task execution state.
        </p>
      </div>

      {error && (
        <div style={{
          backgroundColor: 'rgba(243, 139, 168, 0.15)',
          border: '1px solid #f38ba8',
          color: '#f38ba8',
          padding: '12px 16px',
          borderRadius: '6px',
          marginBottom: '24px',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
        {/* Submit Task Card */}
        <div style={{
          backgroundColor: '#181825',
          border: '1px solid #313244',
          borderRadius: '8px',
          padding: '24px'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: '#89b4fa', marginBottom: '16px' }}>
            Submit New Task
          </h2>
          <form onSubmit={handleSubmit}>
            <textarea
              rows={4}
              value={requestText}
              onChange={(e) => setRequestText(e.target.value)}
              placeholder="e.g. Research market trends in agent orchestration and write a brief summary report."
              style={{
                width: '100%',
                backgroundColor: '#11111b',
                border: '1px solid #45475a',
                borderRadius: '6px',
                color: '#cdd6f4',
                padding: '12px',
                fontSize: '14px',
                marginBottom: '16px',
                resize: 'vertical',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
            <button
              type="submit"
              disabled={loading || !requestText.trim()}
              style={{
                backgroundColor: loading || !requestText.trim() ? '#45475a' : '#89b4fa',
                color: '#11111b',
                fontWeight: 'bold',
                border: 'none',
                borderRadius: '6px',
                padding: '10px 20px',
                cursor: loading || !requestText.trim() ? 'not-allowed' : 'pointer',
                fontSize: '14px'
              }}
            >
              {loading ? 'Submitting...' : '🚀 Submit Task'}
            </button>
          </form>
        </div>

        {/* Task Lookup Card */}
        <div style={{
          backgroundColor: '#181825',
          border: '1px solid #313244',
          borderRadius: '8px',
          padding: '24px'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: '#89b4fa', marginBottom: '16px' }}>
            Lookup Existing Task
          </h2>
          <form onSubmit={handleSearch}>
            <input
              type="text"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              placeholder="Enter Task UUID..."
              style={{
                width: '100%',
                backgroundColor: '#11111b',
                border: '1px solid #45475a',
                borderRadius: '6px',
                color: '#cdd6f4',
                padding: '12px',
                fontSize: '14px',
                marginBottom: '16px',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
            <button
              type="submit"
              disabled={loading || !searchId.trim()}
              style={{
                backgroundColor: loading || !searchId.trim() ? '#45475a' : '#cba6f7',
                color: '#11111b',
                fontWeight: 'bold',
                border: 'none',
                borderRadius: '6px',
                padding: '10px 20px',
                cursor: loading || !searchId.trim() ? 'not-allowed' : 'pointer',
                fontSize: '14px'
              }}
            >
              {loading ? 'Searching...' : '🔍 Fetch Task Status'}
            </button>
          </form>
        </div>
      </div>

      {/* Active / Submitted Task Details */}
      {activeTask && (
        <div style={{
          backgroundColor: '#181825',
          border: '1px solid #313244',
          borderRadius: '8px',
          padding: '24px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: '#a6e3a1' }}>
              Task Record Details
            </h3>
            <button
              onClick={() => navigate('/traces')}
              style={{
                backgroundColor: '#313244',
                color: '#cba6f7',
                border: '1px solid #45475a',
                borderRadius: '6px',
                padding: '6px 14px',
                fontSize: '13px',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              View in Trace Explorer →
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '20px' }}>
            <div style={{ backgroundColor: '#11111b', padding: '12px', borderRadius: '6px', border: '1px solid #313244' }}>
              <div style={{ fontSize: '12px', color: '#a6adc8' }}>TASK ID</div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#89b4fa', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeTask.id}
              </div>
            </div>
            <div style={{ backgroundColor: '#11111b', padding: '12px', borderRadius: '6px', border: '1px solid #313244' }}>
              <div style={{ fontSize: '12px', color: '#a6adc8' }}>STATUS</div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#fab387' }}>
                {activeTask.status.toUpperCase()}
              </div>
            </div>
            <div style={{ backgroundColor: '#11111b', padding: '12px', borderRadius: '6px', border: '1px solid #313244' }}>
              <div style={{ fontSize: '12px', color: '#a6adc8' }}>CONFIDENCE</div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#a6e3a1' }}>
                {(activeTask.confidence * 100).toFixed(0)}%
              </div>
            </div>
            <div style={{ backgroundColor: '#11111b', padding: '12px', borderRadius: '6px', border: '1px solid #313244' }}>
              <div style={{ fontSize: '12px', color: '#a6adc8' }}>TOTAL COST</div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#f9e2af' }}>
                ${activeTask.total_cost_usd.toFixed(4)}
              </div>
            </div>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '13px', color: '#a6adc8', marginBottom: '4px' }}>Original Request:</div>
            <div style={{ backgroundColor: '#11111b', padding: '12px', borderRadius: '6px', border: '1px solid #313244', fontSize: '14px' }}>
              {activeTask.request_text}
            </div>
          </div>

          {activeTask.plan && (
            <div>
              <div style={{ fontSize: '13px', color: '#a6adc8', marginBottom: '4px' }}>Generated Plan:</div>
              <pre style={{
                backgroundColor: '#11111b',
                padding: '12px',
                borderRadius: '6px',
                border: '1px solid #313244',
                fontSize: '12px',
                overflowX: 'auto',
                color: '#89dceb'
              }}>
                {JSON.stringify(activeTask.plan, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
