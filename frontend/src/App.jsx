import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Shield, Activity, Terminal, Send, Upload,
  Users, Cpu, Zap, CheckCircle, Loader,
  ShieldCheck, ShieldAlert, Car, Truck,
  CreditCard, AlertTriangle, Eye,
} from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

/* ── Event type configuration ──────────────────────────────────────────────── */
const EVT = {
  person_detected: { label: 'Person Detected',      cls: 'evt-cyan',   emoji: '👤' },
  vehicle_detected:{ label: 'Vehicle Detected',      cls: 'evt-blue',   emoji: '🚗' },
  helmet_on:       { label: 'Helmet On ✅',          cls: 'evt-green',  emoji: '⛑️' },
  no_helmet:       { label: 'No Helmet 🚨',          cls: 'evt-red',    emoji: '⚠️' },
  license_plate:   { label: 'License Plate',         cls: 'evt-amber',  emoji: '📋' },
};
const evtCfg = (type) => EVT[type] ?? { label: type, cls: '', emoji: '📌' };

/* ── StatBadge component ────────────────────────────────────────────────────── */
function StatBadge({ icon: Icon, label, value, color = 'default' }) {
  return (
    <div className={`stat-badge stat-${color}`}>
      <Icon size={12} />
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

/* ── Main App ───────────────────────────────────────────────────────────────── */
export default function App() {
  const [events,     setEvents]     = useState([]);
  const [messages,   setMessages]   = useState([{
    role: 'ai',
    content: 'SentraVision AI online. I can detect persons, helmets, vehicles & license plates in real-time.',
  }]);
  const [input,      setInput]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [uploading,  setUploading]  = useState(false);

  // Stream state
  const [streamId,    setStreamId]    = useState(null);
  const [streamStats, setStreamStats] = useState(null);
  const [videoBlob,   setVideoBlob]   = useState(null);   // local blob URL

  const messagesEndRef = useRef(null);
  const fileInputRef   = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);
  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  /* ── Poll events every 1.5 s ── */
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API_BASE}/events`);
        const d = await r.json();
        setEvents(d);
      } catch (_) {}
    }, 1500);
    return () => clearInterval(id);
  }, []);

  /* ── Poll stream stats every 1 s ── */
  useEffect(() => {
    if (!streamId) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API_BASE}/streams/status/${streamId}`);
        if (!r.ok) return;
        const d = await r.json();
        setStreamStats(d);
        if (d.status === 'done' || d.status === 'error') clearInterval(id);
      } catch (_) {}
    }, 1000);
    return () => clearInterval(id);
  }, [streamId]);

  /* ── File upload ── */
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Instant local preview
    setVideoBlob(URL.createObjectURL(file));
    setStreamStats(null);
    setUploading(true);

    const fd = new FormData();
    fd.append('file', file);
    try {
      const r  = await fetch(`${API_BASE}/streams/upload`, { method: 'POST', body: fd });
      const d  = await r.json();
      setStreamId(d.stream_id);
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `✅ "${file.name}" uploaded — Stream #${d.stream_id} started.\nDetecting persons · helmets · vehicles · license plates in real-time…`,
      }]);
    } catch (_) {
      setMessages(prev => [...prev, { role: 'ai', content: '❌ Upload failed. Is the backend running?' }]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  /* ── Chat ── */
  const handleSend = async () => {
    if (!input.trim()) return;
    const msg = { role: 'user', content: input };
    setMessages(p => [...p, msg]);
    setInput('');
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: msg.content }),
      });
      const d = await r.json();
      setMessages(p => [...p, { role: 'ai', content: d.response }]);
    } catch (_) {
      setMessages(p => [...p, { role: 'ai', content: '⚠️ Error connecting to backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  /* ── Derived stats ── */
  const isProcessing  = streamStats?.status === 'processing';
  const isDone        = streamStats?.status === 'done';
  const isError       = streamStats?.status === 'error';
  const progressPct   = streamStats?.progress        ?? 0;
  const fps           = streamStats?.fps             ?? 0;
  const personsCount  = streamStats?.persons_count   ?? 0;
  const helmetCount   = streamStats?.helmet_count    ?? 0;
  const noHelmetCount = streamStats?.no_helmet_count ?? 0;
  const vc            = streamStats?.vehicle_counts  ?? {};
  const totalVehicles = streamStats?.total_vehicles  ?? 0;
  const plates        = streamStats?.license_plates  ?? [];

  return (
    <div className="app-container">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="header glass-panel">
        <div className="brand">
          <Shield className="brand-icon" size={28} />
          <span>SENTRA<span style={{ color: 'var(--primary)', fontWeight: 300 }}>VISION</span></span>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {streamStats && (
            <div className={`processing-pill ${isDone ? 'pill-done' : isError ? 'pill-error' : ''}`}>
              {isProcessing ? <><Loader size={13} className="spin-icon" />Analyzing {progressPct}%</>
               : isDone     ? <><CheckCircle size={13} />Analysis Complete</>
               : isError    ? <>⚠️ Processing Error</>
               : null}
            </div>
          )}
          <input type="file" accept="video/*" style={{ display: 'none' }}
            ref={fileInputRef} onChange={handleFileUpload} />
          <button id="upload-video-btn" className="upload-btn"
            onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            <Upload size={15} />
            {uploading ? 'Uploading…' : 'Upload Video'}
          </button>
          <span className="sys-status">SYSTEM: <span style={{ color: '#0f0' }}>OPTIMAL</span></span>
        </div>
      </header>

      {/* ── Main Video Feed ─────────────────────────────────────────────────── */}
      <main className="main-feed glass-panel">
        <div className="video-container">

          {/* Feed badge (top-left) */}
          <div className="feed-overlay">
            <div className={`live-badge ${isProcessing ? 'badge-processing' : isDone ? 'badge-done' : ''}`}>
              <div className="live-dot" />
              {isProcessing ? 'ANALYZING' : isDone ? 'DONE' : 'FEED'}
            </div>
          </div>

          {/* ── Stats HUD (top-right overlay) ─────────────────────────────── */}
          {streamStats && (
            <div className="stats-hud">
              {/* Row 1 – persons */}
              <div className="hud-row">
                <StatBadge icon={Users}       label="Persons"    value={personsCount}  color={personsCount > 0 ? 'cyan' : 'default'} />
                <StatBadge icon={ShieldCheck} label="Helmets"    value={helmetCount}   color={helmetCount > 0 ? 'success' : 'default'} />
                <StatBadge icon={ShieldAlert} label="No Helmet"  value={noHelmetCount} color={noHelmetCount > 0 ? 'danger' : 'default'} />
              </div>
              {/* Row 2 – vehicles */}
              <div className="hud-row">
                <StatBadge icon={Car}   label="Cars"  value={vc.car  ?? 0} color="default" />
                <StatBadge icon={Car}   label="Bikes" value={vc.motorcycle ?? 0} color="default" />
                <StatBadge icon={Truck} label="Heavy" value={(vc.bus ?? 0) + (vc.truck ?? 0)} color="default" />
              </div>
              {/* Row 3 – progress + fps */}
              <div className="hud-row">
                <StatBadge icon={Cpu} label="Progress" value={`${progressPct}%`} color="default" />
                <StatBadge icon={Zap} label="FPS"      value={fps}               color="default" />
                <StatBadge icon={Eye} label="Vehicles" value={totalVehicles}      color={totalVehicles > 0 ? 'blue' : 'default'} />
              </div>
              {/* Row 4 – latest plate */}
              {plates.length > 0 && (
                <div className="hud-row">
                  <div className="plate-hud-tag">
                    <CreditCard size={12} />
                    {plates[plates.length - 1]}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Progress bar (bottom edge) */}
          {isProcessing && (
            <div className="progress-bar-wrap">
              <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
            </div>
          )}

          {/* Video or placeholder */}
          {videoBlob ? (
            <video key={videoBlob} className="video-feed"
              src={videoBlob} controls autoPlay muted loop />
          ) : (
            <div className="no-video-placeholder">
              <Upload size={44} style={{ opacity: 0.2, marginBottom: '14px' }} />
              <p>Upload a video to start AI analysis</p>
              <p className="placeholder-sub">
                Detects persons · helmets · vehicles · license plates
              </p>
            </div>
          )}

        </div>
      </main>

      {/* ── Right Sidebar ───────────────────────────────────────────────────── */}
      <aside className="side-panel">

        {/* License Plates panel – appears when plates are detected */}
        {plates.length > 0 && (
          <div className="plates-panel glass-panel">
            <h3 className="section-title" style={{ marginBottom: '10px' }}>
              <CreditCard size={16} color="var(--warning)" />
              License Plates Detected
            </h3>
            <div className="plates-list">
              {plates.map((p, i) => <span key={i} className="plate-tag">{p}</span>)}
            </div>
          </div>
        )}

        {/* Real-time Event Log */}
        <div className="events-section glass-panel">
          <h3 className="section-title">
            <Activity size={18} color="var(--primary)" />
            Event Log
            {events.length > 0 && (
              <span className="event-count-badge">{events.length}</span>
            )}
          </h3>
          <div className="events-list">
            {events.length === 0 ? (
              <div className="empty-state">Upload a video to start detecting events</div>
            ) : (
              events.map((ev, i) => {
                const cfg = evtCfg(ev.type);
                return (
                  <div key={`${ev.id}-${i}`} className={`event-card ${cfg.cls}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`event-title ${cfg.cls}`}>{cfg.emoji} {cfg.label}</span>
                      <span className="event-time">{ev.time}</span>
                    </div>
                    <span style={{ fontSize: '0.83rem', color: 'var(--text-main)' }}>{ev.desc}</span>
                    {ev.metadata?.confidence != null && (
                      <div className="conf-bar-wrap">
                        <div className="conf-bar-fill"
                          style={{ width: `${(ev.metadata.confidence * 100).toFixed(0)}%` }} />
                        <span className="conf-label">{(ev.metadata.confidence * 100).toFixed(0)}%</span>
                      </div>
                    )}
                    {ev.metadata?.vehicle_type && (
                      <span className="vehicle-badge">{ev.metadata.vehicle_type}</span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* AI Chat */}
        <div className="chat-section glass-panel">
          <h3 className="section-title">
            <Terminal size={18} color="var(--primary)" />
            Security Assistant
          </h3>
          <div className="chat-history">
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>{m.content}</div>
            ))}
            {loading && (
              <div className="chat-msg ai" style={{ opacity: 0.6 }}>
                <span className="typing-indicator">Analyzing…</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-wrapper">
            <input id="chat-input" type="text" className="chat-input"
              placeholder="Ask about the footage…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()} />
            <button id="chat-send-btn" className="chat-send"
              onClick={handleSend} disabled={loading || !input.trim()}>
              <Send size={18} />
            </button>
          </div>
        </div>

      </aside>
    </div>
  );
}
