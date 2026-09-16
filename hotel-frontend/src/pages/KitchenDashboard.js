import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, ChefHat, LogOut } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const KitchenDashboard = ({ userData, handleLogout }) => {
  const [orders, setOrders] = useState([]);
  const [updatingId, setUpdatingId] = useState(null);

  useEffect(() => {
    fetchKitchenOrders();
    const interval = setInterval(fetchKitchenOrders, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchKitchenOrders = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.get(`${API_BASE}kitchen/orders/?_cb=${new Date().getTime()}`, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });
      setOrders(res.data);
    } catch (err) {
      console.error('Orders fetch failed', err);
    }
  };

  const updateStatus = async (orderId, newStatus) => {
    if (updatingId === orderId) return; // prevent double-click
    setUpdatingId(orderId);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        alert('Session expired. Please log in again.');
        setUpdatingId(null);
        return;
      }
      await axios.post(
        `${API_BASE}orders/${orderId}/update-status/`,
        { status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchKitchenOrders();
    } catch (err) {
      console.error('Status update failed', err);
      const status = err?.response?.status;
      const msg = err?.response?.data?.error || err?.response?.data?.detail || err?.message || 'Unknown error';
      if (status === 401 || status === 403) {
        alert(`Authentication error (${status}): Please log out and log in again.`);
      } else if (status === 404) {
        alert('Order not found. It may have been removed already.');
        fetchKitchenOrders();
      } else {
        alert(`Could not update order status.\nError ${status || ''}: ${msg}`);
      }
    } finally {
      setUpdatingId(null);
    }
  };

  const doLogout = () => {
    localStorage.clear();
    delete axios.defaults.headers.common['Authorization'];
    if (handleLogout) handleLogout();
    else window.location.replace('/');
  };

  return (
    <div style={kdsContainer}>
      <header style={kdsHeader}>
        {/* Left: Logo + Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <ChefHat size={32} color="#fff" />
          <div>
            <h1 style={{ color: '#fff', margin: 0, fontSize: '22px', fontWeight: '900', letterSpacing: '1px' }}>
              KITCHEN DISPLAY SYSTEM
            </h1>
            {userData?.username && (
              <p style={{ color: '#94a3b8', margin: 0, fontSize: '12px', fontWeight: '600' }}>
                Logged in as: {userData.username}
              </p>
            )}
          </div>
        </div>

        {/* Right: Active Orders Badge + Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={statsBadge}>Active Orders: {orders.length}</div>
          <button onClick={doLogout} style={logoutBtn} title="Logout">
            <LogOut size={18} style={{ marginRight: '8px' }} />
            Logout
          </button>
        </div>
      </header>

      <main style={orderGrid}>
        <AnimatePresence>
          {orders.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={emptyState}
            >
              <ChefHat size={64} color="#334155" />
              <p style={{ color: '#475569', fontSize: '20px', fontWeight: '700', marginTop: '20px' }}>
                No pending orders
              </p>
              <p style={{ color: '#64748b', fontSize: '14px' }}>Kitchen is all caught up!</p>
            </motion.div>
          ) : (
            orders.map(order => (
              <motion.div
                key={order.id}
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                style={orderCard}
              >
                <div style={{ ...cardHeader, backgroundColor: order.status === 'pending' ? '#ef4444' : '#f59e0b' }}>
                  <span style={tableNum}>TABLE {order.table_code}</span>
                  <div style={timeAgo}>
                    <Clock size={14} /> <span>Just now</span>
                  </div>
                </div>

                <div style={itemList}>
                  {order.items.map((item, idx) => (
                    <div key={idx} style={foodItem}>
                      <span style={itemQty}>{item.quantity}x</span>
                      <span style={itemName}>{item.menu_item_name}</span>
                    </div>
                  ))}
                </div>

                <div style={cardFooter}>
                  {order.status === 'pending' ? (
                    <button
                      onClick={() => updateStatus(order.id, 'preparing')}
                      style={{
                        ...prepBtn,
                        opacity: updatingId === order.id ? 0.6 : 1,
                        cursor: updatingId === order.id ? 'wait' : 'pointer',
                      }}
                      disabled={updatingId === order.id}
                    >
                      {updatingId === order.id ? '⏳ STARTING...' : 'START COOKING'}
                    </button>
                  ) : (
                    <button
                      onClick={() => updateStatus(order.id, 'ready')}
                      style={{
                        ...readyBtn,
                        opacity: updatingId === order.id ? 0.6 : 1,
                        cursor: updatingId === order.id ? 'wait' : 'pointer',
                      }}
                      disabled={updatingId === order.id}
                    >
                      {updatingId === order.id ? '⏳ UPDATING...' : 'MARK AS READY ✓'}
                    </button>
                  )}
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

// --- Styles ---
const kdsContainer = { minHeight: '100vh', backgroundColor: '#0f172a', paddingBottom: '50px' };
const kdsHeader = { backgroundColor: '#1e293b', padding: '20px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '4px solid #334155' };
const statsBadge = { backgroundColor: '#0ea5e9', color: '#fff', padding: '10px 20px', borderRadius: '30px', fontWeight: 'bold', fontSize: '16px' };
const logoutBtn = { display: 'flex', alignItems: 'center', backgroundColor: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)', color: '#ef4444', padding: '10px 18px', borderRadius: '12px', fontWeight: '700', fontSize: '14px', cursor: 'pointer', transition: 'all 0.2s' };
const orderGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '25px', padding: '30px' };
const emptyState = { gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' };
const orderCard = { backgroundColor: '#fff', borderRadius: '15px', overflow: 'hidden', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.3)', display: 'flex', flexDirection: 'column' };
const cardHeader = { padding: '15px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const tableNum = { fontSize: '22px', fontWeight: '900' };
const timeAgo = { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px', opacity: 0.9 };
const itemList = { padding: '20px', flex: 1 };
const foodItem = { display: 'flex', gap: '15px', fontSize: '18px', fontWeight: '700', marginBottom: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' };
const itemQty = { color: '#0ea5e9', minWidth: '30px' };
const itemName = { color: '#1e293b' };
const cardFooter = { padding: '15px' };
const prepBtn = { width: '100%', padding: '15px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer', fontSize: '15px' };
const readyBtn = { width: '100%', padding: '15px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer', fontSize: '15px' };

export default KitchenDashboard;