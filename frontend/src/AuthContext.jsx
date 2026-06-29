import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

let envBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';
envBase = envBase.replace(/\/+$/, '');
if (!envBase.endsWith('/api')) {
  envBase += '/api';
}
const API_BASE = envBase;

const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('sv_token'));
  const [loading, setLoading] = useState(true);

  // Persist token
  useEffect(() => {
    if (token) {
      localStorage.setItem('sv_token', token);
    } else {
      localStorage.removeItem('sv_token');
    }
  }, [token]);

  // Validate existing token on mount
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error('Invalid token');
        return r.json();
      })
      .then((data) => {
        setUser(data);
      })
      .catch(() => {
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const signup = useCallback(async (email, password, name) => {
    const r = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });
    let data;
    try {
      data = await r.json();
    } catch (err) {
      throw new Error(`Server error (${r.status}): Failed to parse response.`);
    }
    if (!r.ok) throw new Error(data.detail || 'Signup failed');
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const login = useCallback(async (email, password) => {
    const r = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    let data;
    try {
      data = await r.json();
    } catch (err) {
      throw new Error(`Server error (${r.status}): Failed to parse response.`);
    }
    if (!r.ok) throw new Error(data.detail || 'Login failed');
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const googleLogin = useCallback(async (idToken) => {
    const r = await fetch(`${API_BASE}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken }),
    });
    let data;
    try {
      data = await r.json();
    } catch (err) {
      throw new Error(`Server error (${r.status}): Failed to parse response.`);
    }
    if (!r.ok) throw new Error(data.detail || 'Google login failed');
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('sv_token');
  }, []);

  // Helper for making authenticated API calls
  const authFetch = useCallback(
    (url, options = {}) => {
      const headers = { ...(options.headers || {}) };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      return fetch(url, { ...options, headers });
    },
    [token]
  );

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!user && !!token,
    signup,
    login,
    googleLogin,
    logout,
    authFetch,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
