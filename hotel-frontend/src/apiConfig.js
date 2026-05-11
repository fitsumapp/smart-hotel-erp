// file: src/apiConfig.js
// Extract subdomain dynamically and set API BASE URL
const hostname = window.location.hostname;

// Example: hostname = 'atlas.localhost' -> subdomain = 'atlas'
// In production: 'barok.hotelerp.acrmatech.com' -> subdomain = 'barok'
const subdomain = hostname.split('.')[0];

const isProduction = hostname.includes('acrmatech.com');
const isNgrok = hostname.includes('ngrok-free.app');

// API_BASE_URL ends at /api — individual API calls append their own path
// e.g. API_BASE_URL + '/hotel/rooms/' => 'https://hotelerp.acrmatech.com/api/hotel/rooms/'
export const API_BASE_URL = (hostname === 'localhost' || hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000/api'
    : isProduction
        ? `https://${hostname}/api`   // uses current subdomain (e.g. hotel1.hotelerp.acrmatech.com)
        : isNgrok
            ? `${window.location.protocol}//${hostname}/api`
            : `http://${subdomain}.localhost:8000/api`;

// Base host without /api — for images, media files, etc.
export const BASE_URL = (hostname === 'localhost' || hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : isProduction
        ? `https://hotelerp.acrmatech.com`
        : isNgrok
            ? `${window.location.protocol}//${hostname}`
            : `http://${subdomain}.localhost:8000`;

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
        return user?.tenant_schema || '';
    } catch (error) {
        return '';
    }
};