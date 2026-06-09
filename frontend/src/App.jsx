import React, { useState, useEffect, useRef } from 'react';
import { Shield, Activity, Terminal, Send, Upload, Video } from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [events, setEvents] = useState([]);
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'SentraVision AI online. How can I assist you with the security feed today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch events periodically
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const res = await fetch(`${API_BASE}/events`);
        const data = await res.json();
        setEvents(data);
      } catch (err) {
        // Silently fail if backend is offline
      }
    };
    
    fetchEvents();
    const interval = setInterval(fetchEvents, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, []);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg.content })
      });
      const data = await res.json();
      
      setMessages(prev => [...prev, { role: 'ai', content: data.response }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'ai', content: 'Error connecting to the backend. Is it running?' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/streams/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      alert(data.message);
    } catch (error) {
      alert('Failed to upload video. Make sure the backend is running!');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header glass-panel">
        <div className="brand">
          <Shield className="brand-icon" size={28} />
          <span>SENTRA<span style={{color: 'var(--primary)', fontWeight: 300}}>VISION</span></span>
        </div>
        <div style={{display: 'flex', gap: '16px', alignItems: 'center'}}>
           <input 
             type="file" 
             accept="video/*" 
             style={{display: 'none'}} 
             ref={fileInputRef}
             onChange={handleFileUpload} 
           />
           <button 
             onClick={() => fileInputRef.current?.click()} 
             style={{
               background: 'rgba(0, 240, 255, 0.1)', 
               border: '1px solid var(--primary)', 
               color: 'var(--primary)', 
               padding: '8px 16px', 
               borderRadius: '8px', 
               display: 'flex', 
               gap: '8px',
               cursor: 'pointer',
               alignItems: 'center',
               fontFamily: 'var(--font-family)',
               fontWeight: 600,
               transition: 'all 0.2s ease'
             }}
             onMouseOver={(e) => e.target.style.background = 'rgba(0, 240, 255, 0.2)'}
             onMouseOut={(e) => e.target.style.background = 'rgba(0, 240, 255, 0.1)'}
             disabled={uploading}
           >
             <Upload size={16} />
             {uploading ? 'Uploading...' : 'Upload Video'}
           </button>
           <span style={{fontSize: '0.85rem', color: 'var(--text-muted)'}}>SYSTEM STATUS: <span style={{color: '#0f0'}}>OPTIMAL</span></span>
        </div>
      </header>

      {/* Main Video Feed */}
      <main className="main-feed glass-panel">
        <div className="video-container">
          <div className="feed-overlay">
            <div className="live-badge">
              <div className="live-dot"></div>
              FEED ACTIVE
            </div>
          </div>
          <img src="/mock_feed.png" alt="Live Feed" className="video-feed" />
        </div>
      </main>

      {/* Right Sidebar */}
      <aside className="side-panel">
        
        {/* Real-time Event Log */}
        <div className="events-section glass-panel">
          <h3 className="section-title">
            <Activity size={18} color="var(--primary)" />
            Real-time Events
          </h3>
          <div className="events-list">
            {events.length === 0 ? (
              <div style={{color: 'var(--text-muted)', fontSize: '0.9rem', textAlign: 'center', marginTop: '20px'}}>No events logged yet. Upload a video to start processing!</div>
            ) : (
              events.map((ev, index) => (
                <div key={`${ev.id}-${index}`} className="event-card">
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                    <span className="event-title">{ev.type}</span>
                    <span className="event-time">{ev.time}</span>
                  </div>
                  <span style={{fontSize: '0.85rem', color: 'var(--text-main)'}}>{ev.desc}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* AI Chat Assistant */}
        <div className="chat-section glass-panel">
          <h3 className="section-title">
            <Terminal size={18} color="var(--primary)" />
            Security Assistant
          </h3>
          <div className="chat-history">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-msg ${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {loading && (
              <div className="chat-msg ai" style={{opacity: 0.6}}>
                <span className="typing-indicator">Analyzing...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-wrapper">
            <input 
              type="text" 
              className="chat-input" 
              placeholder="Ask about the footage..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            />
            <button className="chat-send" onClick={handleSend} disabled={loading || !input.trim()}>
              <Send size={18} />
            </button>
          </div>
        </div>

      </aside>
    </div>
  );
}

export default App;
