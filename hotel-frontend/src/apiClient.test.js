import {
  apiErrorMessage,
  clearSession,
  saveSession,
  refreshSession,
  isApiRequest
} from './apiClient';
import { resolveApiBaseUrl, API_BASE_URL } from './apiConfig';
import axios from 'axios';

describe('apiErrorMessage parser', () => {
  it('extracts nested validation error messages from backend envelope', () => {
    const error = {
      response: {
        data: {
          error: 'Request could not be completed.',
          code: 'invalid',
          error_details: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              name: ['inventory category with this name already exists.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Name: Inventory category with this name already exists.');
  });

  it('extracts error from direct details object', () => {
    const error = {
      response: {
        data: {
          error: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              selling_price: ['Ensure this value is greater than or equal to 0.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Selling Price: Ensure this value is greater than or equal to 0.');
  });

  it('extracts non_field_errors without field prefix', () => {
    const error = {
      response: {
        data: {
          error: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              non_field_errors: ['Invalid username or password combination.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Invalid username or password combination.');
  });

  it('extracts HTTP 429 throttle messages cleanly', () => {
    const error = {
      response: {
        status: 429,
        data: {
          error: {
            code: 'throttled',
            message: 'Request was throttled. Expected available in 45 seconds.'
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Request was throttled. Expected available in 45 seconds.');
  });

  it('handles server unavailable 502/503/504 errors with informative message', () => {
    const error = {
      response: {
        status: 503,
        data: {}
      }
    };
    expect(apiErrorMessage(error)).toBe('The server is temporarily unavailable or restarting. Please try again shortly.');
  });

  it('handles connection timeout and offline network errors', () => {
    const timeoutErr = {
      code: 'ECONNABORTED',
      message: 'timeout of 20000ms exceeded',
      response: undefined
    };
    expect(apiErrorMessage(timeoutErr)).toBe('Request timed out. Please check your connection and try again.');

    const netErr = {
      message: 'Network Error',
      response: undefined
    };
    expect(apiErrorMessage(netErr)).toBe('Unable to connect to the server. Please check your network connection.');
  });
});

describe('resolveApiBaseUrl routing logic', () => {
  it('resolves localhost development port 3000 to Django port 8000', () => {
    const loc = { origin: 'http://localhost:3000', hostname: 'localhost', protocol: 'http:', port: '3000' };
    expect(resolveApiBaseUrl(loc)).toBe('http://localhost:8000/api');
  });

  it('resolves LAN development IP on port 3000 to same LAN IP on Django port 8000', () => {
    const loc = { origin: 'http://192.168.1.15:3000', hostname: '192.168.1.15', protocol: 'http:', port: '3000' };
    expect(resolveApiBaseUrl(loc)).toBe('http://192.168.1.15:8000/api');
  });

  it('resolves production reverse-proxied origin without custom port to same-origin /api', () => {
    const loc = { origin: 'https://hotelerp.acrmatech.com', hostname: 'hotelerp.acrmatech.com', protocol: 'https:', port: '' };
    expect(resolveApiBaseUrl(loc)).toBe('https://hotelerp.acrmatech.com/api');
  });

  it('respects explicitly configured REACT_APP_API_BASE_URL', () => {
    const loc = { origin: 'https://anywhere.com', hostname: 'anywhere.com', protocol: 'https:', port: '' };
    expect(resolveApiBaseUrl(loc, 'https://api.external.com/api/')).toBe('https://api.external.com/api');
  });
});

describe('Session management & isApiRequest', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('saveSession stores credentials and clearSession removes them', () => {
    saveSession({
      tokens: { access: 'test_acc_123', refresh: 'test_ref_456' },
      user: { id: 1, email: 'admin@hotel.com', role: 'admin' }
    });
    expect(localStorage.getItem('access_token')).toBe('test_acc_123');
    expect(localStorage.getItem('refresh_token')).toBe('test_ref_456');

    clearSession();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('isApiRequest matches API base URL endpoints and rejects foreign origins', () => {
    expect(isApiRequest({ url: `${API_BASE_URL}/users/settings/` })).toBe(true);
    expect(isApiRequest({ url: 'https://api.chapa.co/v1/transaction/initialize' })).toBe(false);
  });
});
