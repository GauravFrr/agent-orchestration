import React, { useEffect, useState } from 'react';
import { ReviewRequest, fetchReviews } from '../api/reviews';
import { ReviewCard } from '../components/ReviewCard';
import { useReviewSocket } from '../hooks/useReviewSocket';

export const Reviews: React.FC = () => {
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'pending' | 'all'>('pending');
  const [loading, setLoading] = useState(true);

  const loadReviews = async () => {
    try {
      const data = await fetchReviews(filter === 'pending' ? 'pending' : undefined);
      setReviews(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load reviews:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviews();
  }, [filter]);

  useReviewSocket(() => {
    loadReviews();
  });

  const selectedReview = reviews.find((r) => r.id === selectedId) || reviews[0];

  return (
    <div style={{
      display: 'flex',
      height: 'calc(100vh - 60px)',
      backgroundColor: '#11111b',
      color: '#cdd6f4',
      fontFamily: 'sans-serif'
    }}>
      {/* Left Queue Panel */}
      <div style={{
        width: '320px',
        borderRight: '1px solid #313244',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#181825'
      }}>
        <div style={{
          padding: '16px',
          borderBottom: '1px solid #313244',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ margin: 0, fontSize: '16px', color: '#cdd6f4' }}>Review Queue</h2>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
            style={{
              backgroundColor: '#1e1e2e',
              color: '#cdd6f4',
              border: '1px solid #45475a',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '12px'
            }}
          >
            <option value="pending">Pending Only</option>
            <option value="all">All Reviews</option>
          </select>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {loading ? (
            <div style={{ padding: '16px', color: '#a6adc8', fontSize: '13px' }}>Loading reviews...</div>
          ) : reviews.length === 0 ? (
            <div style={{ padding: '16px', color: '#a6adc8', fontSize: '13px' }}>No review requests found.</div>
          ) : (
            reviews.map((r) => {
              const isSelected = r.id === selectedId;
              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedId(r.id)}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    marginBottom: '8px',
                    cursor: 'pointer',
                    backgroundColor: isSelected ? '#313244' : '#1e1e2e',
                    border: isSelected ? '1px solid #89b4fa' : '1px solid transparent'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#89b4fa' }}>
                      {r.trigger_reason}
                    </span>
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: r.status === 'pending' ? '#fab387' : '#a6e3a1',
                      color: '#11111b',
                      fontWeight: 'bold'
                    }}>
                      {r.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#bac2de', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.context_snapshot?.request_text || 'No description'}
                  </div>
                  <div style={{ fontSize: '10px', color: '#a6adc8', marginTop: '4px' }}>
                    Level: {r.approval_level}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Decision & Detail Panel */}
      <div style={{ flex: 1, padding: '24px', overflowY: 'auto' }}>
        {selectedReview ? (
          <ReviewCard review={selectedReview} onDecisionSubmitted={loadReviews} />
        ) : (
          <div style={{ color: '#a6adc8', textAlign: 'center', marginTop: '100px' }}>
            Select a review request from the queue to view details and execute decisions.
          </div>
        )}
      </div>
    </div>
  );
};
