import React, { useState } from 'react';
import { Reviews } from './pages/Reviews';
import { TraceExplorer } from './pages/TraceExplorer';

export default function App() {
  const [activeTab, setActiveTab] = useState<'reviews' | 'traces'>('reviews');

  return (
    <div style={{
      backgroundColor: '#11111b',
      minHeight: '100vh',
      color: '#cdd6f4',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Top Navbar */}
      <div style={{
        height: '60px',
        borderBottom: '1px solid #313244',
        backgroundColor: '#181825',
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        justifyContent: 'space-between'
      }}>
        <div style={{ fontWeight: 'bold', fontSize: '18px', color: '#89b4fa' }}>
          ⚡ Agent Orchestration Platform
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button
            onClick={() => setActiveTab('reviews')}
            style={{
              backgroundColor: activeTab === 'reviews' ? '#313244' : 'transparent',
              color: activeTab === 'reviews' ? '#89b4fa' : '#a6adc8',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Human Reviews Queue
          </button>
          <button
            onClick={() => setActiveTab('traces')}
            style={{
              backgroundColor: activeTab === 'traces' ? '#313244' : 'transparent',
              color: activeTab === 'traces' ? '#cba6f7' : '#a6adc8',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Trace Explorer & Replay
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === 'reviews' && <Reviews />}
      {activeTab === 'traces' && <TraceExplorer />}
    </div>
  );
}
