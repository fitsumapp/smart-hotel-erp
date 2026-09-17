import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import './App.css';
import CategoryManager from './CategoryManager';
import MenuManager from './MenuManager';
import RoomManager from './RoomManager';
import TableManager from './TableManager';
import UserManager from './UserManager';
import AuthPage from './AuthPage';
import CustomerDashboard from './pages/CustomerDashboard';
import BookingsManager from './pages/BookingsManager';
import ReportsCenter from './pages/ReportsCenter';

// Settings component
import SystemSettingsManager from './SystemSettingsManager';

// Role-specific dashboards
import WaiterDashboard from './pages/WaiterDashboard';
import CashierDashboard from './pages/CashierDashboard';
import KitchenDashboard from './pages/KitchenDashboard';
import BarDashboard from './pages/BarDashboard';
import ReceptionDashboard from './pages/ReceptionDashboard';
import InventoryDashboard from './pages/InventoryDashboard';
import FinanceDashboard from './pages/FinanceDashboard';
import CustomerPaymentPage from './pages/CustomerPaymentPage';
import PublicBookingConfirmation from './pages/PublicBookingConfirmation';
import OrdersManager from './pages/OrdersManager';

import { Bell, Search, LogOut, Loader2, Menu } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import { API_BASE_URL, getTenantSchemaHint } from './apiConfig';

// --- AXIOS INTERCEPTOR ---
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    
    // Add Tenant Schema Header automatically
    const tenantHint = getTenantSchemaHint();
    if (tenantHint) {
      config.headers['X-Tenant-Schema'] = tenantHint;
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const code = error.response.data?.error?.code || error.response.data?.code;
      if (code === 'token_not_valid') {
        console.warn('Session expired. Refreshing auth state...');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_data');
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// Inline SVG icons (no extra import needed)
// ─────────────────────────────────────────────────────────────────────────────
const ShoppingCartIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
);
const BedIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v9"/>
  </svg>
);
const BoxIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
    <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
  </svg>
);
const TrendUpIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
    <polyline points="17 6 23 6 23 12"/>
  </svg>
);
const PeopleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);

// ─────────────────────────────────────────────────────────────────────────────
// Shared style constants used by the dashboard
// ─────────────────────────────────────────────────────────────────────────────
const progressBg   = { height: '7px', backgroundColor: '#e2e8f0', borderRadius: '10px', overflow: 'hidden' };
const progressFill = { height: '100%', borderRadius: '10px', transition: 'width 0.6s ease' };
const divSeparator = { height: '1px', backgroundColor: 'rgba(148,163,184,0.14)', margin: '14px 0' };
const labelSmall   = { fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.4px' };
const miniPill     = { padding: '6px 12px', borderRadius: '20px', fontSize: '11px', fontWeight: '700', whiteSpace: 'nowrap' };

// Header & Navigation styles
const searchBarStyle = {
  display: 'flex',
  alignItems: 'center',
  backgroundColor: '#f1f5f9',
  padding: '8px 14px',
  borderRadius: '10px',
  width: '300px',
  border: '1px solid rgba(148,163,184,0.12)'
};
const searchInputStyle = {
  border: 'none',
  backgroundColor: 'transparent',
  marginLeft: '8px',
  outline: 'none',
  color: '#0f172a',
  fontSize: '13px',
  fontWeight: '500',
  width: '100%'
};
const headerActionStyle = { display: 'flex', alignItems: 'center', gap: '16px' };
const userProfileStyle  = { display: 'flex', alignItems: 'center', paddingLeft: '16px', borderLeft: '1px solid rgba(148,163,184,0.16)' };
const pageTitle = { fontSize: '22px', fontWeight: '800', marginBottom: '22px', letterSpacing: '-0.5px', color: '#0f172a', textAlign: 'left' };
const logoutButtonStyle = {
  backgroundColor: '#fef2f2',
  border: '1px solid rgba(239,68,68,0.2)',
  padding: '8px',
  borderRadius: '8px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginLeft: '10px',
  transition: 'all 0.2s'
};

// ─────────────────────────────────────────────────────────────────────────────
// Reusable UI Sub-components
// ─────────────────────────────────────────────────────────────────────────────
const KpiCard = ({ label, value, icon, color, bg, alert }) => (
  <motion.div
    whileHover={{ y: -3, boxShadow: '0 12px 28px rgba(15,23,42,0.1)' }}
    style={{
      backgroundColor: bg,
      border: `1px solid ${color}22`,
      borderRadius: '16px',
      padding: '16px',
      position: 'relative',
      overflow: 'hidden',
      cursor: 'default',
      transition: 'all 0.2s'
    }}
  >
    {alert && (
      <div style={{
        position: 'absolute', top: '10px', right: '10px',
        width: '8px', height: '8px', borderRadius: '50%',
        backgroundColor: '#ef4444', boxShadow: '0 0 0 3px rgba(239,68,68,0.2)'
      }} />
    )}
    <div style={{ fontSize: '22px', marginBottom: '10px' }}>{icon}</div>
    <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: '6px' }}>{label}</div>
    <div style={{ fontSize: '17px', fontWeight: '900', color, lineHeight: '1.2', wordBreak: 'break-word' }}>{value}</div>
  </motion.div>
);

const SectionCard = ({ title, subtitle, icon, iconBg, iconColor, children }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35 }}
    style={{
      backgroundColor: 'rgba(255,255,255,0.94)',
      borderRadius: '20px',
      border: '1px solid rgba(148,163,184,0.14)',
      boxShadow: '0 8px 24px rgba(15,23,42,0.05)',
      padding: '22px',
      display: 'flex',
      flexDirection: 'column'
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
      <div style={{ width: '38px', height: '38px', borderRadius: '10px', backgroundColor: iconBg, color: iconColor, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        {icon}
      </div>
      <div>
        <h3 style={{ margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f172a' }}>{title}</h3>
        <p style={{ margin: 0, fontSize: '10px', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{subtitle}</p>
      </div>
    </div>
    {children}
  </motion.div>
);

const MetricBox = ({ label, value, accent, alert }) => (
  <div style={{
    backgroundColor: '#f8fafc',
    borderRadius: '12px',
    padding: '14px',
    border: `1px solid ${alert ? 'rgba(239,68,68,0.25)' : 'rgba(148,163,184,0.12)'}`
  }}>
    <p style={{ margin: 0, fontSize: '10px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</p>
    <p style={{ margin: '5px 0 0', fontWeight: '900', fontSize: '20px', color: alert ? '#ef4444' : accent }}>{value}</p>
  </div>
);

const RoomStatusPill = ({ label, count, color, bg }) => (
  <div style={{ backgroundColor: bg, borderRadius: '10px', padding: '10px', textAlign: 'center', border: `1px solid ${color}22` }}>
    <p style={{ margin: 0, fontWeight: '900', fontSize: '18px', color }}>{count}</p>
    <p style={{ margin: '3px 0 0', fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{label}</p>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// 1. ADMIN DASHBOARD CONTENT
// ─────────────────────────────────────────────────────────────────────────────
const DashboardContent = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.get(`${API_BASE_URL}/users/dashboard-stats/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch dashboard stats', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '350px', gap: '15px' }}>
        <Loader2 className="animate-spin" size={36} style={{ color: '#0f766e' }} />
        <span style={{ color: '#64748b', fontWeight: '600', fontSize: '14px' }}>Loading Dashboard Metrics...</span>
      </div>
    );
  }

  const pos          = stats?.pos          || {};
  const rooms        = stats?.rooms        || {};
  const reservations = stats?.reservations || {};
  const inventory    = stats?.inventory    || {};
  const finance      = stats?.finance      || {};
  const staff        = stats?.staff        || {};

  const fmt  = (n) => (n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtN = (n) => (n || 0).toLocaleString();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* ── ROW 1: KPI Strip ────────────────────────────────────────────── */}
      <div className="kpi-grid">
        <KpiCard label="Today's Revenue"    value={`ETB ${fmt(pos.todayRevenue)}`}           icon="💰" color="#0f766e" bg="#f0fdfa" />
        <KpiCard label="Total POS Revenue"  value={`ETB ${fmt(pos.revenue)}`}                icon="🧾" color="#3b82f6" bg="#eff6ff" />
        <KpiCard label="Occupancy Rate"     value={`${rooms.occupancyPct || 0}%`}            icon="🏨" color="#8b5cf6" bg="#f5f3ff" />
        <KpiCard label="Active Reservations" value={fmtN(reservations.active)}               icon="📅" color="#f59e0b" bg="#fffbeb" />
        <KpiCard label="Low Stock Alerts"   value={fmtN(inventory.lowStockAlerts)}           icon="⚠️" color="#ef4444" bg="#fef2f2" alert={inventory.lowStockAlerts > 0} />
        <KpiCard label="Net Profit"         value={`ETB ${fmt(finance.netProfit)}`}          icon="📈"
          color={finance.netProfit >= 0 ? '#10b981' : '#ef4444'}
          bg={finance.netProfit >= 0 ? '#f0fdf4' : '#fef2f2'} />
      </div>

      {/* ── ROW 2: POS + Rooms ──────────────────────────────────────────── */}
      <div className="dashboard-two-col">

        {/* POS / Food & Beverage */}
        <SectionCard title="Point of Sale" subtitle="Food & Beverage Orders" iconBg="#eff6ff" iconColor="#3b82f6" icon={<ShoppingCartIcon />}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <MetricBox label="Total Orders"    value={fmtN(pos.totalOrders)}            accent="#3b82f6" />
            <MetricBox label="Today's Orders"  value={fmtN(pos.todayOrders)}            accent="#0f766e" />
            <MetricBox label="Pending Orders"  value={fmtN(pos.pendingOrders)}          accent="#f59e0b" alert={pos.pendingOrders > 0} />
            <MetricBox label="Tips Collected"  value={`ETB ${fmt(pos.tips)}`}           accent="#10b981" />
          </div>
          <div style={divSeparator} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={labelSmall}>Today's Revenue</span>
            <span style={{ fontWeight: '800', fontSize: '18px', color: '#0f766e' }}>ETB {fmt(pos.todayRevenue)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
            <span style={labelSmall}>Total Lifetime Revenue</span>
            <span style={{ fontWeight: '700', fontSize: '14px', color: '#1e293b' }}>ETB {fmt(pos.revenue)}</span>
          </div>
        </SectionCard>

        {/* Front Office & Rooms */}
        <SectionCard title="Front Office & Rooms" subtitle="Room Status Overview" iconBg="#f5f3ff" iconColor="#8b5cf6" icon={<BedIcon />}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
            <RoomStatusPill label="Available"   count={rooms.available   || 0} color="#10b981" bg="#f0fdf4" />
            <RoomStatusPill label="Occupied"    count={rooms.occupied    || 0} color="#8b5cf6" bg="#f5f3ff" />
            <RoomStatusPill label="Reserved"    count={rooms.reserved    || 0} color="#3b82f6" bg="#eff6ff" />
            <RoomStatusPill label="Cleaning"    count={rooms.cleaning    || 0} color="#f59e0b" bg="#fffbeb" />
            <RoomStatusPill label="Maintenance" count={rooms.maintenance || 0} color="#ef4444" bg="#fef2f2" />
            <RoomStatusPill label="Total"       count={rooms.total       || 0} color="#0f766e" bg="#f0fdfa" />
          </div>
          <div style={divSeparator} />
          <div style={{ marginBottom: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={labelSmall}>Occupancy Rate</span>
              <span style={{ fontWeight: '800', fontSize: '13px', color: '#8b5cf6' }}>{rooms.occupancyPct || 0}%</span>
            </div>
            <div style={progressBg}>
              <div style={{ ...progressFill, width: `${rooms.occupancyPct || 0}%`, background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)' }} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <div style={{ ...miniPill, backgroundColor: '#eff6ff', color: '#3b82f6' }}>
              ✈️ {reservations.checkInsToday || 0} Check-ins Today
            </div>
            <div style={{ ...miniPill, backgroundColor: '#fef2f2', color: '#ef4444' }}>
              🚪 {reservations.checkOutsToday || 0} Check-outs Today
            </div>
          </div>
        </SectionCard>
      </div>

      {/* ── ROW 3: Inventory + Finance + Staff ──────────────────────────── */}
      <div className="dashboard-three-col">

        {/* Inventory */}
        <SectionCard title="Inventory Control" subtitle="Stock & Asset Overview" iconBg="#fffbeb" iconColor="#f59e0b" icon={<BoxIcon />}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <MetricBox label="Total SKUs"       value={fmtN(inventory.totalItems)}     accent="#f59e0b" />
            <MetricBox label="Low Stock Items"  value={fmtN(inventory.lowStockAlerts)} accent="#ef4444" alert={inventory.lowStockAlerts > 0} />
          </div>
          <div style={divSeparator} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={labelSmall}>Total Inventory Value</span>
            <span style={{ fontWeight: '800', fontSize: '16px', color: '#f59e0b' }}>ETB {fmt(inventory.totalValue)}</span>
          </div>
          {inventory.lowStockAlerts > 0 && (
            <div style={{ marginTop: '10px', padding: '10px 14px', backgroundColor: '#fef2f2', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.2)', fontSize: '12px', color: '#ef4444', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
              ⚠️ {inventory.lowStockAlerts} item{inventory.lowStockAlerts !== 1 ? 's' : ''} below reorder level
            </div>
          )}
        </SectionCard>

        {/* Finance */}
        <SectionCard title="Finance & Accounts" subtitle="Income, Expenses & Profit" iconBg="#f0fdf4" iconColor="#10b981" icon={<TrendUpIcon />}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', backgroundColor: '#f0fdf4', borderRadius: '12px', border: '1px solid rgba(16,185,129,0.15)' }}>
              <div>
                <p style={{ margin: 0, fontSize: '10px', fontWeight: '700', color: '#10b981', letterSpacing: '0.5px', textTransform: 'uppercase' }}>Total Income</p>
                <p style={{ margin: '3px 0 0', fontWeight: '800', fontSize: '17px', color: '#0f172a' }}>ETB {fmt(finance.totalIncome)}</p>
              </div>
              <span style={{ fontSize: '22px' }}>💵</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', backgroundColor: '#fef2f2', borderRadius: '12px', border: '1px solid rgba(239,68,68,0.15)' }}>
              <div>
                <p style={{ margin: 0, fontSize: '10px', fontWeight: '700', color: '#ef4444', letterSpacing: '0.5px', textTransform: 'uppercase' }}>Total Expenses</p>
                <p style={{ margin: '3px 0 0', fontWeight: '800', fontSize: '17px', color: '#0f172a' }}>ETB {fmt(finance.totalExpenses)}</p>
              </div>
              <span style={{ fontSize: '22px' }}>📉</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', backgroundColor: finance.netProfit >= 0 ? '#f0fdfa' : '#fef2f2', borderRadius: '12px', border: `1px solid ${finance.netProfit >= 0 ? 'rgba(15,118,110,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
              <div>
                <p style={{ margin: 0, fontSize: '10px', fontWeight: '700', color: finance.netProfit >= 0 ? '#0f766e' : '#ef4444', letterSpacing: '0.5px', textTransform: 'uppercase' }}>Net Profit</p>
                <p style={{ margin: '3px 0 0', fontWeight: '800', fontSize: '19px', color: finance.netProfit >= 0 ? '#0f766e' : '#ef4444' }}>ETB {fmt(finance.netProfit)}</p>
              </div>
              <span style={{ fontSize: '22px' }}>{finance.netProfit >= 0 ? '✅' : '🔴'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
              <span style={labelSmall}>Room Revenue (All-time)</span>
              <span style={{ fontWeight: '700', fontSize: '13px', color: '#8b5cf6' }}>ETB {fmt(reservations.roomRevenue)}</span>
            </div>
          </div>
        </SectionCard>

        {/* Staff */}
        <SectionCard title="Staff" subtitle="Active Team Members" iconBg="#f0fdfa" iconColor="#0f766e" icon={<PeopleIcon />}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '12px', paddingTop: '16px' }}>
            <div style={{ width: '84px', height: '84px', borderRadius: '50%', background: 'linear-gradient(135deg, #0f766e, #14b8a6)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(15,118,110,0.28)' }}>
              <span style={{ fontSize: '34px', fontWeight: '900', color: '#fff' }}>{staff.totalActive || 0}</span>
            </div>
            <div style={{ textAlign: 'center' }}>
              <p style={{ margin: 0, fontWeight: '700', fontSize: '13px', color: '#475569' }}>Active Staff Members</p>
              <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#94a3b8' }}>Across all departments</p>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 2. DASHBOARD LAYOUT (FOR ADMIN / FINANCE)
// ─────────────────────────────────────────────────────────────────────────────
const DashboardLayout = ({ activeTab, setActiveTab, userData, handleLogout }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-layout-container">
      {/* Mobile overlay — closes sidebar when tapped */}
      {sidebarOpen && (
        <div
          className="mobile-sidebar-overlay open"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        handleLogout={handleLogout}
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
      />

      <div className="main-content-container">
        <header className="app-header no-print">
          {/* Hamburger — only visible on mobile/tablet */}
          <button
            className="mobile-toggle-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            <Menu size={22} color="#334155" />
          </button>

          <div style={searchBarStyle}>
            <Search size={18} color="#64748b" />
            <input type="text" placeholder="Search records, rooms..." style={searchInputStyle} />
          </div>

          <div style={headerActionStyle}>
            <div style={{ padding: '8px', borderRadius: '10px', backgroundColor: '#f1f5f9', color: '#64748b', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(148,163,184,0.12)' }}>
              <Bell size={20} />
            </div>
            <div style={userProfileStyle}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: 'rgba(15,118,110,0.1)', color: '#0f766e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '800', fontSize: '15px' }}>
                {userData?.username ? userData.username.charAt(0).toUpperCase() : 'A'}
              </div>
              <div style={{ marginLeft: '10px', marginRight: '15px', textAlign: 'left' }}>
                <p style={{ margin: 0, fontWeight: '700', fontSize: '13px', color: '#0f172a' }}>{userData?.username || 'Admin'}</p>
                <p style={{ margin: 0, fontSize: '10px', color: '#0f766e', fontWeight: '700', letterSpacing: '0.5px' }}>{userData?.role?.toUpperCase()}</p>
              </div>
              <button onClick={handleLogout} style={logoutButtonStyle} title="Logout">
                <LogOut size={16} color="#ef4444" />
              </button>
            </div>
          </div>
        </header>

        <main className="main-body-container">
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' && (
              <motion.div key="dash" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <h1 style={pageTitle}>Admin Dashboard Overview</h1>
                <DashboardContent />
              </motion.div>
            )}
            {activeTab === 'orders'               && <OrdersManager userData={userData} />}
            {activeTab === 'categories'           && <CategoryManager />}
            {activeTab === 'menus'                && <MenuManager />}
            {activeTab === 'inventory'            && <InventoryDashboard userData={userData} handleLogout={handleLogout} />}
            {['rooms', 'reservation_booking', 'checkin_checkout', 'night_audit'].includes(activeTab) && (
              <RoomManager activeSection={activeTab} />
            )}
            {activeTab === 'bookings'  && <BookingsManager />}
            {activeTab === 'reports'   && <ReportsCenter />}
            {activeTab === 'finance'   && <FinanceDashboard />}
            {activeTab === 'tables'    && <TableManager />}
            {activeTab === 'users'     && <UserManager />}
            {activeTab === 'settings'  && <SystemSettingsManager />}
            {activeTab === 'report_police'    && <ReportsCenter initialTab="police" />}
            {activeTab === 'report_xreport'   && <ReportsCenter initialTab="xreport" />}
            {activeTab === 'report_zreport'   && <ReportsCenter initialTab="zreport" />}
            {activeTab === 'report_occupancy' && <ReportsCenter initialTab="occupancy" />}
            {activeTab === 'report_bookings'  && <ReportsCenter initialTab="bookings" />}
            {activeTab === 'report_inventory' && <ReportsCenter initialTab="inventory" />}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 3. MAIN APP COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [userData, setUserData]   = useState(null);

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      const parsed = JSON.parse(savedUser);
      setUserData(parsed);
      if (parsed.role?.toLowerCase().trim() === 'finance') setActiveTab('finance');
    }
  }, []);

  const handleLoginSuccess = (user) => {
    setUserData(user);
    const role = user.role?.toLowerCase().trim();
    if (role === 'finance') {
      setActiveTab('finance');
    } else {
      setActiveTab('dashboard');
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    delete axios.defaults.headers.common['Authorization'];
    setUserData(null);
    window.location.replace('/');
  };

  const renderDashboard = () => {
    const token = localStorage.getItem('access_token');
    const user  = userData || JSON.parse(localStorage.getItem('user') || 'null');
    if (!token || !user) return <Navigate to="/" replace />;
    const role = user.role?.toLowerCase().trim();
    switch (role) {
      case 'admin':
      case 'finance':
        return <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />;
      case 'waiter':
        return <WaiterDashboard userData={user} handleLogout={handleLogout} />;
      case 'cashier':
        return <CashierDashboard userData={user} handleLogout={handleLogout} />;
      case 'kitchen':
        return <KitchenDashboard userData={user} handleLogout={handleLogout} />;
      case 'bar':
        return <BarDashboard userData={user} handleLogout={handleLogout} />;
      case 'reception':
        return <ReceptionDashboard userData={user} handleLogout={handleLogout} />;
      case 'inventory':
        return <InventoryDashboard userData={user} handleLogout={handleLogout} />;
      case 'customer':
        return <CustomerDashboard userData={user} handleLogout={handleLogout} />;
      default:
        return <div style={{ padding: '50px', textAlign: 'center' }}><h1>Unauthorized</h1><button onClick={handleLogout}>Back to Login</button></div>;
    }
  };

  return (
    <Routes>
      <Route path="/"                  element={<AuthPage onLoginSuccess={handleLoginSuccess} />} />
      <Route path="/dashboard"         element={renderDashboard()} />
      <Route path="/customer-dashboard" element={<CustomerDashboard />} />
      <Route path="/booking/:token"    element={<PublicBookingConfirmation />} />
      <Route path="/pay/:token"        element={<CustomerPaymentPage />} />
      <Route path="*"                  element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
export default App;
