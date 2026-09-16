// src/LoadingContext.js
// Shows loading overlay ONLY on mutating requests (POST, PUT, PATCH, DELETE).
// GET requests (page loads, polling) are always silent.
import React, { createContext, useContext, useState, useRef, useCallback } from 'react';
import axios from 'axios';

const LoadingContext = createContext(null);

// ── Methods that trigger the overlay ─────────────────────────────────────────
const LOADING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

// ── POST/PUT/DELETE paths that are background/non-critical (stay silent) ──────
const SILENT_PATTERNS = [
  /notifications/,
];

const shouldShowLoading = (config) => {
  const method = (config.method || '').toLowerCase();
  if (!LOADING_METHODS.has(method)) return false; // GET → silent
  const url = config.url || '';
  return !SILENT_PATTERNS.some((p) => p.test(url));
};

export function LoadingProvider({ children }) {
  const [loadingCount, setLoadingCount] = useState(0);
  const activeIds = useRef(new Set());
  const nextId = useRef(0);

  const inc = useCallback(() => setLoadingCount((c) => c + 1), []);
  const dec = useCallback(() => setLoadingCount((c) => Math.max(0, c - 1)), []);

  const interceptorsSet = useRef(false);
  if (!interceptorsSet.current) {
    interceptorsSet.current = true;

    axios.interceptors.request.use(
      (config) => {
        if (shouldShowLoading(config)) {
          const id = nextId.current++;
          config._loadingId = id;
          activeIds.current.add(id);
          inc();
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    const finish = (config) => {
      const id = config?._loadingId;
      if (id !== undefined && activeIds.current.has(id)) {
        activeIds.current.delete(id);
        dec();
      }
    };

    axios.interceptors.response.use(
      (response) => { finish(response.config); return response; },
      (error)    => { finish(error?.config);   return Promise.reject(error); }
    );
  }

  return (
    <LoadingContext.Provider value={{ isLoading: loadingCount > 0 }}>
      {children}
      <GlobalLoadingOverlay active={loadingCount > 0} />
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  return useContext(LoadingContext);
}

// ── Beautiful loading overlay ─────────────────────────────────────────────────
function GlobalLoadingOverlay({ active }) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(15,23,42,0.52)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
        // Block all interaction while loading; invisible when not active
        pointerEvents: active ? 'all' : 'none',
        opacity: active ? 1 : 0,
        transition: 'opacity 0.2s ease',
      }}
      aria-hidden={!active}
      aria-label="Loading"
    >
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 16,
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 20,
        padding: '32px 44px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        {/* Three concentric spinning rings */}
        <div style={{ position: 'relative', width: 60, height: 60 }}>
          <SpinRing size={60} dur="2.4s" color="#60a5fa" />
          <SpinRing size={42} dur="1.6s" color="#818cf8" reverse />
          <SpinRing size={24} dur="1.0s" color="#f472b6" />
          <div style={{
            position: 'absolute', inset: 0, margin: 'auto',
            width: 8, height: 8, borderRadius: '50%',
            background: '#fff',
            boxShadow: '0 0 8px 3px rgba(255,255,255,0.55)',
          }} />
        </div>

        <span style={{
          color: '#e2e8f0',
          fontSize: 14,
          fontWeight: 600,
          letterSpacing: '0.5px',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}>
          Processing…
        </span>
      </div>

      <style>{`
        @keyframes _ld_spin  { to { transform: rotate(360deg); } }
        @keyframes _ld_spinR { to { transform: rotate(-360deg); } }
      `}</style>
    </div>
  );
}

function SpinRing({ size, dur, color, reverse }) {
  const half = size / 2;
  return (
    <div style={{
      position: 'absolute',
      top: '50%', left: '50%',
      width: size, height: size,
      marginTop: -half, marginLeft: -half,
      borderRadius: '50%',
      border: '2.5px solid transparent',
      borderTopColor: color,
      borderRightColor: color + '55',
      animation: `${reverse ? '_ld_spinR' : '_ld_spin'} ${dur} linear infinite`,
    }} />
  );
}
