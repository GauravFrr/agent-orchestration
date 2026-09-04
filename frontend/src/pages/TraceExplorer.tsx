import React, { useEffect, useState } from 'react';
import { fetchTaskTrace, TaskTraceTree, TraceSpanData, fetchTaskReplays, ReplayRecord } from '../api/traces';
import { CostPerfStrip } from '../components/CostPerfStrip';
import { TraceTree } from '../components/TraceTree';
import { SpanDetailDrawer } from '../components/SpanDetailDrawer';
import { ReplayModal } from '../components/ReplayModal';

export const TraceExplorer: React.FC = () => {
  const [taskIdInput, setTaskIdInput] = useState<string>('1785a44a-e614-48a0-859f-0687fae5fdea');
  const [activeTaskId, setActiveTaskId] = useState<string>('1785a44a-e614-48a0-859f-0687fae5fdea');
  const [traceData, setTraceData] = useState<TaskTraceTree | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<TraceSpanData | null>(null);
  const [replayModalSpan, setReplayModalSpan] = useState<TraceSpanData | null>(null);
  const [replays, setReplays] = useState<ReplayRecord[]>([]);
  const [comparedReplayTaskId, setComparedReplayTaskId] = useState<string | null>(null);
  const [replayTraceData, setReplayTraceData] = useState<TaskTraceTree | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrace = async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTaskTrace(id);
      setTraceData(data);
      setActiveTaskId(id);
      
      const repList = await fetchTaskReplays(id);
      setReplays(repList);
    } catch (err: any) {
      setError(err.message || 'Failed to load task trace.');
    } finally {
      setLoading(false);
    }
  };

  const loadReplayComparison = async (replayId: string) => {
    try {
      const data = await fetchTaskTrace(replayId);
      setReplayTraceData(data);
      setComparedReplayTaskId(replayId);
    } catch (err: any) {
      console.error("Failed to load replay comparison trace:", err);
    }
  };

  useEffect(() => {
    loadTrace(activeTaskId);
  }, []);

  return (
    <div style={{ padding: '24px', backgroundColor: '#11111b', minHeight: '100vh', color: '#cdd6f4', fontFamily: 'sans-serif' }}>
      {/* Header & Task ID Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#cba6f7', display: 'flex', alignItems: 'center', gap: '10px' }}>
            🔍 Trace Explorer & Replay System
          </h2>
          <p style={{ margin: '4px 0 0 0', color: '#a6adc8', fontSize: '0.85rem' }}>
            Inspect full OpenTelemetry execution trees, payloads, latency, and compare replay divergence.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={taskIdInput}
            onChange={(e) => setTaskIdInput(e.target.value)}
            placeholder="Enter Task UUID..."
            style={{
              padding: '8px 12px',
              backgroundColor: '#181825',
              border: '1px solid #313244',
              borderRadius: '6px',
              color: '#cdd6f4',
              width: '320px',
              fontFamily: 'monospace',
              fontSize: '0.85rem'
            }}
          />
          <button
            onClick={() => loadTrace(taskIdInput)}
            style={{
              padding: '8px 16px',
              backgroundColor: '#89b4fa',
              color: '#11111b',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            Load Trace
          </button>
        </div>
      </div>

      {loading && <div style={{ color: '#89b4fa', padding: '20px' }}>Loading execution trace...</div>}
      {error && <div style={{ color: '#f38ba8', padding: '16px', background: '#313244', borderRadius: '6px' }}>{error}</div>}

      {traceData && (
        <>
          {/* Top Metric Strip */}
          <CostPerfStrip
            totalCostUsd={traceData.total_cost_usd}
            totalLatencyMs={traceData.total_latency_ms}
            costByAgent={traceData.cost_by_agent}
            costByTool={traceData.cost_by_tool}
          />

          {/* Linked Replay Bar */}
          {replays.length > 0 && (
            <div style={{
              background: '#181825',
              border: '1px solid #313244',
              borderRadius: '8px',
              padding: '12px 16px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ fontSize: '0.85rem', color: '#fab387', fontWeight: 600 }}>
                🔗 Linked Replay Runs ({replays.length}):
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                {replays.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => loadReplayComparison(r.resulting_task_id)}
                    style={{
                      padding: '4px 10px',
                      backgroundColor: comparedReplayTaskId === r.resulting_task_id ? '#89b4fa' : '#313244',
                      color: comparedReplayTaskId === r.resulting_task_id ? '#11111b' : '#cdd6f4',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    Replay {r.resulting_task_id.slice(0, 8)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Main Tree Surface: Side-by-side if replay compared */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: replayTraceData ? '1fr 1fr' : '1fr',
            gap: '20px'
          }}>
            {/* Primary Original Trace Tree */}
            <div style={{ background: '#181825', padding: '16px', borderRadius: '8px', border: '1px solid #313244' }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#89b4fa' }}>
                Original Task Trace ({traceData.task_id.slice(0, 8)})
              </h4>
              <TraceTree
                spans={traceData.trace_tree}
                onSelectSpan={(span) => setSelectedSpan(span)}
                selectedSpanId={selectedSpan?.id}
              />
            </div>

            {/* Replay Comparison Trace Tree */}
            {replayTraceData && (
              <div style={{ background: '#181825', padding: '16px', borderRadius: '8px', border: '1px solid #fab387' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ margin: 0, color: '#fab387' }}>
                    Replay Run Trace ({replayTraceData.task_id.slice(0, 8)})
                  </h4>
                  <button
                    onClick={() => { setReplayTraceData(null); setComparedReplayTaskId(null); }}
                    style={{ background: 'none', border: 'none', color: '#a6adc8', cursor: 'pointer' }}
                  >
                    Close Comparison ✕
                  </button>
                </div>
                <TraceTree
                  spans={replayTraceData.trace_tree}
                  onSelectSpan={(span) => setSelectedSpan(span)}
                  selectedSpanId={selectedSpan?.id}
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* Slide-over Span Detail Drawer */}
      {selectedSpan && (
        <SpanDetailDrawer
          span={selectedSpan}
          onClose={() => setSelectedSpan(null)}
          onOpenReplayModal={(span) => setReplayModalSpan(span)}
        />
      )}

      {/* Replay Modal */}
      {replayModalSpan && (
        <ReplayModal
          span={replayModalSpan}
          onClose={() => setReplayModalSpan(null)}
          onReplaySuccess={(replayTaskId) => {
            loadTrace(activeTaskId);
            loadReplayComparison(replayTaskId);
          }}
        />
      )}
    </div>
  );
};
