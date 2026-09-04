import React, { useState } from 'react';
import { TraceSpanData, triggerTaskReplay } from '../api/traces';

interface ReplayModalProps {
  span: TraceSpanData;
  onClose: () => void;
  onReplaySuccess: (replayTaskId: string) => void;
}

export const ReplayModal: React.FC<ReplayModalProps> = ({
  span,
  onClose,
  onReplaySuccess,
}) => {
  const [inputOverrideJson, setInputOverrideJson] = useState<string>(
    JSON.stringify({ request_text: span.payload?.request_text || '' }, null, 2)
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmitReplay = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      let parsedOverride: Record<string, any> | undefined = undefined;
      if (inputOverrideJson.trim()) {
        parsedOverride = JSON.parse(inputOverrideJson);
      }
      const checkpointIdToUse = span.payload?.checkpoint_id || span.id;
      const res = await triggerTaskReplay(span.task_id, checkpointIdToUse, parsedOverride);
      onReplaySuccess(res.resulting_task_id);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to launch task replay.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      fontFamily: 'sans-serif'
    }}>
      <div style={{
        backgroundColor: '#181825',
        border: '1px solid #45475a',
        borderRadius: '8px',
        width: '560px',
        padding: '24px',
        color: '#cdd6f4',
        boxShadow: '0 10px 30px rgba(0,0,0,0.6)'
      }}>
        <h3 style={{ margin: '0 0 12px 0', color: '#89b4fa' }}>🔄 Trigger Task Replay</h3>
        <p style={{ fontSize: '0.85rem', color: '#a6adc8', marginBottom: '16px' }}>
          Replay execution from span node <strong>{span.actor}</strong> ({span.id.slice(0, 8)}).
          Optionally override the input payload below before launching forward execution as a new task run.
        </p>

        {errorMessage && (
          <div style={{
            background: '#f38ba8',
            color: '#11111b',
            padding: '10px',
            borderRadius: '6px',
            fontSize: '0.85rem',
            marginBottom: '12px'
          }}>
            {errorMessage}
          </div>
        )}

        <label style={{ fontSize: '0.8rem', color: '#bac2de', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
          Input Override (JSON format):
        </label>
        <textarea
          value={inputOverrideJson}
          onChange={(e) => setInputOverrideJson(e.target.value)}
          rows={8}
          style={{
            width: '100%',
            backgroundColor: '#11111b',
            color: '#a6e3a1',
            border: '1px solid #313244',
            borderRadius: '6px',
            padding: '10px',
            fontFamily: 'monospace',
            fontSize: '0.85rem',
            marginBottom: '20px',
            boxSizing: 'border-box'
          }}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              padding: '8px 16px',
              backgroundColor: '#313244',
              color: '#cdd6f4',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmitReplay}
            disabled={isSubmitting}
            style={{
              padding: '8px 20px',
              backgroundColor: '#a6e3a1',
              color: '#11111b',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            {isSubmitting ? 'Launching...' : 'Run Replay'}
          </button>
        </div>
      </div>
    </div>
  );
};
