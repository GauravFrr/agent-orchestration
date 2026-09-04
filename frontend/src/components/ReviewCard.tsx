import React, { useState } from 'react';
import { ReviewRequest, submitDecision, DecisionPayload } from '../api/reviews';
import { ChatWithAgent } from './ChatWithAgent';

interface ReviewCardProps {
  review: ReviewRequest;
  onDecisionSubmitted: () => void;
}

export const ReviewCard: React.FC<ReviewCardProps> = ({ review, onDecisionSubmitted }) => {
  const [activeTab, setActiveTab] = useState<'decision' | 'chat'>('decision');
  const [decisionMode, setDecisionMode] = useState<'approve' | 'modify' | 'reject' | 'take_over' | null>(null);
  
  const [feedback, setFeedback] = useState('');
  const [modifiedInputStr, setModifiedInputStr] = useState(
    JSON.stringify(review.context_snapshot?.subtask?.input || {}, null, 2)
  );
  const [takenOverOutputStr, setTakenOverOutputStr] = useState(
    JSON.stringify({ summary: "Human-verified output for subtask" }, null, 2)
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPending = review.status === 'pending';

  const handleExecuteDecision = async (decision: 'approve' | 'modify' | 'reject' | 'take_over') => {
    setSubmitting(true);
    setError(null);

    let payload: DecisionPayload = { decision };

    try {
      if (decision === 'reject') {
        payload.feedback = feedback || 'Action rejected by human reviewer.';
      } else if (decision === 'modify') {
        payload.feedback = feedback;
        payload.modified_input = JSON.parse(modifiedInputStr);
      } else if (decision === 'take_over') {
        payload.feedback = feedback;
        payload.taken_over_output = JSON.parse(takenOverOutputStr);
      } else if (decision === 'approve') {
        payload.feedback = feedback;
      }

      await submitDecision(review.id, payload);
      onDecisionSubmitted();
    } catch (err: any) {
      setError(err.message || 'Failed to submit decision');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      backgroundColor: '#181825',
      borderRadius: '8px',
      border: '1px solid #313244',
      padding: '20px',
      color: '#cdd6f4',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    }}>
      {/* Header Badge Strip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{
            backgroundColor: '#fab387',
            color: '#11111b',
            padding: '4px 10px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 'bold'
          }}>
            Trigger: {review.trigger_reason}
          </span>
          <span style={{
            backgroundColor: '#f38ba8',
            color: '#11111b',
            padding: '4px 10px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 'bold'
          }}>
            Level: {review.approval_level.toUpperCase()}
          </span>
        </div>
        <span style={{ fontSize: '12px', color: '#a6adc8' }}>
          ID: {review.id.slice(0, 8)}...
        </span>
      </div>

      {/* Task Context Overview */}
      <div style={{ backgroundColor: '#1e1e2e', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
        <div style={{ fontWeight: 'bold', color: '#89b4fa', marginBottom: '4px' }}>Original Request:</div>
        <div>{review.context_snapshot?.request_text || 'N/A'}</div>
        
        {review.context_snapshot?.subtask && (
          <div style={{ marginTop: '8px' }}>
            <span style={{ fontWeight: 'bold', color: '#a6e3a1' }}>Target Subtask: </span>
            <code>{review.context_snapshot.subtask.id}</code> ({review.context_snapshot.subtask.specialist})
            {review.context_snapshot.subtask.action_tag && (
              <span style={{ marginLeft: '8px', color: '#f9e2af' }}>
                🏷️ tag: {review.context_snapshot.subtask.action_tag}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Proposed Action Card */}
      <div style={{
        backgroundColor: '#313244',
        padding: '14px',
        borderRadius: '6px',
        borderLeft: '4px solid #89b4fa'
      }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', color: '#cdd6f4', marginBottom: '6px' }}>
          Agent Proposed Action
        </div>
        <div style={{ fontSize: '13px', color: '#bac2de' }}>
          {review.context_snapshot?.proposed_action || 'Execute subtask with provided parameters.'}
        </div>
      </div>

      {/* Decision / Chat Tab Switcher */}
      <div style={{ display: 'flex', borderBottom: '1px solid #313244', gap: '16px' }}>
        <button
          onClick={() => setActiveTab('decision')}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'decision' ? '2px solid #89b4fa' : 'none',
            color: activeTab === 'decision' ? '#89b4fa' : '#a6adc8',
            padding: '8px 12px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '13px'
          }}
        >
          Human Decision Panel
        </button>
        <button
          onClick={() => setActiveTab('chat')}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'chat' ? '2px solid #89b4fa' : 'none',
            color: activeTab === 'chat' ? '#89b4fa' : '#a6adc8',
            padding: '8px 12px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '13px'
          }}
        >
          Chat with Paused Agent
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'chat' ? (
        <ChatWithAgent reviewId={review.id} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {!isPending ? (
            <div style={{
              padding: '12px',
              backgroundColor: '#181825',
              border: '1px solid #a6e3a1',
              borderRadius: '6px',
              color: '#a6e3a1',
              fontSize: '13px'
            }}>
              ✅ Decision <strong>{review.status.toUpperCase()}</strong> recorded.
              {review.decision_payload?.author && (
                <div style={{ fontSize: '11px', color: '#bac2de', marginTop: '4px' }}>
                  Author: {review.decision_payload.author.type} ({review.decision_payload.author.user_id}) at {review.decided_at}
                </div>
              )}
            </div>
          ) : (
            <>
              {error && (
                <div style={{ color: '#f38ba8', fontSize: '13px', padding: '8px', backgroundColor: '#313244', borderRadius: '4px' }}>
                  ⚠️ {error}
                </div>
              )}

              {/* Feedback Input */}
              <div>
                <label style={{ fontSize: '12px', color: '#a6adc8', display: 'block', marginBottom: '4px' }}>
                  Feedback / Notes (optional for approve, required for reject):
                </label>
                <input
                  type="text"
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Enter human feedback notes..."
                  style={{
                    width: '100%',
                    backgroundColor: '#1e1e2e',
                    border: '1px solid #45475a',
                    borderRadius: '4px',
                    color: '#cdd6f4',
                    padding: '8px',
                    fontSize: '13px'
                  }}
                />
              </div>

              {/* Inline Editors for Modify / Take Over */}
              {decisionMode === 'modify' && (
                <div>
                  <label style={{ fontSize: '12px', color: '#fab387', display: 'block', marginBottom: '4px' }}>
                    Modified Subtask Input (JSON):
                  </label>
                  <textarea
                    rows={5}
                    value={modifiedInputStr}
                    onChange={(e) => setModifiedInputStr(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#11111b',
                      border: '1px solid #fab387',
                      borderRadius: '4px',
                      color: '#a6e3a1',
                      fontFamily: 'monospace',
                      padding: '8px',
                      fontSize: '12px'
                    }}
                  />
                </div>
              )}

              {decisionMode === 'take_over' && (
                <div>
                  <label style={{ fontSize: '12px', color: '#f38ba8', display: 'block', marginBottom: '4px' }}>
                    Human Authored Subtask Output (JSON Takeover):
                  </label>
                  <textarea
                    rows={5}
                    value={takenOverOutputStr}
                    onChange={(e) => setTakenOverOutputStr(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#11111b',
                      border: '1px solid #f38ba8',
                      borderRadius: '4px',
                      color: '#89b4fa',
                      fontFamily: 'monospace',
                      padding: '8px',
                      fontSize: '12px'
                    }}
                  />
                </div>
              )}

              {/* 4 Decision Buttons */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
                <button
                  disabled={submitting}
                  onClick={() => handleExecuteDecision('approve')}
                  style={{
                    backgroundColor: '#a6e3a1',
                    color: '#11111b',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  Approve
                </button>

                <button
                  disabled={submitting}
                  onClick={() => {
                    if (decisionMode === 'modify') handleExecuteDecision('modify');
                    else setDecisionMode('modify');
                  }}
                  style={{
                    backgroundColor: '#fab387',
                    color: '#11111b',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  {decisionMode === 'modify' ? 'Submit Modify' : 'Modify'}
                </button>

                <button
                  disabled={submitting}
                  onClick={() => handleExecuteDecision('reject')}
                  style={{
                    backgroundColor: '#f38ba8',
                    color: '#11111b',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  Reject
                </button>

                <button
                  disabled={submitting}
                  onClick={() => {
                    if (decisionMode === 'take_over') handleExecuteDecision('take_over');
                    else setDecisionMode('take_over');
                  }}
                  style={{
                    backgroundColor: '#cba6f7',
                    color: '#11111b',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  {decisionMode === 'take_over' ? 'Submit Take Over' : 'Take Over'}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
