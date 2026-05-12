import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Package, LogOut, TrendingUp, AlertTriangle, CheckCircle, RefreshCw
} from 'lucide-react';
import { motion } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const InventoryDashboard = ({ userData, handleLogout }) => {
  const [menuItems, setMenuItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('menu');

  const fetchData = useCallback(async () => {
    try {
      const [itemsRes, catsRes] = await Promise.all([
        axios.get(`${API_BASE}menu-items/`),
        axios.get(`${API_BASE}categories/`),
      ]);
      setMenuItems(itemsRes.data || []);
      setCategories(catsRes.data || []);
    } catch (err) {
      console.error('Inventory fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const availableItems = menuItems.filter(i => i.is_available);
  const unavailableItems = menuItems.filter(i => !i.is_available);

  const toggleAvailability = async (item) => {
    try {
      const formData = new FormData();
      formData.append('is_available', !item.is_available);
      await axios.patch(`${API_BASE}menu-items/${item.id}/`, { is_available: !item.is_available });
      fetchData();
    } catch (err) {
      console.error('Toggle error:', err.response?.data);
      alert('Could not update item availability.');
    }
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div style={loadingStyle}>
          <Package size={48} color="#0ea5e9" style={{ marginBottom: '15px' }} />
          <p style={{ color: '#94a3b8' }}>Loading inventory data…</p>
        </div>
      );
    }

    if (activeTab === 'menu') {
      return (
        <div>
          {/* Summary cards */}
          <div style={summaryGrid}>
            <SummaryCard
              icon={<Package size={22} color="#0ea5e9" />}
              label="Total Items"
              value={menuItems.length}
              color="#0ea5e9"
            />
            <SummaryCard
              icon={<CheckCircle size={22} color="#10b981" />}
              label="Available"
              value={availableItems.length}
              color="#10b981"
            />
            <SummaryCard
              icon={<AlertTriangle size={22} color="#ef4444" />}
              label="Unavailable"
              value={unavailableItems.length}
              color="#ef4444"
            />
            <SummaryCard
              icon={<TrendingUp size={22} color="#f59e0b" />}
              label="Categories"
              value={categories.length}
              color="#f59e0b"
            />
          </div>

          {/* Items table */}
          <div style={tableCard}>
            <div style={tableCardHeader}>
              <h3 style={sectionTitle}>Menu Item Availability</h3>
              <button onClick={fetchData} style={refreshBtn}>
                <RefreshCw size={14} style={{ marginRight: '6px' }} /> Refresh
              </button>
            </div>
            <table style={tableStyle}>
              <thead>
                <tr style={theadRow}>
                  <th style={th}>Item Name</th>
                  <th style={th}>Category</th>
                  <th style={th}>Price (ETB)</th>
                  <th style={th}>Status</th>
                  <th style={th}>Action</th>
                </tr>
              </thead>
              <tbody>
                {menuItems.map(item => (
                  <motion.tr
                    key={item.id}
                    style={{ ...tdRow, opacity: item.is_available ? 1 : 0.55 }}
                    whileHover={{ backgroundColor: '#1e293b' }}
                  >
                    <td style={td}>{item.name}</td>
                    <td style={td}>{item.category_name || '—'}</td>
                    <td style={td}>{parseFloat(item.price).toFixed(2)}</td>
                    <td style={td}>
                      <span style={{
                        ...statusPill,
                        backgroundColor: item.is_available ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                        color: item.is_available ? '#10b981' : '#ef4444',
                        border: `1px solid ${item.is_available ? '#10b981' : '#ef4444'}`,
                      }}>
                        {item.is_available ? '✓ Available' : '✗ Unavailable'}
                      </span>
                    </td>
                    <td style={td}>
                      <button
                        onClick={() => toggleAvailability(item)}
                        style={{
                          ...toggleBtn,
                          backgroundColor: item.is_available ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
                          color: item.is_available ? '#ef4444' : '#10b981',
                          border: `1px solid ${item.is_available ? '#ef4444' : '#10b981'}`,
                        }}
                      >
                        {item.is_available ? 'Mark Unavailable' : 'Mark Available'}
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    // Categories tab
    return (
      <div style={tableCard}>
        <div style={tableCardHeader}>
          <h3 style={sectionTitle}>Categories</h3>
        </div>
        <table style={tableStyle}>
          <thead>
            <tr style={theadRow}>
              <th style={th}>Category Name</th>
              <th style={th}>Station</th>
              <th style={th}>Items Count</th>
            </tr>
          </thead>
          <tbody>
            {categories.map(cat => {
              const count = menuItems.filter(i => i.category === cat.id).length;
              return (
                <tr key={cat.id} style={tdRow}>
                  <td style={td}>{cat.name}</td>
                  <td style={td}>
                    <span style={{
                      ...statusPill,
                      backgroundColor: cat.station === 'Bar' ? 'rgba(124,58,237,0.15)' : 'rgba(14,165,233,0.15)',
                      color: cat.station === 'Bar' ? '#7c3aed' : '#0ea5e9',
                      border: `1px solid ${cat.station === 'Bar' ? '#7c3aed' : '#0ea5e9'}`,
                    }}>
                      {cat.station}
                    </span>
                  </td>
                  <td style={td}>{count} items</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Package size={32} color="#0ea5e9" />
          <div>
            <h1 style={{ color: '#fff', margin: 0, fontSize: '22px', fontWeight: 900 }}>INVENTORY CONTROL</h1>
            <p style={{ color: '#94a3b8', margin: 0, fontSize: '13px' }}>
              {userData?.username || 'Inventory Staff'} — INVENTORY
            </p>
          </div>
        </div>
        {handleLogout && (
          <button onClick={handleLogout} style={logoutBtn} title="Logout">
            <LogOut size={18} color="#ef4444" />
          </button>
        )}
      </header>

      <div style={tabBar}>
        {['menu', 'categories'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              ...tabBtn,
              borderBottom: activeTab === tab ? '3px solid #0ea5e9' : '3px solid transparent',
              color: activeTab === tab ? '#0ea5e9' : '#94a3b8',
            }}
          >
            {tab === 'menu' ? 'Menu Items' : 'Categories'}
          </button>
        ))}
      </div>

      <main style={{ padding: '30px' }}>
        {renderContent()}
      </main>
    </div>
  );
};

const SummaryCard = ({ icon, label, value, color }) => (
  <motion.div whileHover={{ y: -4 }} style={summaryCard}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', fontWeight: 600, letterSpacing: '0.5px' }}>
          {label.toUpperCase()}
        </p>
        <h2 style={{ margin: '8px 0 0', fontSize: '32px', fontWeight: 900, color: '#fff' }}>{value}</h2>
      </div>
      <div style={{ padding: '10px', borderRadius: '12px', backgroundColor: 'rgba(255,255,255,0.05)' }}>
        {icon}
      </div>
    </div>
    <div style={{ marginTop: '15px', height: '3px', backgroundColor: '#1f2937', borderRadius: '3px' }}>
      <div style={{ height: '100%', width: '60%', backgroundColor: color, borderRadius: '3px' }} />
    </div>
  </motion.div>
);

// Styles
const containerStyle = { minHeight: '100vh', backgroundColor: '#0f172a', paddingBottom: '50px' };
const headerStyle = {
  background: 'linear-gradient(135deg, #0c1a2e, #0f2944)',
  padding: '20px 40px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  borderBottom: '3px solid #0ea5e9',
};
const logoutBtn = {
  background: 'transparent',
  border: '1px solid #334155',
  borderRadius: '8px',
  padding: '6px 10px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
};
const tabBar = { display: 'flex', gap: '0', padding: '0 40px', backgroundColor: '#111827', borderBottom: '1px solid #1f2937' };
const tabBtn = {
  padding: '14px 24px',
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontWeight: 700,
  fontSize: '13px',
  letterSpacing: '0.5px',
  transition: 'all 0.2s',
};
const summaryGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '25px' };
const summaryCard = { backgroundColor: '#111827', padding: '22px', borderRadius: '20px', border: '1px solid #1f2937' };
const loadingStyle = { textAlign: 'center', paddingTop: '100px' };
const tableCard = { backgroundColor: '#111827', borderRadius: '20px', border: '1px solid #1f2937', overflow: 'hidden' };
const tableCardHeader = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 25px', borderBottom: '1px solid #1f2937' };
const sectionTitle = { margin: 0, color: '#fff', fontSize: '16px', fontWeight: 700 };
const refreshBtn = { display: 'flex', alignItems: 'center', backgroundColor: '#1f2937', color: '#94a3b8', border: '1px solid #334155', borderRadius: '8px', padding: '7px 14px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 };
const tableStyle = { width: '100%', borderCollapse: 'collapse' };
const theadRow = { backgroundColor: '#0f172a' };
const th = { padding: '12px 20px', textAlign: 'left', fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.5px', textTransform: 'uppercase' };
const tdRow = { borderBottom: '1px solid #1f2937', transition: 'background 0.15s' };
const td = { padding: '13px 20px', fontSize: '13px', color: '#e2e8f0' };
const statusPill = { padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700 };
const toggleBtn = { padding: '5px 12px', borderRadius: '8px', fontSize: '11px', fontWeight: 700, cursor: 'pointer' };

export default InventoryDashboard;
