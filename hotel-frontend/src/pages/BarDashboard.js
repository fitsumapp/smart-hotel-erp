import { apiErrorMessage } from '../apiClient';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Clock, Wine, LogOut, AlertTriangle, CheckCircle, Sparkles } from 'lucide-react';
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
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
    osc.frequency.exponentialRampToValueAtTime(1046.50, ctx.currentTime + 0.18); // C6
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) {
    // AudioContext might require initial user gesture
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

const BarDashboard = ({ userData, handleLogout }) => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [updatingItemId, setUpdatingItemId] = useState(null);
  const [settings, setSettings] = useState({
    bar_fulfillment_target_minutes: 5,
    bar_delay_warning_minutes: 10,
  });
  const [now, setNow] = useState(Date.now());

  const prevOrderIdsRef = useRef(new Set());
  const initialLoadRef = useRef(true);

  // 1-second live ticker
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
            bar_fulfillment_target_minutes: data.bar_fulfillment_target_minutes ?? 5,
            bar_delay_warning_minutes: data.bar_delay_warning_minutes ?? 10,
          });
        }
      } catch (err) {
        console.error('Failed to load settings in BDS:', err);
      }
    };
    fetchSettings();
  }, []);

  const fetchBarOrders = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.get(`${API_BASE}kitchen/orders/?station=Bar&_cb=${new Date().getTime()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });
      // Only keep orders with Bar items, and only render drink items in each ticket
      const barOrders = (res.data || [])
        .map(order => ({
          ...order,
          items: (order.items || []).filter(item => {
            const st = (item.station || item.category_station || '').toLowerCase();
            if (st === 'bar') return true;
            if (st === 'kitchen') return false;
            const cat = (item.category_name || '').toLowerCase();
            const name = (item.menu_item_name || '').toLowerCase();
            return /drink|beverage|juice|beer|wine|bar|cocktail|soda|coffee|tea|መጠጥ|ቢራ|ጭማቂ|አረቄ/i.test(cat) ||
                   /drink|beverage|juice|beer|wine|bar|cocktail|soda|coffee|tea|መጠጥ|ቢራ|ጭማቂ|አረቄ/i.test(name);
          })
        }))
        .filter(order => order.items.length > 0);

      // Play audio chime if new order arrives
      const currentIds = new Set(barOrders.map(o => o.id));
      if (!initialLoadRef.current) {
        const hasNewOrder = barOrders.some(o => !prevOrderIdsRef.current.has(o.id));
        if (hasNewOrder) {
          playChime();
        }
      } else {
        initialLoadRef.current = false;
      }
      prevOrderIdsRef.current = currentIds;

      setOrders(barOrders);
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

  // Direct fulfillment transition to ready for Bar station
  const updateStatus = async (orderId, newStatus = 'ready') => {
    if (updatingId === orderId) return;
    setUpdatingId(orderId);
    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        `${API_BASE}orders/${orderId}/update-status/`,
        { status: newStatus, station: 'Bar' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchBarOrders();
    } catch (err) {
      console.error('Status update error:', err.response?.data);
      const msg = apiErrorMessage(err, 'Could not update order status.');
      alert(msg);
    } finally {
      setUpdatingId(null);
    }
  };

  // Direct individual item fulfillment to ready
  const updateItemStatus = async (orderId, itemId, newStatus = 'ready') => {
    if (updatingItemId === itemId) return;
    setUpdatingItemId(itemId);
    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        `${API_BASE}orders/${orderId}/update-status/`,
        { status: newStatus, item_id: itemId, station: 'Bar' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchBarOrders();
    } catch (err) {
      console.error('Item status update error:', err.response?.data);
      const msg = apiErrorMessage(err, 'Could not update item status.');
      alert(msg);
    } finally {
      setUpdatingItemId(null);
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
              {userData?.username || 'Bar Staff'} — Direct Fulfillment
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={statsBadge}>Active Orders: {orders.length}</div>
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
            <h2 style={{ color: '#94a3b8', fontWeight: 700 }}>No Active Bar Orders</h2>
            <p style={{ color: '#64748b' }}>Beverage orders will appear here automatically.</p>
          </div>
        ) : (
          <div style={gridStyle}>
            <AnimatePresence>
              {orders.map(order => {
                // Calculate timing metrics
                const startTime = new Date(order.received_at || order.created_at || now).getTime();
                const elapsedSeconds = Math.max(0, Math.floor((now - startTime) / 1000));
                const elapsedMinutes = Math.floor(elapsedSeconds / 60);

                const targetMins = settings.bar_fulfillment_target_minutes || 5;
                const delayMins = settings.bar_delay_warning_minutes || 10;

                const isCritical = elapsedMinutes >= delayMins;
                const isOverdue = !isCritical && elapsedMinutes >= targetMins;

                const items = order.items || [];
                const allReady = items.length > 0 && items.every(it => it.status === 'ready');

                // Header gradient based on urgency
                let headerBackground = 'linear-gradient(135deg, #7c3aed, #5b21b6)';
                if (isCritical) {
                  headerBackground = 'linear-gradient(135deg, #b91c1c, #7f1d1d)';
                } else if (isOverdue) {
                  headerBackground = 'linear-gradient(135deg, #d97706, #92400e)';
                } else if (allReady) {
                  headerBackground = 'linear-gradient(135deg, #059669, #047857)';
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
                    <div style={{ ...cardHeader, background: headerBackground }}>
                      <div>
                        <span style={tableLabel}>TABLE {order.table_code}</span>
                        <div style={{ fontSize: '11px', opacity: 0.85, fontWeight: '600' }}>
                          #{order.id} {order.waiter_name ? `• ${order.waiter_name}` : ''}
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                        <div style={timeStyle}>
                          <Clock size={14} />
                          <span style={{ marginLeft: '5px', fontSize: '14px', fontWeight: '800', fontVariantNumeric: 'tabular-nums' }}>
                            {formatElapsed(elapsedSeconds)}
                          </span>
                        </div>

                        {isCritical && (
                          <span style={criticalBadge}>
                            <AlertTriangle size={11} style={{ marginRight: '3px' }} />
                            +{elapsedMinutes - delayMins}m DELAYED
                          </span>
                        )}
                        {isOverdue && (
                          <span style={overdueBadge}>
                            ⚠️ +{elapsedMinutes - targetMins}m OVER TARGET
                          </span>
                        )}
                      </div>
                    </div>

                    <div style={itemListStyle}>
                      {items.map((item) => (
                        <div key={item.id} style={{ ...itemRow, flexDirection: 'column', alignItems: 'stretch' }}>
                          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', width: '100%' }}>
                            <span style={qtyStyle}>{item.quantity}×</span>
                            <span style={nameStyle}>{item.menu_item_name}</span>

                            {/* Status badge */}
                            <span style={{
                              fontSize: '11px',
                              fontWeight: '700',
                              padding: '2px 8px',
                              borderRadius: '10px',
                              backgroundColor: item.status === 'ready' ? '#dcfce7' : '#f3e8ff',
                              color: item.status === 'ready' ? '#166534' : '#6b21a8',
                              textTransform: 'uppercase'
                            }}>
                              {item.status}
                            </span>

                            {/* Direct Fulfillment Action Button for item */}
                            {item.status !== 'ready' ? (
                              <button
                                onClick={() => updateItemStatus(order.id, item.id, 'ready')}
                                disabled={updatingItemId === item.id}
                                style={barItemReadyBtn}
                                title="Mark drink ready"
                              >
                                {updatingItemId === item.id ? '...' : <><CheckCircle size={11} style={{ marginRight: '2px' }} /> Ready</>}
                              </button>
                            ) : (
                              <span style={readyCheckPill}>✓</span>
                            )}
                          </div>

                          {item.notes ? (
                            <div style={{
                              fontSize: '13px',
                              color: '#6b21a8',
                              backgroundColor: '#f3e8ff',
                              padding: '4px 10px',
                              borderRadius: '6px',
                              marginTop: '6px',
                              marginLeft: '35px',
                              fontWeight: '600',
                              borderLeft: '3px solid #9333ea'
                            }}>
                              📝 Note: {item.notes}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>

                    {/* Card Footer: Station batch direct fulfillment */}
                    <div style={footerStyle}>
                      {allReady ? (
                        <div style={allReadyNotice}>
                          <CheckCircle size={18} />
                          ALL DRINKS READY FOR WAITER
                        </div>
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
                          {updatingId === order.id ? (
                            '⏳ UPDATING...'
                          ) : (
                            <>
                              <Sparkles size={16} style={{ marginRight: '6px' }} />
                              MARK ALL DRINKS READY ✓
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </motion.div>
                );
              })}
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
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '25px' };
const orderCard = {
  backgroundColor: '#fff',
  borderRadius: '16px',
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
  transition: 'box-shadow 0.3s',
};
const cardHeader = { padding: '15px 18px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const tableLabel = { fontSize: '20px', fontWeight: 900 };
const timeStyle = { display: 'flex', alignItems: 'center', opacity: 0.95 };
const itemListStyle = { padding: '18px', flex: 1 };
const itemRow = { display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' };
const qtyStyle = { color: '#7c3aed', fontWeight: 800, minWidth: '28px', fontSize: '16px' };
const nameStyle = { color: '#1e293b', fontWeight: 700, flex: 1, fontSize: '15px' };
const footerStyle = { padding: '15px', backgroundColor: '#fafafa', borderTop: '1px solid #f1f5f9' };
const readyBtn = {
  width: '100%',
  padding: '14px',
  background: 'linear-gradient(135deg, #10b981, #059669)',
  color: '#fff',
  border: 'none',
  borderRadius: '10px',
  fontWeight: 800,
  cursor: 'pointer',
  fontSize: '15px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  boxShadow: '0 4px 12px rgba(16,185,129,0.25)',
};

const barItemReadyBtn = {
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

const readyCheckPill = {
  color: '#166534',
  fontWeight: '800',
  fontSize: '14px',
  padding: '2px 6px'
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

export default BarDashboard;
