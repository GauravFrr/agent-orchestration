import React from 'react';
import { TraceSpanData } from '../api/traces';

interface SpanDetailDrawerProps {
  span: TraceSpanData | null;
  onClose: () => void;
  onOpenReplayModal?: (span: TraceSpanData) => void;
}

export const SpanDetailDrawer: React.FC<SpanDetailDrawerProps> = ({
  span,
  onClose,
  onOpenReplayModal,
}) => {
  if (!span) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      width: '520px',
      height: '100vh',
      backgroundColor: '#181825',
      borderLeft: '1px solid #45475a',
      boxShadow: '-4px 0 20px rgba(0,0,0,0.5)',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      color: '#cdd6f4',
      fontFamily: 'sans-serif'
    }}>
      {/* Drawer Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid #313244',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#1e1e2e'
      }}>
        <div>
          <div style={{ fontSize: '0.8rem', color: '#a6adc8', textTransform: 'uppercase', fontWeight: 600 }}>Span Payload Details</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f5e0dc', marginTop: '2px' }}>
            {span.actor} <span style={{ color: '#6c7086', fontSize: '0.9rem' }}>({span.span_type})</span>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#a6adc8',
            fontSize: '1.4rem',
            cursor: 'pointer'
          }}
        >
          ✕
        </button>
      </div>

      {/* Drawer Body */}
      <div style={{ flex: 1, padding: '20px', overflowY: 'auto' }}>
        {/* Metric Badges */}
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <div style={{ background: '#313244', padding: '6px 12px', borderRadius: '4px', fontSize: '0.8rem' }}>
            Latency: <strong style={{ color: '#89b4fa' }}>{span.latency_ms}ms</strong>
          </div>
          <div style={{ background: '#313244', padding: '6px 12px', borderRadius: '4px', fontSize: '0.8rem' }}>
            Cost: <strong style={{ color: '#a6e3a1' }}>${span.cost_usd.toFixed(6)}</strong>
          </div>
          {span.tokens_in !== null && (
            <div style={{ background: '#313244', padding: '6px 12px', borderRadius: '4px', fontSize: '0.8rem' }}>
              Tokens: <strong style={{ color: '#f9e2af' }}>{span.tokens_in} in / {span.tokens_out} out</strong>
            </div>
          )}
        </div>

        {/* Replay Trigger Button */}
        {onOpenReplayModal && (
          <button
            onClick={() => onOpenReplayModal(span)}
            style={{
              width: '100%',
              padding: '10px',
              backgroundColor: '#89b4fa',
              color: '#11111b',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
          >
            🔄 Replay Task From This Checkpoint Node
          </button>
        )}

        {/* Payload JSON Inspector */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '0.85rem', color: '#bac2de', fontWeight: 600, marginBottom: '6px' }}>
            Prompt / Response Payload:
          </div>
          <pre style={{
            background: '#11111b',
            padding: '12px',
            borderRadius: '6px',
            border: '1px solid #313244',
            fontSize: '0.8rem',
            color: '#a6e3a1',
            overflowX: 'auto',
            maxHeight: '400px',
            whiteSpace: 'pre-wrap'
          }}>
            {JSON.stringify(span.payload, null, 2)}
          </pre>
        </div>

        {/* Timestamps & Identifiers */}
        <div style={{ borderTop: '1px solid #313244', paddingTop: '16px', fontSize: '0.8rem', color: '#a6adc8' }}>
          <div><strong>Span ID:</strong> {span.id}</div>
          <div><strong>Parent Span ID:</strong> {span.parent_span_id || 'None (Root)'}</div>
          <div><strong>Task ID:</strong> {span.task_id}</div>
          <div><strong>Subtask ID:</strong> {span.subtask_id || 'N/A'}</div>
          <div><strong>Started At:</strong> {span.started_at || 'N/A'}</div>
          <div><strong>Ended At:</strong> {span.ended_at || 'N/A'}</div>
        </div>
      </div>
    </div>
  );
};
