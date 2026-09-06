import React, { useEffect, useState } from 'react';
import { fetchMemories, deleteMemory, MemoryRecord } from '../api/memory';

export const Memory: React.FC = () => {
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMemories();
      setMemories(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch memories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMemories();
  }, []);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to hard-purge this memory record from Postgres and ChromaDB?')) {
      return;
    }
    setDeletingId(id);
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err: any) {
      alert(`Error deleting memory: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const filteredMemories = memories.filter((m) => {
    if (filterType === 'all') return true;
    return m.memory_type.toLowerCase() === filterType.toLowerCase();
  });

  const getTypeBadgeStyle = (type: string) => {
    switch (type.toLowerCase()) {
      case 'plan':
        return { backgroundColor: 'rgba(137, 180, 250, 0.2)', color: '#89b4fa', border: '1px solid #89b4fa' };
      case 'fact':
        return { backgroundColor: 'rgba(166, 227, 161, 0.2)', color: '#a6e3a1', border: '1px solid #a6e3a1' };
      case 'preference':
        return { backgroundColor: 'rgba(203, 166, 247, 0.2)', color: '#cba6f7', border: '1px solid #cba6f7' };
      default:
        return { backgroundColor: 'rgba(148, 163, 184, 0.2)', color: '#94a3b8', border: '1px solid #94a3b8' };
    }
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto', color: '#cdd6f4' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#a6e3a1', marginBottom: '8px' }}>
            Memory Dashboard
          </h1>
          <p style={{ color: '#a6adc8', fontSize: '14px' }}>
            Inspect short-term working state and long-term semantic memories stored in PostgreSQL & ChromaDB.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              backgroundColor: '#181825',
              border: '1px solid #313244',
              color: '#cdd6f4',
              borderRadius: '6px',
              padding: '8px 14px',
              fontSize: '14px',
              outline: 'none'
            }}
          >
            <option value="all">All Memory Types</option>
            <option value="plan">Plan</option>
            <option value="fact">Fact</option>
            <option value="preference">Preference</option>
          </select>

          <button
            onClick={loadMemories}
            disabled={loading}
            style={{
              backgroundColor: '#313244',
              color: '#cdd6f4',
              border: '1px solid #45475a',
              borderRadius: '6px',
              padding: '8px 14px',
              fontSize: '14px',
              fontWeight: 'bold',
              cursor: 'pointer'
            }}
          >
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
        </div>
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

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#a6adc8' }}>
          Loading memories...
        </div>
      ) : filteredMemories.length === 0 ? (
        <div style={{
          backgroundColor: '#181825',
          border: '1px solid #313244',
          borderRadius: '8px',
          padding: '48px',
          textAlign: 'center',
          color: '#a6adc8'
        }}>
          No memory records found for filter "{filterType}".
        </div>
      ) : (
        <div style={{
          backgroundColor: '#181825',
          border: '1px solid #313244',
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#11111b', borderBottom: '1px solid #313244', color: '#a6adc8', fontSize: '12px' }}>
                <th style={{ padding: '12px 16px' }}>TYPE</th>
                <th style={{ padding: '12px 16px' }}>SUMMARY</th>
                <th style={{ padding: '12px 16px' }}>IMPORTANCE SCORE</th>
                <th style={{ padding: '12px 16px' }}>RETRIEVED</th>
                <th style={{ padding: '12px 16px' }}>CREATED AT</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {filteredMemories.map((mem) => {
                const badgeStyle = getTypeBadgeStyle(mem.memory_type);
                return (
                  <tr key={mem.id} style={{ borderBottom: '1px solid #313244' }}>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{
                        padding: '4px 10px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 'bold',
                        ...badgeStyle
                      }}>
                        {mem.memory_type.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', color: '#cdd6f4', maxWidth: '400px' }}>
                      {mem.summary}
                    </td>
                    <td style={{ padding: '14px 16px', color: '#f9e2af', fontWeight: 'bold' }}>
                      {mem.importance_score.toFixed(2)}
                    </td>
                    <td style={{ padding: '14px 16px', color: '#89b4fa' }}>
                      {mem.retrieval_count} times
                    </td>
                    <td style={{ padding: '14px 16px', color: '#a6adc8', fontSize: '13px' }}>
                      {new Date(mem.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleDelete(mem.id)}
                        disabled={deletingId === mem.id}
                        style={{
                          backgroundColor: 'rgba(243, 139, 168, 0.15)',
                          color: '#f38ba8',
                          border: '1px solid #f38ba8',
                          borderRadius: '4px',
                          padding: '6px 12px',
                          fontSize: '12px',
                          fontWeight: 'bold',
                          cursor: deletingId === mem.id ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {deletingId === mem.id ? 'Deleting...' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
