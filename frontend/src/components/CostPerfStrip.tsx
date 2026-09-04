import React from 'react';

interface CostPerfStripProps {
  totalCostUsd: number;
  totalLatencyMs: number;
  costByAgent: Record<string, number>;
  costByTool: Record<string, number>;
}

export const CostPerfStrip: React.FC<CostPerfStripProps> = ({
  totalCostUsd,
  totalLatencyMs,
  costByAgent,
  costByTool,
}) => {
  const maxAgentCost = Math.max(...Object.values(costByAgent), 0.0001);
  const maxToolCost = Math.max(...Object.values(costByTool), 0.0001);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 2fr 2fr',
      gap: '16px',
      padding: '16px',
      backgroundColor: '#181825',
      borderRadius: '8px',
      border: '1px solid #313244',
      marginBottom: '20px',
      color: '#cdd6f4'
    }}>
      {/* Metric 1: Total Cost */}
      <div style={{ background: '#1e1e2e', padding: '12px', borderRadius: '6px', border: '1px solid #45475a' }}>
        <div style={{ fontSize: '0.75rem', color: '#a6adc8', textTransform: 'uppercase', fontWeight: 600 }}>Total Execution Cost</div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#a6e3a1', marginTop: '4px' }}>
          ${totalCostUsd.toFixed(6)}
        </div>
      </div>

      {/* Metric 2: Total Latency */}
      <div style={{ background: '#1e1e2e', padding: '12px', borderRadius: '6px', border: '1px solid #45475a' }}>
        <div style={{ fontSize: '0.75rem', color: '#a6adc8', textTransform: 'uppercase', fontWeight: 600 }}>Total Duration</div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#89b4fa', marginTop: '4px' }}>
          {(totalLatencyMs / 1000).toFixed(2)}s
        </div>
      </div>

      {/* Bar Chart 1: Cost by Agent */}
      <div style={{ background: '#1e1e2e', padding: '12px', borderRadius: '6px', border: '1px solid #45475a' }}>
        <div style={{ fontSize: '0.75rem', color: '#a6adc8', textTransform: 'uppercase', fontWeight: 600, marginBottom: '8px' }}>
          Cost by Agent
        </div>
        {Object.keys(costByAgent).length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: '#6c7086' }}>No agent cost data</div>
        ) : (
          Object.entries(costByAgent).map(([agent, cost]) => (
            <div key={agent} style={{ marginBottom: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#bac2de' }}>
                <span>{agent}</span>
                <span>${cost.toFixed(6)}</span>
              </div>
              <div style={{ background: '#313244', height: '6px', borderRadius: '3px', marginTop: '2px', overflow: 'hidden' }}>
                <div style={{
                  background: '#cba6f7',
                  height: '100%',
                  width: `${Math.min(100, (cost / maxAgentCost) * 100)}%`
                }} />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Bar Chart 2: Cost by Tool */}
      <div style={{ background: '#1e1e2e', padding: '12px', borderRadius: '6px', border: '1px solid #45475a' }}>
        <div style={{ fontSize: '0.75rem', color: '#a6adc8', textTransform: 'uppercase', fontWeight: 600, marginBottom: '8px' }}>
          Cost by Tool
        </div>
        {Object.keys(costByTool).length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: '#6c7086' }}>No tool executions</div>
        ) : (
          Object.entries(costByTool).map(([tool, cost]) => (
            <div key={tool} style={{ marginBottom: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#bac2de' }}>
                <span>{tool}</span>
                <span>${cost.toFixed(6)}</span>
              </div>
              <div style={{ background: '#313244', height: '6px', borderRadius: '3px', marginTop: '2px', overflow: 'hidden' }}>
                <div style={{
                  background: '#fab387',
                  height: '100%',
                  width: `${Math.min(100, (cost / maxToolCost) * 100)}%`
                }} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
