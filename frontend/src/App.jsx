import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Shield, Activity, Terminal, Send, Upload,
  Users, Cpu, Zap, CheckCircle, Loader,
  ShieldCheck, ShieldAlert, Car, Truck,
  CreditCard, AlertTriangle, Eye,
} from 'lucide-react';
import './index.css';

const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000/api').replace(/\/+$/, '');

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
  const [videoBlob,   setVideoBlob]   = useState(null);
  
  // Post-analysis report
  const [report,      setReport]      = useState(null);   // local blob URL

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
        if (!r.ok) return;
        const d = await r.json();
        if (Array.isArray(d)) {
          setEvents(d);
        }
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
    setReport(null);
    setUploading(true);

    const fd = new FormData();
    fd.append('file', file);
    try {
      const r  = await fetch(`${API_BASE}/streams/upload`, { method: 'POST', body: fd });
      if (!r.ok) {
        const errText = await r.text();
        throw new Error(`Upload Failed (${r.status}): ${errText}`);
      }
      const d  = await r.json();
      setStreamId(d.stream_id);
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `✅ "${file.name}" uploaded — Stream #${d.stream_id} started.\nDetecting persons · helmets · vehicles · license plates in real-time…`,
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: `❌ Error: ${err.message}` }]);
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

  /* ── Fetch report when done ── */
  useEffect(() => {
    if (isDone && !report) {
      fetch(`${API_BASE}/reports/summary`)
        .then(r => r.json())
        .then(d => setReport(d))
        .catch(console.error);
    }
  }, [isDone, report]);

  return (
    <div className="page-wrapper">
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
                      <span className="event-time">
                        {ev.metadata?.video_time ? `${ev.metadata.video_time.toFixed(1)}s` : ev.time}
                      </span>
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

      {/* ── Comprehensive Bottom Summary ────────────────────────────────────── */}
      {isDone && report && (
        <div className="bottom-summary glass-panel" style={{ margin: '0 16px 16px 16px' }}>
          <h2 className="summary-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle size={28} /> Analysis Report
          </h2>

          {/* ── Aggregate Stats Row ── */}
          {report.stats && (
            <div className="stats-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '12px', marginBottom: '24px' }}>
              {[
                { label: 'Persons', value: report.stats.total_persons, icon: '👤', color: 'var(--primary)' },
                { label: 'Helmets', value: report.stats.total_helmets, icon: '⛑️', color: 'var(--success)' },
                { label: 'No Helmet', value: report.stats.total_no_helmets, icon: '🚨', color: 'var(--danger)' },
                { label: 'Cars', value: report.stats.total_cars, icon: '🚗', color: 'var(--blue)' },
                { label: 'Motorcycles', value: report.stats.total_motorcycles, icon: '🏍️', color: 'var(--warning)' },
                { label: 'Vehicles', value: report.stats.total_vehicles, icon: '🚛', color: 'var(--text-muted)' },
                { label: 'Plates Read', value: report.stats.total_plates_read, icon: '📋', color: 'var(--warning)' },
              ].map((s, i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.04)', border: '1px solid var(--panel-border)',
                  borderRadius: '12px', padding: '16px', textAlign: 'center',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                }}>
                  <div style={{ fontSize: '1.8rem', marginBottom: '4px' }}>{s.icon}</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── No-Helmet Time Ranges ── */}
          <div style={{ background: 'rgba(255,255,255,0.05)', padding: '16px', borderRadius: '12px', border: '1px solid var(--panel-border)', marginBottom: '20px' }}>
            <h4 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldAlert size={18} /> No-Helmet Time Ranges
            </h4>
            {report.no_helmet_ranges && report.no_helmet_ranges.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {report.no_helmet_ranges.map((tr, i) => (
                  <span key={`tr-${i}`} style={{ background: 'rgba(255,68,68,0.15)', color: '#ff7777', padding: '6px 12px', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 600 }}>
                    {tr}
                  </span>
                ))}
              </div>
            ) : (
              <span style={{ fontSize: '0.95rem', color: 'var(--success)' }}>✅ All detected riders wore helmets.</span>
            )}
          </div>

          {/* ── Violations Table ── */}
          {report.violations && report.violations.length > 0 && (
            <div style={{ background: 'rgba(255,68,68,0.04)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,68,68,0.2)', marginBottom: '20px' }}>
              <h4 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} /> Helmet Violations Detail
              </h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left' }}>Person ID</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left' }}>Time</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left' }}>Confidence</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left' }}>License Plate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.violations.map((v, i) => (
                      <tr key={`v-${i}`} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--danger)', fontWeight: 600 }}>#{v.person_id}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--text-main)' }}>{v.time}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ color: v.confidence >= 0.5 ? 'var(--warning)' : 'var(--text-muted)', fontWeight: 600 }}>
                            {(v.confidence * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          {v.license_plate === 'Unable to read' ? (
                            <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Unable to read</span>
                          ) : (
                            <span style={{ background: 'rgba(255,204,0,0.1)', color: 'var(--warning)', padding: '2px 8px', borderRadius: '4px', fontWeight: 700, fontFamily: 'monospace' }}>
                              {v.license_plate}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Tracked Entities Grid ── */}
          {report.all_detections && report.all_detections.length > 0 && (
            <>
              <h3 style={{ marginBottom: '16px', color: 'var(--text-main)' }}>Tracked Entities</h3>
              <div className="summary-grid">
                {report.all_detections.map((obj, i) => {
                  const clsType = obj.type.replace(/\s+/g, '-');
                  return (
                    <div key={`obj-${i}`} className="summary-card">
                      <div className="card-header">
                        <span className={`type-${clsType}`}>{obj.type}</span>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>ID #{obj.id}</span>
                      </div>
                      <div className="card-conf">
                        <div>AI Confidence Score</div>
                        <div className="conf-bar-wrap" style={{ marginTop: 0, height: '6px' }}>
                          <div className="conf-bar-fill" style={{ width: `${(obj.confidence * 100).toFixed(0)}%` }} />
                        </div>
                        <div style={{ textAlign: 'right', fontWeight: 600, color: 'var(--text-main)' }}>
                          {(obj.confidence * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

    </div>
  );
}
