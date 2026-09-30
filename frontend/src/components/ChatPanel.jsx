import { useState, useRef, useEffect } from 'react';
import api from '../api';

// ─── Suggested questions ─────────────────────────────────────────────────────
const SUGGESTIONS = [
  'Is this design safe?',
  'Why did it fail?',
  'How can I improve the safety factor?',
  'What does the compliance mean?',
  'How much material was removed?',
  'Is the displacement acceptable?',
  'What is the stress utilisation?',
  'Explain the topology optimization result.',
];

// ─── Single message bubble ────────────────────────────────────────────────────
function Bubble({ role, content }) {
  const isUser = role === 'user';
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '10px',
    }}>
      {!isUser && (
        <div style={{
          width: '28px', height: '28px', borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '13px', marginRight: '8px', marginTop: '2px',
        }}>🤖</div>
      )}
      <div style={{
        maxWidth: '82%',
        padding: '10px 14px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser
          ? 'linear-gradient(135deg, rgba(139,92,246,0.35), rgba(6,182,212,0.25))'
          : 'var(--bg-elevated)',
        border: `1px solid ${isUser ? 'rgba(139,92,246,0.3)' : 'var(--border-subtle)'}`,
        fontSize: '12px',
        lineHeight: '1.6',
        color: 'var(--text-primary)',
        whiteSpace: 'pre-wrap',
      }}>
        {content}
      </div>
    </div>
  );
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '8px 12px' }}>
      <div style={{
        width: '28px', height: '28px', borderRadius: '50%',
        background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px',
      }}>🤖</div>
      <div style={{ background: 'var(--bg-elevated)', borderRadius: '12px', padding: '10px 14px', display: 'flex', gap: '4px' }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--accent-purple)',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

// ─── Main ChatPanel ───────────────────────────────────────────────────────────
export default function ChatPanel({ spec, feaResult, topoResult, isOpen, onToggle }) {
  const [messages, setMessages]   = useState([
    { role: 'assistant', content: 'Hi! I\'m your design AI. Ask me anything about the FEA results, safety margins, or topology optimization. 👋' },
  ]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef(null);
  const inputRef                  = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isOpen]);

  const sendMessage = async (text) => {
    const userText = (text || input).trim();
    if (!userText || loading) return;
    setInput('');

    const newMessages = [...messages, { role: 'user', content: userText }];
    setMessages(newMessages);
    setLoading(true);

    try {
      // Send only the last 10 messages to keep context window small
      const historySlice = newMessages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      const res = await api.sendChatMessage(historySlice, spec, feaResult, topoResult);
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply || res.error || 'No response.' }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <>
      {/* ── Bounce keyframe ─────────────────────────────────────────── */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        @keyframes slide-up {
          from { opacity: 0; transform: translateY(20px) scale(0.95); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .chat-panel-open { animation: slide-up 0.25s ease; }
      `}</style>

      {/* ── Toggle bubble button ─────────────────────────────────────── */}
      <button
        id="chat-toggle-btn"
        onClick={onToggle}
        title="Ask AI about results"
        style={{
          position: 'fixed', bottom: '24px', right: '24px', zIndex: 1000,
          width: '52px', height: '52px', borderRadius: '50%', border: 'none',
          background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)',
          color: '#fff', fontSize: '22px', cursor: 'pointer',
          boxShadow: '0 4px 20px rgba(139,92,246,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'transform 0.2s, box-shadow 0.2s',
        }}
        onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
      >
        {isOpen ? '✕' : '🤖'}
      </button>

      {/* ── Chat panel ──────────────────────────────────────────────── */}
      {isOpen && (
        <div
          className="chat-panel-open"
          style={{
            position: 'fixed', bottom: '88px', right: '24px', zIndex: 999,
            width: '380px', height: '520px',
            background: 'rgba(15,23,42,0.97)',
            border: '1px solid rgba(139,92,246,0.3)',
            borderRadius: '20px',
            display: 'flex', flexDirection: 'column',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(139,92,246,0.15)',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '14px 18px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(6,182,212,0.1))',
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <div style={{
              width: '34px', height: '34px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px',
            }}>🤖</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '13px' }}>Design AI Assistant</div>
              <div style={{ fontSize: '10px', color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-green)', boxShadow: '0 0 6px var(--accent-green)' }} />
                Context-aware · {feaResult ? 'FEA loaded' : 'No results yet'}
              </div>
            </div>
            <button onClick={() => setMessages([{ role: 'assistant', content: 'Chat cleared. What would you like to know?' }])}
              style={{ marginLeft: 'auto', fontSize: '10px', padding: '3px 8px', borderRadius: '6px', cursor: 'pointer',
                background: 'transparent', border: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              Clear
            </button>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '14px 12px' }}>
            {messages.map((m, i) => <Bubble key={i} role={m.role} content={m.content} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          {/* Suggestions (only before first user message) */}
          {messages.length <= 1 && (
            <div style={{ padding: '0 12px 8px', display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
              {SUGGESTIONS.slice(0, 4).map(s => (
                <button key={s} onClick={() => sendMessage(s)}
                  style={{
                    fontSize: '10px', padding: '4px 10px', borderRadius: '20px', cursor: 'pointer',
                    background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)',
                    color: 'var(--accent-purple)', whiteSpace: 'nowrap',
                  }}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div style={{
            padding: '12px', borderTop: '1px solid var(--border-subtle)',
            display: 'flex', gap: '8px', alignItems: 'flex-end',
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about stress, safety factor, material…"
              rows={1}
              style={{
                flex: 1, resize: 'none', padding: '10px 12px',
                background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                borderRadius: '12px', color: 'var(--text-primary)', fontSize: '12px',
                fontFamily: 'inherit', outline: 'none', lineHeight: '1.5',
                maxHeight: '80px', overflowY: 'auto',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => e.target.style.borderColor = 'rgba(139,92,246,0.5)'}
              onBlur={e => e.target.style.borderColor = 'var(--border-subtle)'}
            />
            <button
              id="chat-send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              style={{
                width: '38px', height: '38px', borderRadius: '10px', border: 'none', cursor: 'pointer',
                background: input.trim() && !loading
                  ? 'linear-gradient(135deg, #8b5cf6, #06b6d4)'
                  : 'var(--bg-elevated)',
                color: input.trim() && !loading ? '#fff' : 'var(--text-muted)',
                fontSize: '16px', transition: 'all 0.2s', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {loading ? '⏳' : '↑'}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
