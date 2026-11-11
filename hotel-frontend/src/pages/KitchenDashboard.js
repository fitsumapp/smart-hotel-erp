import { apiErrorMessage } from '../apiClient';
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Clock, ChefHat, LogOut, AlertTriangle, CheckCircle, Play } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

// Synthesized audio chime using Web Audio API (zero external assets required)
const playChime = () => {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (e) {
    // AudioContext might require initial user gesture; safe to ignore
  }
};

const formatElapsed = (seconds) => {
  if (seconds < 0) seconds = 0;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hrs}h ${remMins}m`;
  }
  return `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
};

const KitchenDashboard = ({ userData, handleLogout }) => {
  const [orders, setOrders] = useState([]);
  const [updatingId, setUpdatingId] = useState(null);
  const [updatingItemId, setUpdatingItemId] = useState(null);
  const [settings, setSettings] = useState({
    kds_prep_target_minutes: 15,
    kds_delay_warning_minutes: 20,
  });
  const [now, setNow] = useState(Date.now());

  const prevOrderIdsRef = useRef(new Set());
  const initialLoadRef = useRef(true);

  // 1-second live ticker for elapsed timers
  useEffect(() => {
    const ticker = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(ticker);
  }, []);

  // Fetch operational settings on mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const res = await axios.get(`${API_BASE}settings/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = Array.isArray(res.data) ? res.data[0] : res.data;
        if (data) {
          setSettings({
            kds_prep_target_minutes: data.kds_prep_target_minutes ?? 15,
            kds_delay_warning_minutes: data.kds_delay_warning_minutes ?? 20,
          });
        }
      } catch (err) {
        console.error('Failed to load settings in KDS:', err);
      }
    };
    fetchSettings();
  }, []);

  // Polling kitchen orders every 10 seconds
  useEffect(() => {
    fetchKitchenOrders();
    const interval = setInterval(fetchKitchenOrders, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchKitchenOrders = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.get(`${API_BASE}kitchen/orders/?station=Kitchen&_cb=${new Date().getTime()}`, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });
      // Only keep orders with Kitchen items, and only render food items in each ticket
      const kitchenOrders = (res.data || [])
        .map(order => ({
          ...order,
          items: (order.items || []).filter(item => {
            const st = (item.station || item.category_station || '').toLowerCase();
            if (st === 'kitchen') return true;
            if (st === 'bar') return false;
            const cat = (item.category_name || '').toLowerCase();
            return !/drink|beverage|juice|beer|wine|bar|cocktail|soda|coffee|tea|መጠጥ|ቢራ|ጭማቂ/i.test(cat);
          })
        }))
        .filter(order => order.items.length > 0);

      // Play audio chime if new order detected
      const currentIds = new Set(kitchenOrders.map(o => o.id));
      if (!initialLoadRef.current) {
        const hasNewOrder = kitchenOrders.some(o => !prevOrderIdsRef.current.has(o.id));
        if (hasNewOrder) {
          playChime();
        }
      } else {
        initialLoadRef.current = false;
      }
      prevOrderIdsRef.current = currentIds;

      setOrders(kitchenOrders);
    } catch (err) {
      console.error('Orders fetch failed', err);
    }
  };

  // Station batch update (e.g. START ALL COOKING or MARK ALL READY)
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
        { status: newStatus, station: 'Kitchen' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchKitchenOrders();
    } catch (err) {
      console.error('Status update failed', err);
      const status = err?.response?.status;
      const msg = apiErrorMessage(err, 'Failed to update order.');
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

  // Individual item status update
  const updateItemStatus = async (orderId, itemId, newStatus) => {
    if (updatingItemId === itemId) return;
    setUpdatingItemId(itemId);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        alert('Session expired. Please log in again.');
        setUpdatingItemId(null);
        return;
      }
      await axios.post(
        `${API_BASE}orders/${orderId}/update-status/`,
        { status: newStatus, item_id: itemId, station: 'Kitchen' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchKitchenOrders();
    } catch (err) {
      console.error('Item status update failed', err);
      const msg = err?.response?.data?.error || err?.response?.data?.detail || err?.message || 'Update failed';
      alert(`Could not update item: ${msg}`);
    } finally {
      setUpdatingItemId(null);
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
            orders.map(order => {
              // Calculate ticket timing metrics
              const startTime = new Date(order.received_at || order.created_at || now).getTime();
              const elapsedSeconds = Math.max(0, Math.floor((now - startTime) / 1000));
              const elapsedMinutes = Math.floor(elapsedSeconds / 60);

              const targetMins = settings.kds_prep_target_minutes || 15;
              const delayMins = settings.kds_delay_warning_minutes || 20;

              const isCritical = elapsedMinutes >= delayMins;
              const isOverdue = !isCritical && elapsedMinutes >= targetMins;

              // Items breakdown for station
              const items = order.items || [];
              const allReady = items.length > 0 && items.every(it => it.status === 'ready');
              const anyPreparing = items.some(it => it.status === 'preparing');
              const allPending = items.every(it => it.status === 'pending');

              // Header styling based on urgency and status
              let headerBg = '#ef4444';
              if (isCritical) {
                headerBg = 'linear-gradient(135deg, #b91c1c, #7f1d1d)';
              } else if (isOverdue) {
                headerBg = 'linear-gradient(135deg, #d97706, #92400e)';
              } else if (order.status === 'preparing' || anyPreparing) {
                headerBg = '#f59e0b';
              } else if (allReady) {
                headerBg = '#10b981';
              }

              return (
                <motion.div
                  key={order.id}
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  style={{
                    ...orderCard,
                    border: isCritical ? '3px solid #ef4444' : isOverdue ? '2px solid #f59e0b' : '1px solid transparent',
                    boxShadow: isCritical ? '0 0 20px rgba(239,68,68,0.35)' : '0 10px 15px -3px rgba(0,0,0,0.3)',
                  }}
                >
                  <div style={{ ...cardHeader, background: headerBg }}>
                    <div>
                      <span style={tableNum}>TABLE {order.table_code}</span>
                      <div style={{ fontSize: '11px', opacity: 0.85, fontWeight: '600' }}>
                        #{order.id} {order.waiter_name ? `• ${order.waiter_name}` : ''}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                      <div style={timeAgo}>
                        <Clock size={14} />
                        <span style={{ fontWeight: '800', fontVariantNumeric: 'tabular-nums' }}>
                          {formatElapsed(elapsedSeconds)}
                        </span>
                      </div>

                      {isCritical && (
                        <span style={criticalBadge}>
                          <AlertTriangle size={11} style={{ marginRight: '3px' }} />
                          +{elapsedMinutes - delayMins}m CRITICAL
                        </span>
                      )}
                      {isOverdue && (
                        <span style={overdueBadge}>
                          ⚠️ +{elapsedMinutes - targetMins}m OVERDUE
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={itemList}>
                    {items.map((item) => {
                      const itemPrepSec = item.preparation_started_at
                        ? Math.max(0, Math.floor((now - new Date(item.preparation_started_at).getTime()) / 1000))
                        : null;

                      return (
                        <div key={item.id} style={{ ...foodItem, flexDirection: 'column', alignItems: 'flex-start' }}>
                          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', width: '100%' }}>
                            <span style={itemQty}>{item.quantity}x</span>
                            <div style={{ flex: 1 }}>
                              <div style={itemName}>{item.menu_item_name}</div>
                              {itemPrepSec !== null && item.status === 'preparing' && (
                                <div style={{ fontSize: '11px', color: '#b45309', fontWeight: '700' }}>
                                  Cooking: {formatElapsed(itemPrepSec)}
                                </div>
                              )}
                            </div>

                            {/* Item status badge */}
                            <span style={{
                              fontSize: '11px',
                              fontWeight: '700',
                              padding: '2px 8px',
                              borderRadius: '10px',
                              backgroundColor: item.status === 'ready' ? '#dcfce7' : item.status === 'preparing' ? '#fef3c7' : '#fee2e2',
                              color: item.status === 'ready' ? '#166534' : item.status === 'preparing' ? '#b45309' : '#991b1b',
                              textTransform: 'uppercase'
                            }}>
                              {item.status}
                            </span>

                            {/* Item-level action button */}
                            {item.status === 'pending' && (
                              <button
                                onClick={() => updateItemStatus(order.id, item.id, 'preparing')}
                                disabled={updatingItemId === item.id}
                                style={itemActionStartBtn}
                                title="Start cooking this item"
                              >
                                {updatingItemId === item.id ? '...' : <><Play size={11} style={{ marginRight: '2px' }} /> Cook</>}
                              </button>
                            )}
                            {item.status === 'preparing' && (
                              <button
                                onClick={() => updateItemStatus(order.id, item.id, 'ready')}
                                disabled={updatingItemId === item.id}
                                style={itemActionReadyBtn}
                                title="Mark this item ready"
                              >
                                {updatingItemId === item.id ? '...' : <><CheckCircle size={11} style={{ marginRight: '2px' }} /> Ready</>}
                              </button>
                            )}
                          </div>

                          {item.notes ? (
                            <div style={{
                              fontSize: '13px',
                              color: '#b45309',
                              backgroundColor: '#fef3c7',
                              padding: '4px 10px',
                              borderRadius: '6px',
                              marginTop: '6px',
                              marginLeft: '35px',
                              fontWeight: '600',
                              borderLeft: '3px solid #f59e0b'
                            }}>
                              📝 Note: {item.notes}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>

                  {/* Card Footer: Station batch actions */}
                  <div style={cardFooter}>
                    {allReady ? (
                      <div style={allReadyNotice}>
                        <CheckCircle size={18} />
                        ALL ITEMS READY FOR WAITER
                      </div>
                    ) : allPending ? (
                      <button
                        onClick={() => updateStatus(order.id, 'preparing')}
                        style={{
                          ...prepBtn,
                          opacity: updatingId === order.id ? 0.6 : 1,
                          cursor: updatingId === order.id ? 'wait' : 'pointer',
                        }}
                        disabled={updatingId === order.id}
                      >
                        {updatingId === order.id ? '⏳ STARTING...' : 'START COOKING ALL'}
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
                        {updatingId === order.id ? '⏳ UPDATING...' : 'MARK ALL READY ✓'}
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })
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
const orderGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '25px', padding: '30px' };
const emptyState = { gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' };
const orderCard = { backgroundColor: '#fff', borderRadius: '15px', overflow: 'hidden', display: 'flex', flexDirection: 'column', transition: 'box-shadow 0.3s' };
const cardHeader = { padding: '15px 18px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const tableNum = { fontSize: '20px', fontWeight: '900' };
const timeAgo = { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '15px', fontWeight: '700' };
const itemList = { padding: '18px', flex: 1 };
const foodItem = { display: 'flex', gap: '10px', fontSize: '16px', fontWeight: '700', marginBottom: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' };
const itemQty = { color: '#0ea5e9', minWidth: '28px', fontWeight: '800' };
const itemName = { color: '#1e293b', fontWeight: '700', lineHeight: 1.2 };
const cardFooter = { padding: '15px', backgroundColor: '#fafafa', borderTop: '1px solid #f1f5f9' };
const prepBtn = { width: '100%', padding: '14px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer', fontSize: '15px' };
const readyBtn = { width: '100%', padding: '14px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer', fontSize: '15px' };

const itemActionStartBtn = {
  display: 'flex',
  alignItems: 'center',
  padding: '4px 10px',
  backgroundColor: '#0284c7',
  color: '#fff',
  border: 'none',
  borderRadius: '6px',
  fontSize: '12px',
  fontWeight: '700',
  cursor: 'pointer'
};

const itemActionReadyBtn = {
  display: 'flex',
  alignItems: 'center',
  padding: '4px 10px',
  backgroundColor: '#10b981',
  color: '#fff',
  border: 'none',
  borderRadius: '6px',
  fontSize: '12px',
  fontWeight: '700',
  cursor: 'pointer'
};

const criticalBadge = {
  display: 'inline-flex',
  alignItems: 'center',
  backgroundColor: '#fee2e2',
  color: '#991b1b',
  fontSize: '10px',
  fontWeight: '800',
  padding: '2px 6px',
  borderRadius: '6px',
  letterSpacing: '0.5px'
};

const overdueBadge = {
  display: 'inline-flex',
  alignItems: 'center',
  backgroundColor: '#fef3c7',
  color: '#b45309',
  fontSize: '10px',
  fontWeight: '800',
  padding: '2px 6px',
  borderRadius: '6px',
  letterSpacing: '0.5px'
};

const allReadyNotice = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '8px',
  padding: '12px',
  backgroundColor: '#dcfce7',
  color: '#166534',
  fontWeight: '800',
  borderRadius: '10px',
  fontSize: '13px'
};

export default KitchenDashboard;
