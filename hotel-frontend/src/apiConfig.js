// file: src/apiConfig.js
// Extract subdomain dynamically and set API BASE URL
const hostname = window.location.hostname;

// Example: hostname = 'atlas.localhost' -> subdomain = 'atlas'
// In production: 'barok.hotelerp.acrmatech.com' -> subdomain = 'barok'
export const subdomain = hostname.split('.')[0];

const isProduction = hostname.includes('acrmatech.com');
const isNgrok = hostname.includes('ngrok-free.app');

// For *.localhost subdomains we use 127.0.0.1 (always resolves on Windows)
// without editing the hosts file.  The subdomain is sent as X-Tenant-Schema
// header so Django still knows which tenant schema to use.
export const API_BASE_URL = (hostname === 'localhost' || hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000/api'
    : hostname.endsWith('.localhost')
        ? 'http://127.0.0.1:8000/api'
        : isProduction
            ? `https://${hostname}/api`  // ← dynamic subdomain backend
            : isNgrok
                ? `${window.location.protocol}//${hostname}/api`
                : `http://127.0.0.1:8000/api`;

// Base host without /api — for images, media files, etc.
export const BASE_URL = (hostname === 'localhost' || hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : hostname.endsWith('.localhost')
        ? 'http://127.0.0.1:8000'
        : isProduction
            ? `https://${hostname}`      // ← dynamic subdomain base
            : isNgrok
                ? `${window.location.protocol}//${hostname}`
                : `http://127.0.0.1:8000`;

// Returns the tenant schema name to send as X-Tenant-Schema header.
// Priority: URL ?tenant= param → localStorage → logged-in user → subdomain
export const getTenantSchemaHint = () => {
    try {
        const urlTenant = new URLSearchParams(window.location.search).get('tenant');
        if (urlTenant) {
            localStorage.setItem('public_tenant_schema', urlTenant);
            return urlTenant;
        }
        const savedPublicTenant = localStorage.getItem('public_tenant_schema');
        if (savedPublicTenant) return savedPublicTenant;
        const user = JSON.parse(localStorage.getItem('user') || 'null');
        if (user?.tenant_schema) return user.tenant_schema;
        // Fall back to the subdomain extracted from the current URL
        // e.g. barok.localhost  →  'barok'
        if (hostname.endsWith('.localhost') || isProduction) {
            return subdomain;
        }
        return '';
    } catch (error) {
        return '';
    }
};