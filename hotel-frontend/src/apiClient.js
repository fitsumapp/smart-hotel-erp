import axios from 'axios';
import { API_BASE_URL } from './apiConfig';

const transport = axios.create({ timeout: 20000 });
let inFlightRefreshPromise = null;
let sessionGeneration = 0;

export const apiErrorMessage = (error, fallback = 'Request failed. Please try again.') => {
  if (!error) return fallback;

  // 1. Connection dropped / CORS preflight failure / timeout (no HTTP response received)
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return 'Request timed out. Please check your connection and try again.';
    }
    if (error.message === 'Network Error' || (typeof navigator !== 'undefined' && !navigator.onLine)) {
      return 'Unable to connect to the server. Please check your network connection.';
    }
    return error.message || fallback;
  }

  const { status, data } = error.response;

  // 2. High-level HTTP status codes
  if (status === 429) {
    const detail = data?.error?.message || data?.detail || data?.error;
    return typeof detail === 'string' ? detail : 'Too many requests. Please wait a moment and try again.';
  }
  if (status === 502 || status === 503 || status === 504) {
    return 'The server is temporarily unavailable or restarting. Please try again shortly.';
  }
  if (status === 401) {
    const detail = data?.error?.message || data?.detail || (typeof data?.error === 'string' ? data.error : null);
    if (detail && typeof detail === 'string') return detail;
    return 'Invalid credentials or session expired. Please sign in again.';
  }
  if (status === 403) {
    const detail = data?.error?.message || data?.detail || (typeof data?.error === 'string' ? data.error : null);
    if (detail && typeof detail === 'string') return detail;
    return 'You do not have permission to perform this action.';
  }

  // 3. Nested validation details (standard API envelope: data.error.details)
  const details = data?.error?.details || data?.error_details?.details || data?.details;
  if (details && typeof details === 'object') {
    const messages = [];
    const collect = (val, prefix = '') => {
      if (!val) return;
      if (Array.isArray(val)) {
        val.forEach(item => collect(item, prefix));
      } else if (typeof val === 'object') {
        Object.entries(val).forEach(([k, v]) => {
          const nextPrefix = k === 'non_field_errors' || k === 'detail' ? '' : `${k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}: `;
          collect(v, nextPrefix);
        });
      } else {
        const strVal = String(val);
        const capitalized = strVal.charAt(0).toUpperCase() + strVal.slice(1);
        messages.push(prefix ? `${prefix}${capitalized}` : capitalized);
      }
    };
    collect(details);
    if (messages.length > 0) return messages.join('\n');
  }

  // 4. Direct field validation dict: { username: ["..."] }
  if (typeof data === 'object' && !Array.isArray(data)) {
    const messages = [];
    Object.entries(data).forEach(([k, val]) => {
      if (['code', 'error', 'error_details'].includes(k)) return;
      const prefix = k === 'non_field_errors' || k === 'detail' ? '' : `${k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}: `;
      if (Array.isArray(val)) {
        val.forEach(v => {
          const strVal = String(v);
          const capitalized = strVal.charAt(0).toUpperCase() + strVal.slice(1);
          messages.push(`${prefix}${capitalized}`);
        });
      } else if (typeof val === 'string') {
        const capitalized = val.charAt(0).toUpperCase() + val.slice(1);
        messages.push(`${prefix}${capitalized}`);
      }
    });
    if (messages.length > 0) return messages.join('\n');
  }

  // 5. Fallback to detail / message strings
  const detail = data?.error?.message || data?.detail || (typeof data?.error === 'string' ? data.error : null);
  if (typeof detail === 'string' && detail !== 'Request could not be completed.') return detail;
  if (data && typeof data === 'object') {
    const messages = Object.values(data).flat().filter(value => typeof value === 'string');
    if (messages.length) return messages.join(' ');
  }
  return typeof detail === 'string' ? detail : fallback;
};

export const clearSession = () => {
  sessionGeneration += 1;
  ['access_token', 'refresh_token', 'user', 'user_data', 'public_tenant_schema'].forEach(key => localStorage.removeItem(key));
  delete axios.defaults.headers.common.Authorization;
};

export const saveSession = ({ tokens, user }) => {
  if (!tokens?.access || !tokens?.refresh || !user) throw new Error('Invalid login response.');
  sessionGeneration += 1;
  localStorage.setItem('access_token', tokens.access);
  localStorage.setItem('refresh_token', tokens.refresh);
  localStorage.setItem('user', JSON.stringify(user));
  axios.defaults.headers.common.Authorization = `Bearer ${tokens.access}`;
};

const withSessionLock = work => (typeof window !== 'undefined' && window.navigator?.locks)
  ? window.navigator.locks.request('hotel-auth-session', work)
  : work();

export const refreshSession = failedAccess => {
  // If access token was already rotated and updated by a parallel request, return it immediately
  const currentAccess = typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null;
  if (currentAccess && failedAccess && currentAccess !== failedAccess) {
    return Promise.resolve(currentAccess);
  }

  // Single-flight promise latch: reuse active in-flight refresh operation
  if (!inFlightRefreshPromise) {
    const generation = sessionGeneration;
    inFlightRefreshPromise = withSessionLock(async () => {
      const liveAccess = localStorage.getItem('access_token');
      if (liveAccess && failedAccess && liveAccess !== failedAccess) {
        return liveAccess;
      }
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) throw new Error('No refresh session.');

      try {
        const { data } = await transport.post(`${API_BASE_URL}/users/token/refresh/`, { refresh });
        if (generation !== sessionGeneration || localStorage.getItem('refresh_token') !== refresh) {
          // If session changed under us, do not overwrite with stale data
          const updated = localStorage.getItem('access_token');
          if (updated) return updated;
          throw new Error('Session changed during refresh.');
        }
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh || refresh);
        axios.defaults.headers.common.Authorization = `Bearer ${data.access}`;
        return data.access;
      } catch (err) {
        const status = err.response?.status;
        const code = err.response?.data?.code;
        const isTerminalAuthFailure = [400, 401].includes(status) && (
          code === 'token_not_valid' ||
          code === 'session_revoked' ||
          code === 'user_inactive' ||
          !localStorage.getItem('refresh_token') ||
          (err.response?.data && typeof err.response.data.detail === 'string' && (
            err.response.data.detail.toLowerCase().includes('blacklisted') ||
            err.response.data.detail.toLowerCase().includes('revoked') ||
            err.response.data.detail.toLowerCase().includes('invalid')
          ))
        );

        if (isTerminalAuthFailure) {
          clearSession();
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new Event('hotel-session-expired'));
          }
        }
        // For transient network errors, 502/503/504, or lock timeouts, do NOT clearSession
        throw err;
      }
    }).finally(() => {
      inFlightRefreshPromise = null;
    });
  }
  return inFlightRefreshPromise;
};

export const logoutSession = async () => {
  if (inFlightRefreshPromise) await inFlightRefreshPromise.catch(() => {});
  return withSessionLock(async () => {
    try {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) await transport.post(`${API_BASE_URL}/users/logout/`, { refresh });
    } catch (error) {
      if (![400, 401].includes(error.response?.status)) throw error;
    }
    clearSession();
  });
};

export const isApiRequest = config => {
  if (!config?.url) return false;
  let url;
  try { url = new URL(config.url, config.baseURL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')); }
  catch (_) { return false; }
  const base = new URL(API_BASE_URL);
  if (url.origin !== base.origin) return false;
  const basePath = base.pathname.replace(/\/+$/, '');
  return basePath === '' || url.pathname === basePath || url.pathname.startsWith(basePath + '/');
};

axios.interceptors.request.use(config => {
  if (isApiRequest(config)) {
    config.timeout = config.timeout || 20000;
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (token) {
      if (config.headers && typeof config.headers.set === 'function') {
        config.headers.set('Authorization', `Bearer ${token}`);
      } else {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    } else {
      if (config.headers && typeof config.headers.delete === 'function') {
        config.headers.delete('Authorization');
      } else if (config.headers) {
        delete config.headers.Authorization;
      }
    }
  }
  return config;
});

axios.interceptors.response.use(response => response, async error => {
  const config = error.config;
  const status = error.response?.status;
  const authEndpoint = /\/(login|register|verify-mfa|verify-otp|resend-otp|token\/refresh)\//;

  // Single retry on 401 using refreshed token
  if (config && isApiRequest(config) && status === 401 && !config._retried && !authEndpoint.test(config.url)) {
    config._retried = true;
    try {
      const oldHeader = config.headers?.Authorization || (typeof config.headers?.get === 'function' ? config.headers.get('Authorization') : '');
      const oldAccess = String(oldHeader || '').replace(/^Bearer /, '');
      const newAccess = await refreshSession(oldAccess);

      if (config.headers && typeof config.headers.set === 'function') {
        config.headers.set('Authorization', `Bearer ${newAccess}`);
      } else {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${newAccess}`;
      }
      return axios(config);
    } catch (refreshError) {
      // Re-throw so callers handle appropriately
      throw refreshError;
    }
  }

  // Normalize API envelope error details if present
  if (error.response?.data && typeof error.response.data.error === 'object') {
    const envelope = error.response.data.error;
    error.response.data = {
      ...error.response.data,
      code: envelope.code,
      error_details: envelope,
      error: apiErrorMessage(error)
    };
  }

  return Promise.reject(error);
});
