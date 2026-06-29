import React, { useState, useEffect, useRef } from 'react';
import { Shield, Mail, Lock, User, Eye, EyeOff, ArrowRight, Loader } from 'lucide-react';
import { useAuth } from './AuthContext';
import './auth.css';

export default function LoginPage() {
  const { login, signup, googleLogin } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const googleBtnRef = useRef(null);

  // Initialize Google Sign-In
  useEffect(() => {
    const initGoogle = () => {
      if (window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID || '',
          callback: handleGoogleResponse,
        });
        if (googleBtnRef.current) {
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            type: 'standard',
            theme: 'filled_black',
            size: 'large',
            width: '100%',
            text: 'continue_with',
            shape: 'pill',
            logo_alignment: 'left',
          });
        }
      }
    };

    // Google script might load after component mounts
    if (window.google?.accounts?.id) {
      initGoogle();
    } else {
      const timer = setInterval(() => {
        if (window.google?.accounts?.id) {
          initGoogle();
          clearInterval(timer);
        }
      }, 200);
      return () => clearInterval(timer);
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoogleResponse = async (response) => {
    if (!response.credential) return;
    setLoading(true);
    setError('');
    try {
      await googleLogin(response.credential);
    } catch (err) {
      setError(err.message || 'Google sign-in failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'signup') {
        await signup(email, password, name);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode(mode === 'login' ? 'signup' : 'login');
    setError('');
  };

  return (
    <div className="auth-page">
      {/* Animated background elements */}
      <div className="auth-bg-orb auth-bg-orb-1" />
      <div className="auth-bg-orb auth-bg-orb-2" />
      <div className="auth-bg-orb auth-bg-orb-3" />
      <div className="auth-scanlines" />

      <div className="auth-card">
        {/* Brand header */}
        <div className="auth-brand">
          <div className="auth-brand-icon-wrap">
            <Shield className="auth-brand-icon" size={36} />
          </div>
          <h1 className="auth-brand-title">
            SENTRA<span className="auth-brand-accent">VISION</span>
          </h1>
          <p className="auth-brand-subtitle">AI Video Surveillance & Security</p>
        </div>

        {/* Mode toggle */}
        <div className="auth-toggle">
          <button
            className={`auth-toggle-btn ${mode === 'login' ? 'active' : ''}`}
            onClick={() => { setMode('login'); setError(''); }}
          >
            Sign In
          </button>
          <button
            className={`auth-toggle-btn ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => { setMode('signup'); setError(''); }}
          >
            Sign Up
          </button>
          <div className={`auth-toggle-slider ${mode === 'signup' ? 'right' : ''}`} />
        </div>

        {/* Error message */}
        {error && (
          <div className="auth-error">
            <span>⚠️</span> {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'signup' && (
            <div className="auth-input-group">
              <User size={18} className="auth-input-icon" />
              <input
                id="auth-name"
                type="text"
                placeholder="Full Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="auth-input"
                autoComplete="name"
              />
            </div>
          )}

          <div className="auth-input-group">
            <Mail size={18} className="auth-input-icon" />
            <input
              id="auth-email"
              type="email"
              placeholder="Email Address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="auth-input"
              required
              autoComplete="email"
            />
          </div>

          <div className="auth-input-group">
            <Lock size={18} className="auth-input-icon" />
            <input
              id="auth-password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
              required
              minLength={6}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            />
            <button
              type="button"
              className="auth-password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex={-1}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          <button
            id="auth-submit-btn"
            type="submit"
            className="auth-submit"
            disabled={loading}
          >
            {loading ? (
              <Loader size={18} className="spin-icon" />
            ) : (
              <>
                {mode === 'login' ? 'Sign In' : 'Create Account'}
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="auth-divider">
          <span>or</span>
        </div>

        {/* Google Sign-In */}
        <div className="auth-google-wrap">
          <div ref={googleBtnRef} className="auth-google-btn" />
        </div>

        {/* Toggle link */}
        <p className="auth-switch">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button type="button" className="auth-switch-link" onClick={toggleMode}>
            {mode === 'login' ? 'Sign Up' : 'Sign In'}
          </button>
        </p>
      </div>

      {/* Footer */}
      <p className="auth-footer">
        Powered by YOLO · LangChain · Pinecone
      </p>
    </div>
  );
}
