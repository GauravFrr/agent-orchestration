import React, { useState } from 'react';
import { sendChatWithAgent } from '../api/reviews';

interface ChatWithAgentProps {
  reviewId: string;
}

interface Message {
  sender: 'human' | 'agent';
  text: string;
}

export const ChatWithAgent: React.FC<ChatWithAgentProps> = ({ reviewId }) => {
  const [messages, setMessages] = useState<Message[]>([
    { sender: 'agent', text: 'Task is currently paused for human review. Ask me any question about the current execution context or reasoning.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { sender: 'human', text: userMsg }]);
    setLoading(true);

    try {
      const res = await sendChatWithAgent(reviewId, userMsg);
      setMessages((prev) => [...prev, { sender: 'agent', text: res.response }]);
    } catch (err: any) {
      setMessages((prev) => [...prev, { sender: 'agent', text: `Error: ${err.message || 'Failed to reach agent'}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '320px',
      backgroundColor: '#1e1e2e',
      borderRadius: '8px',
      border: '1px solid #313244',
      overflow: 'hidden'
    }}>
      <div style={{
        padding: '10px 14px',
        backgroundColor: '#181825',
        borderBottom: '1px solid #313244',
        fontSize: '13px',
        fontWeight: 'bold',
        color: '#cdd6f4'
      }}>
        💬 Q&A with Paused Agent
      </div>

      <div style={{
        flex: 1,
        padding: '12px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        {messages.map((m, idx) => (
          <div key={idx} style={{
            alignSelf: m.sender === 'human' ? 'flex-end' : 'flex-start',
            maxWidth: '85%',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '13px',
            lineHeight: '1.4',
            backgroundColor: m.sender === 'human' ? '#89b4fa' : '#313244',
            color: m.sender === 'human' ? '#11111b' : '#cdd6f4'
          }}>
            {m.text}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', fontSize: '12px', color: '#a6adc8', fontStyle: 'italic' }}>
            Agent is typing...
          </div>
        )}
      </div>

      <form onSubmit={handleSend} style={{
        display: 'flex',
        padding: '8px',
        borderTop: '1px solid #313244',
        gap: '8px',
        backgroundColor: '#181825'
      }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask why a step was taken or request clarification..."
          style={{
            flex: 1,
            backgroundColor: '#1e1e2e',
            border: '1px solid #45475a',
            borderRadius: '4px',
            color: '#cdd6f4',
            padding: '6px 10px',
            fontSize: '13px',
            outline: 'none'
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            backgroundColor: '#89b4fa',
            color: '#11111b',
            border: 'none',
            borderRadius: '4px',
            padding: '6px 14px',
            fontSize: '13px',
            fontWeight: 'bold',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};
