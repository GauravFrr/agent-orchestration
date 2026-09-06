import React, { useState, useEffect } from 'react';
import { Home } from './pages/Home';
import { Reviews } from './pages/Reviews';
import { TraceExplorer } from './pages/TraceExplorer';
import { Memory } from './pages/Memory';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path: string) => {
    window.history.pushState({}, '', path);
    setCurrentPath(path);
  };

  const getActiveTab = () => {
    if (currentPath === '/reviews' || currentPath.startsWith('/reviews/')) return 'reviews';
    if (currentPath === '/traces' || currentPath.startsWith('/traces/')) return 'traces';
    if (currentPath === '/memory' || currentPath.startsWith('/memory/')) return 'memory';
    return 'home';
  };

  const activeTab = getActiveTab();

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
        <div
          onClick={() => navigate('/')}
          style={{ fontWeight: 'bold', fontSize: '18px', color: '#89b4fa', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <span>⚡ Agent Orchestration Platform</span>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => navigate('/')}
            style={{
              backgroundColor: activeTab === 'home' ? '#313244' : 'transparent',
              color: activeTab === 'home' ? '#89b4fa' : '#a6adc8',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Task Operations
          </button>
          <button
            onClick={() => navigate('/reviews')}
            style={{
              backgroundColor: activeTab === 'reviews' ? '#313244' : 'transparent',
              color: activeTab === 'reviews' ? '#f38ba8' : '#a6adc8',
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
            onClick={() => navigate('/traces')}
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
          <button
            onClick={() => navigate('/memory')}
            style={{
              backgroundColor: activeTab === 'memory' ? '#313244' : 'transparent',
              color: activeTab === 'memory' ? '#a6e3a1' : '#a6adc8',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Memory Dashboard
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === 'home' && <Home navigate={navigate} />}
      {activeTab === 'reviews' && <Reviews />}
      {activeTab === 'traces' && <TraceExplorer />}
      {activeTab === 'memory' && <Memory />}
    </div>
  );
}
