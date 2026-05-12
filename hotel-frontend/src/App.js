import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import CategoryManager from './CategoryManager';
import MenuManager from './MenuManager';
import RoomManager from './RoomManager';
import TableManager from './TableManager';
import UserManager from './UserManager';
import AuthPage from './AuthPage';
import CustomerDashboard from './pages/CustomerDashboard';
import BookingsManager from './pages/BookingsManager';
import ReportsCenter from './pages/ReportsCenter';

// አዲሱ የ Settings ማስተካከያ ኮምፖነንት
import SystemSettingsManager from './SystemSettingsManager';

// ዳሽቦርዶች
import WaiterDashboard from './pages/WaiterDashboard';
import CashierDashboard from './pages/CashierDashboard';
import KitchenDashboard from './pages/KitchenDashboard';
import BarDashboard from './pages/BarDashboard';
import ReceptionDashboard from './pages/ReceptionDashboard';
import InventoryDashboard from './pages/InventoryDashboard';
import CustomerPaymentPage from './pages/CustomerPaymentPage';
import PublicBookingConfirmation from './pages/PublicBookingConfirmation';

import {
  Bell, UserCircle, Search, DollarSign, Bed, Activity, BarChart2, TrendingUp, LogOut
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- AXIOS INTERCEPTOR ---
import { getTenantSchemaHint } from './apiConfig';

axios.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        
        // Add Tenant Schema Header automatically
        const tenantHint = getTenantSchemaHint();
        if (tenantHint) {
            config.headers['X-Tenant-Schema'] = tenantHint;
        }
        
        return config;
    },
    (error) => Promise.reject(error)
);

// --- 1. ADMIN DASHBOARD CONTENT ---
const DashboardContent = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
    <div style={statsGrid}>
      <StatCard title="Total Orders" value="1,240" color="#3b82f6" icon={<Activity size={20}/>} percentage={10} />
      <StatCard title="Revenue" value="ETB 94,200" color="#10b981" icon={<DollarSign size={20}/>} percentage={15} />
      <StatCard title="Pending Orders" value="14" color="#f59e0b" icon={<Activity size={20}/>} percentage={-5} />
      <StatCard title="Total Rooms" value="45" color="#0ff" icon={<Bed size={20}/>} percentage={12} />
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: '20px' }}>
      <div style={cardStyle}>
        <div style={cardHeader}>
           <div style={iconBox}><BarChart2 size={18} color="#0ff"/></div>
           <div><h4 style={cardTitle}>SALES METRICS</h4><small style={cardSub}>REAL-TIME PERFORMANCE</small></div>
           <span style={pillBadge}>+ 10%</span>
        </div>
        <h2 style={metricValue}>ETB 0.00</h2>
        <div style={chartPlaceholder}></div>
      </div>

      <div style={cardStyle}>
        <div style={cardHeader}>
           <div style={iconBox}><TrendingUp size={18} color="#10b981"/></div>
           <div><h4 style={cardTitle}>MARKET LEADERS</h4><small style={cardSub}>POPULAR SEGMENTS</small></div>
        </div>
        <LeaderItem name="SPICY CHICKEN BURGER" value="1.2K" progress={80} color="#0ff" />
        <LeaderItem name="DELUXE ROOMS" value="85%" progress={85} color="#10b981" />
      </div>

      <div style={cardStyle}>
        <div style={cardHeader}>
           <div style={{...iconBox, backgroundColor: '#10b981', width:'10px', height:'10px', borderRadius:'50%'}} />
           <div><h4 style={cardTitle}>OPERATIONAL FEED</h4><small style={cardSub}>LIVE UPDATES</small></div>
        </div>
        <div style={feedTabs}><span style={activeFeedTab}>PENDING</span><span style={feedTab}>READY</span></div>
        <div style={feedItem}>
           <p style={{margin: 0, fontWeight: '700', fontSize: '12px'}}>#ORDER-0033</p>
           <span style={statusPill}>pending</span>
        </div>
      </div>
    </div>
  </div>
);

const StatCard = ({ title, value, color, icon, percentage }) => (
  <motion.div whileHover={{ y: -5 }} style={statCardStyle}>
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <div><p style={cardSub}>{title.toUpperCase()}</p><h2 style={{ margin: '5px 0', fontSize: '24px' }}>{value}</h2></div>
      <div style={{...iconBox, color: color}}>{icon}</div>
    </div>
    <div style={{ color: percentage > 0 ? '#10b981' : '#ef4444', fontSize: '12px', marginTop: '10px' }}>
       {percentage > 0 ? '▲' : '▼'} {Math.abs(percentage)}% <span style={cardSub}>vs last month</span>
    </div>
  </motion.div>
);

const LeaderItem = ({ name, value, progress, color }) => (
  <div style={{ marginBottom: '15px' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
      <small style={cardSub}>{name}</small><small style={{fontWeight: '700'}}>{value}</small>
    </div>
    <div style={progressBg}><div style={{...progressFill, width: `${progress}%`, backgroundColor: color}} /></div>
  </div>
);

// --- 2. DASHBOARD LAYOUT (FOR ADMIN) ---
const DashboardLayout = ({ activeTab, setActiveTab, userData, handleLogout }) => (
  <div style={layoutStyle} className="app-layout">
    <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} handleLogout={handleLogout} className="no-print" />
    <div style={mainContentStyle} className="main-content-wrapper">
      <header style={headerStyle} className="no-print">
        <div style={searchBarStyle}><Search size={18} color="#718096" /><input type="text" placeholder="Search..." style={searchInputStyle} /></div>
        <div style={headerActionStyle}>
          <Bell size={20} color="#a0aec0" />
          <div style={userProfileStyle}>
            <UserCircle size={30} color="#0ff" />
            <div style={{ marginLeft: '10px', marginRight: '15px' }}>
              <p style={{ margin: 0, fontWeight: '600', fontSize:'14px' }}>{userData?.username || 'Admin'}</p>
              <p style={{ margin: 0, fontSize:'10px', color:'#94a3b8' }}>{userData?.role?.toUpperCase()}</p>
            </div>
            <button onClick={handleLogout} style={logoutButtonStyle} title="Logout"><LogOut size={18} color="#ef4444" /></button>
          </div>
        </div>
      </header>
      <main style={mainBodyStyle}>
        <AnimatePresence mode="wait">
          {activeTab === 'dashboard' && (
            <motion.div key="dash" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
              <h1 style={pageTitle}>Admin Dashboard Overview</h1><DashboardContent />
            </motion.div>
          )}
          {activeTab === 'categories' && <CategoryManager />}
          {activeTab === 'menus' && <MenuManager />}
          {['rooms', 'reservation_booking', 'checkin_checkout', 'night_audit'].includes(activeTab) && (
            <RoomManager activeSection={activeTab} />
          )}
          {activeTab === 'bookings' && <BookingsManager />}
          {activeTab === 'reports' && <ReportsCenter />}
          {activeTab === 'tables' && <TableManager />}
          {activeTab === 'users' && <UserManager />}
          {activeTab === 'settings' && <SystemSettingsManager />}
        </AnimatePresence>
      </main>
    </div>
  </div>
);

// --- 3. MAIN APP COMPONENT ---
function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      setUserData(JSON.parse(savedUser));
    }
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    delete axios.defaults.headers.common["Authorization"];
    setUserData(null);
    window.location.replace("/");
  };

  const renderDashboard = () => {
    const token = localStorage.getItem('access_token');
    const user = userData || JSON.parse(localStorage.getItem('user'));

    if (!token || !user) return <Navigate to="/" replace />;

    const role = user.role?.toLowerCase().trim();

    switch (role) {
      case 'admin':
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
        return <div style={{padding: '50px', textAlign: 'center', color:'#fff'}}><h1>Unauthorized</h1><button onClick={handleLogout}>Back to Login</button></div>;
    }
  };

  return (
    <Routes>
      <Route path="/" element={<AuthPage />} />
      <Route path="/dashboard" element={renderDashboard()} />
      <Route path="/customer-dashboard" element={<CustomerDashboard />} />
      <Route path="/booking/:token" element={<PublicBookingConfirmation />} />
      <Route path="/pay/:token" element={<CustomerPaymentPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// --- Styles ---
const layoutStyle = { display: 'flex', minHeight: '100vh', backgroundColor: '#0f172a', color: '#fff', fontFamily: "'Inter', sans-serif" };
const mainContentStyle = { marginLeft: '260px', flex: 1, display: 'flex', flexDirection: 'column' };
const headerStyle = { height: '70px', backgroundColor: '#111827', padding: '0 30px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1f2937', position: 'sticky', top: 0, zIndex: 10 };
const searchBarStyle = { display: 'flex', alignItems: 'center', backgroundColor: '#1f2937', padding: '8px 15px', borderRadius: '10px', width: '300px', border: '1px solid #334155' };
const searchInputStyle = { border: 'none', backgroundColor: 'transparent', marginLeft: '10px', outline: 'none', color: '#fff', fontSize: '13px' };
const headerActionStyle = { display: 'flex', alignItems: 'center', gap: '20px' };
const userProfileStyle = { display: 'flex', alignItems: 'center', paddingLeft: '20px', borderLeft: '1px solid #1f2937' };
const mainBodyStyle = { padding: '30px', flex: 1, overflowY: 'auto' };
const pageTitle = { fontSize: '24px', fontWeight: '800', marginBottom: '25px', letterSpacing: '-0.5px' };
const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' };
const statCardStyle = { backgroundColor: '#111827', padding: '20px', borderRadius: '20px', border: '1px solid #1f2937', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' };
const cardStyle = { backgroundColor: '#111827', padding: '24px', borderRadius: '24px', border: '1px solid #1f2937' };
const cardHeader = { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' };
const iconBox = { padding: '8px', borderRadius: '10px', backgroundColor: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const cardTitle = { margin: 0, fontSize: '14px', fontWeight: '800', color: '#fff' };
const cardSub = { margin: 0, fontSize: '11px', color: '#94a3b8', fontWeight: '600' };
const pillBadge = { marginLeft: 'auto', backgroundColor: 'rgba(16,185,129,0.1)', color: '#10b981', padding: '4px 8px', borderRadius: '20px', fontSize: '10px', fontWeight: '700' };
const metricValue = { fontSize: '32px', margin: '10px 0 5px 0', fontWeight: '800', color: '#fff' };
const chartPlaceholder = { height: '80px', width: '100%', marginTop: '20px', background: 'linear-gradient(180deg, rgba(0,255,255,0.1) 0%, transparent 100%)', borderRadius: '12px' };
const progressBg = { height: '6px', backgroundColor: '#1f2937', borderRadius: '10px', overflow: 'hidden' };
const progressFill = { height: '100%', borderRadius: '10px' };
const feedTabs = { display: 'flex', gap: '15px', borderBottom: '1px solid #1f2937', paddingBottom: '10px', marginBottom: '15px' };
const activeFeedTab = { fontSize: '11px', fontWeight: '800', color: '#fff', borderBottom: '2px solid #0ff', paddingBottom: '10px' };
const feedTab = { fontSize: '11px', fontWeight: '800', color: '#64748b', cursor:'pointer' };
const feedItem = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', backgroundColor: '#0f172a', borderRadius: '12px', border: '1px solid #1f2937' };
const statusPill = { backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', fontSize: '10px', padding: '2px 8px', borderRadius: '20px', fontWeight: '700', border: '1px solid #f59e0b' };
const logoutButtonStyle = { backgroundColor: 'transparent', border: '1px solid #334155', padding: '6px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', marginLeft: '10px' };

export default App;
