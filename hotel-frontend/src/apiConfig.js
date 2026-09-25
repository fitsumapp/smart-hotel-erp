// Same-origin by default; localhost development keeps the separate Django port.
export const resolveApiBaseUrl = (location, configured = '') => {
  if (configured.trim()) return new URL(configured.trim(), location.origin).href.replace(/\/$/, '');
  if (['localhost', '127.0.0.1'].includes(location.hostname)) {
    return `${location.protocol}//${location.hostname}:8000/api`;
  }
  return `${location.origin}/api`;
};
export const API_BASE_URL = resolveApiBaseUrl(window.location, process.env.REACT_APP_API_BASE_URL || '');
export const BASE_URL = new URL(API_BASE_URL).origin;
