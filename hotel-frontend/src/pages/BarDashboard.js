import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Clock, Wine, LogOut } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const BarDashboard = ({ userData, handleLogout }) => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchBarOrders = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}kitchen/orders/`);
      // Filter to only Bar-station items if possible; otherwise show all active orders
      const barOrders = res.data.filter(order =>
        order.items && order.items.some(item =>
          (item.category_station || '').toLowerCase() === 'bar' ||
          (item.menu_item_name || '').toLowerCase().includes('drink') ||
          (item.menu_item_name || '').toLowerCase().includes('juice') ||
          (item.menu_item_name || '').toLowerCase().includes('beer') ||
          (item.menu_item_name || '').toLowerCase().includes('wine') ||
          (item.menu_item_name || '').toLowerCase().includes('coffee') ||
          (item.menu_item_name || '').toLowerCase().includes('tea')
        )
      );
      // If no bar-specific items found, show all active orders
      setOrders(barOrders.length > 0 ? barOrders : res.data);
      setLoading(false);
    } catch (err) {
      console.error('Bar orders fetch error:', err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBarOrders();
    const interval = setInterval(fetchBarOrders, 10000);
    return () => clearInterval(interval);
  }, [fetchBarOrders]);

  const updateStatus = async (orderId, newStatus) => {
    try {
      await axios.post(`${API_BASE}orders/${orderId}/update-status/`, { status: newStatus });
      fetchBarOrders();
    } catch (err) {
      console.error('Status update error:', err.response?.data);
      alert('Could not update order status.');
    }
  };

  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Wine size={32} color="#fff" />
          <div>
            <h1 style={{ color: '#fff', margin: 0, fontSize: '22px', fontWeight: 900 }}>BAR DISPLAY SYSTEM</h1>
            <p style={{ color: '#94a3b8', margin: 0, fontSize: '13px' }}>
              {userData?.username || 'Bar Staff'} — BAR
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={statsBadge}>Active: {orders.length}</div>
          {handleLogout && (
            <button onClick={handleLogout} style={logoutBtn} title="Logout">
              <LogOut size={18} color="#ef4444" />
            </button>
          )}
        </div>
      </header>

      <main style={{ padding: '30px' }}>
        {loading ? (
          <div style={loadingStyle}>
            <Wine size={48} color="#7c3aed" style={{ marginBottom: '15px' }} />
            <p style={{ color: '#94a3b8', fontSize: '16px' }}>Loading bar orders…</p>
          </div>
        ) : orders.length === 0 ? (
          <div style={emptyStyle}>
            <Wine size={64} color="#334155" style={{ marginBottom: '20px' }} />
            <h2 style={{ color: '#94a3b8', fontWeight: 700 }}>No Active Orders</h2>
            <p style={{ color: '#64748b' }}>Bar orders will appear here automatically.</p>
          </div>
        ) : (
          <div style={gridStyle}>
            <AnimatePresence>
              {orders.map(order => (
                <motion.div
                  key={order.id}
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  style={orderCard}
                >
                  <div style={{
                    ...cardHeader,
                    background: order.status === 'pending'
                      ? 'linear-gradient(135deg, #7c3aed, #5b21b6)'
                      : 'linear-gradient(135deg, #d97706, #b45309)',
                  }}>
                    <span style={tableLabel}>TABLE {order.table_code}</span>
                    <div style={timeStyle}>
                      <Clock size={14} />
                      <span style={{ marginLeft: '5px', fontSize: '12px' }}>
                        {order.status === 'pending' ? 'NEW ORDER' : 'PREPARING'}
                      </span>
                    </div>
                  </div>

                  <div style={itemListStyle}>
                    {order.items && order.items.map((item, idx) => (
                      <div key={idx} style={itemRow}>
                        <span style={qtyStyle}>{item.quantity}×</span>
                        <span style={nameStyle}>{item.menu_item_name}</span>
                        <span style={priceStyle}>ETB {parseFloat(item.price_at_order || 0).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>

                  <div style={footerStyle}>
                    {order.status === 'pending' ? (
                      <button
                        onClick={() => updateStatus(order.id, 'preparing')}
                        style={prepBtn}
                      >
                        START PREPARING
                      </button>
                    ) : (
                      <button
                        onClick={() => updateStatus(order.id, 'ready')}
                        style={readyBtn}
                      >
                        ✓ MARK READY
                      </button>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>
    </div>
  );
};

// Styles
const containerStyle = { minHeight: '100vh', backgroundColor: '#0f172a', paddingBottom: '50px' };
const headerStyle = {
  background: 'linear-gradient(135deg, #1e1b4b, #312e81)',
  padding: '20px 40px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  borderBottom: '3px solid #4c1d95',
};
const statsBadge = {
  backgroundColor: '#7c3aed',
  color: '#fff',
  padding: '8px 20px',
  borderRadius: '30px',
  fontWeight: 'bold',
  fontSize: '16px',
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
const loadingStyle = { textAlign: 'center', paddingTop: '100px' };
const emptyStyle = { textAlign: 'center', paddingTop: '100px' };
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '25px' };
const orderCard = {
  backgroundColor: '#fff',
  borderRadius: '16px',
  overflow: 'hidden',
  boxShadow: '0 10px 15px -3px rgba(0,0,0,0.3)',
  display: 'flex',
  flexDirection: 'column',
};
const cardHeader = { padding: '15px 18px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const tableLabel = { fontSize: '20px', fontWeight: 900 };
const timeStyle = { display: 'flex', alignItems: 'center', opacity: 0.9 };
const itemListStyle = { padding: '18px', flex: 1 };
const itemRow = { display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' };
const qtyStyle = { color: '#7c3aed', fontWeight: 800, minWidth: '30px', fontSize: '16px' };
const nameStyle = { color: '#1e293b', fontWeight: 700, flex: 1, fontSize: '15px' };
const priceStyle = { color: '#64748b', fontSize: '13px' };
const footerStyle = { padding: '15px' };
const prepBtn = { width: '100%', padding: '13px', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: 800, cursor: 'pointer', fontSize: '14px' };
const readyBtn = { width: '100%', padding: '13px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: 800, cursor: 'pointer', fontSize: '14px' };

export default BarDashboard;
