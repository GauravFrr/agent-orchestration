import React, { useState } from 'react';
import { TraceSpanData } from '../api/traces';

interface TraceTreeProps {
  spans: TraceSpanData[];
  onSelectSpan: (span: TraceSpanData) => void;
  selectedSpanId?: string | null;
}

const SpanNodeItem: React.FC<{
  span: TraceSpanData;
  onSelectSpan: (span: TraceSpanData) => void;
  selectedSpanId?: string | null;
  depth?: number;
}> = ({ span, onSelectSpan, selectedSpanId, depth = 0 }) => {
  const [expanded, setExpanded] = useState<boolean>(true);

  const hasChildren = span.children && span.children.length > 0;
  const isSelected = selectedSpanId === span.id;

  const getSpanColor = (type: string) => {
    switch (type) {
      case 'plan': return '#cba6f7';
      case 'dispatch': return '#89b4fa';
      case 'tool_call': return '#fab387';
      case 'review': return '#f9e2af';
      case 'llm_call': return '#a6e3a1';
      case 'synthesize': return '#94e2d5';
      default: return '#bac2de';
    }
  };

  return (
    <div style={{ marginLeft: `${depth * 20}px`, marginTop: '6px' }}>
      <div
        onClick={() => onSelectSpan(span)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          backgroundColor: isSelected ? '#313244' : '#1e1e2e',
          border: isSelected ? '1px solid #89b4fa' : '1px solid #313244',
          borderRadius: '6px',
          cursor: 'pointer',
          transition: 'all 0.15s ease'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#a6adc8',
                cursor: 'pointer',
                fontSize: '0.8rem',
                padding: 0
              }}
            >
              {expanded ? '▼' : '▶'}
            </button>
          ) : (
            <span style={{ width: '12px' }} />
          )}

          <span
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              fontWeight: 700,
              backgroundColor: `${getSpanColor(span.span_type)}22`,
              color: getSpanColor(span.span_type),
              border: `1px solid ${getSpanColor(span.span_type)}44`
            }}
          >
            {span.span_type.toUpperCase()}
          </span>

          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#cdd6f4' }}>
            {span.actor}
          </span>
          {span.subtask_id && (
            <span style={{ fontSize: '0.75rem', color: '#a6adc8', background: '#313244', padding: '1px 6px', borderRadius: '3px' }}>
              {span.subtask_id}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.8rem' }}>
          <span style={{ color: '#89b4fa' }}>{span.latency_ms}ms</span>
          <span style={{ color: '#a6e3a1', fontWeight: 600 }}>${span.cost_usd.toFixed(6)}</span>
        </div>
      </div>

      {hasChildren && expanded && (
        <div style={{ borderLeft: '2px solid #313244', marginLeft: '12px', paddingLeft: '8px' }}>
          {span.children.map((child) => (
            <SpanNodeItem
              key={child.id}
              span={child}
              onSelectSpan={onSelectSpan}
              selectedSpanId={selectedSpanId}
              depth={0}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const TraceTree: React.FC<TraceTreeProps> = ({
  spans,
  onSelectSpan,
  selectedSpanId,
}) => {
  if (!spans || spans.length === 0) {
    return (
      <div style={{ padding: '24px', color: '#6c7086', textAlign: 'center', background: '#1e1e2e', borderRadius: '8px' }}>
        No spans found for this task execution trace.
      </div>
    );
  }

  return (
    <div>
      {spans.map((span) => (
        <SpanNodeItem
          key={span.id}
          span={span}
          onSelectSpan={onSelectSpan}
          selectedSpanId={selectedSpanId}
        />
      ))}
    </div>
  );
};
