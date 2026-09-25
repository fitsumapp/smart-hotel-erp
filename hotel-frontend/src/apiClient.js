import axios from 'axios';
import { API_BASE_URL } from './apiConfig';

const transport = axios.create({ timeout: 20000 });
let refreshPromise;
let sessionGeneration = 0;

export const apiErrorMessage = (error, fallback = 'Request failed. Please try again.') => {
  const data = error?.response?.data;
  const detail = data?.error?.message || data?.detail || data?.error;
  if (typeof detail === 'string') return detail;
  if (data && typeof data === 'object') {
    const messages = Object.values(data).flat().filter(value => typeof value === 'string');
    if (messages.length) return messages.join(' ');
  }
  return fallback;
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
};

const withSessionLock = work => window.navigator?.locks
  ? window.navigator.locks.request('hotel-auth-session', work)
  : work();

export const refreshSession = failedAccess => {
  if (!refreshPromise) {
    const generation = sessionGeneration;
    refreshPromise = withSessionLock(async () => {
      const currentAccess = localStorage.getItem('access_token');
      if (currentAccess && currentAccess !== failedAccess) return currentAccess;
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) throw new Error('No refresh session.');
      const { data } = await transport.post(`${API_BASE_URL}/users/token/refresh/`, { refresh });
      if (generation !== sessionGeneration || localStorage.getItem('refresh_token') !== refresh) {
        throw new Error('Session changed during refresh.');
      }
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh || refresh);
      return data.access;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
};

export const logoutSession = async () => {
  // Settle in-flight rotation first, then revoke the account's session version.
  if (refreshPromise) await refreshPromise.catch(() => {});
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

const isApiRequest = config => {
  let url;
  try { url = new URL(config.url, config.baseURL || window.location.origin); }
  catch (_) { return false; }
  const base = new URL(API_BASE_URL);
  return url.origin === base.origin && url.pathname.startsWith(base.pathname + '/');
};

axios.interceptors.request.use(config => {
  if (isApiRequest(config)) {
    config.timeout = config.timeout || 20000;
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    else delete config.headers.Authorization;
  }
  return config;
});

axios.interceptors.response.use(response => response, async error => {
  const config = error.config;
  const status = error.response?.status;
  const authEndpoint = /\/(login|register|verify-mfa|verify-otp|resend-otp|token\/refresh)\//;
  if (config && isApiRequest(config) && status === 401 && !config._retried && !authEndpoint.test(config.url)) {
    config._retried = true;
    try {
      const oldAccess = String(config.headers?.Authorization || '').replace(/^Bearer /, '');
      await refreshSession(oldAccess);
      return axios(config);
    } catch (refreshError) {
      // Transient network failures must not destroy a valid refresh session.
      if ([400, 401].includes(refreshError.response?.status) || !localStorage.getItem('refresh_token')) {
        clearSession();
        window.dispatchEvent(new Event('hotel-session-expired'));
      }
      throw refreshError;
    }
  }
  if (error.response?.data && typeof error.response.data.error === 'object') {
    const envelope = error.response.data.error;
    error.response.data = { ...error.response.data, code: envelope.code, error_details: envelope, error: apiErrorMessage(error) };
  }
  return Promise.reject(error);
});
