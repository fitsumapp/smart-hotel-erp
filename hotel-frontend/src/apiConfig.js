// Environment-aware API Base URL resolution
export const resolveApiBaseUrl = (location, configured = '') => {
  if (configured && configured.trim()) {
    return new URL(configured.trim(), location.origin).href.replace(/\/+$/, '');
  }
  // In development, when the frontend is served on a development port (e.g. 3000, 3001, 5173),
  // route to Django port 8000 on the same host (handles localhost, 127.0.0.1, and local LAN IPs like 192.168.x.x)
  if (location && location.port && !['80', '443', ''].includes(location.port)) {
    return `${location.protocol}//${location.hostname}:8000/api`;
  }
  // Production default: same-origin reverse-proxied /api
  return `${location.origin}/api`;
};

export const API_BASE_URL = resolveApiBaseUrl(
  typeof window !== 'undefined' ? window.location : { origin: 'http://localhost:3000', hostname: 'localhost', protocol: 'http:', port: '3000' },
  process.env.REACT_APP_API_BASE_URL || ''
);

export const BASE_URL = new URL(API_BASE_URL).origin;
