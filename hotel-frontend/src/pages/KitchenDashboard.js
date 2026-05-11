import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, CheckCircle, ChefHat, Bell } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL, BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const KitchenDashboard = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchKitchenOrders();
    const interval = setInterval(fetchKitchenOrders, 10000); // በየ10 ሰከንዱ አዲስ ኦርደር መኖሩን ቼክ ያደርጋል
    return () => clearInterval(interval);
  }, []);

  const fetchKitchenOrders = async () => {
  try {
    const token = localStorage.getItem('access');
    // 2. URL መንገዱ በ urls.py ካለው ጋር አንድ መሆኑን አረጋግጥ
    const res = await axios.get(`${API_BASE}kitchen/orders/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    setOrders(res.data);
    setLoading(false);
  } catch (err) {
    console.error("Orders መጫን አልተቻለም", err);
  }
};

const updateStatus = async (orderId, newStatus) => {
  try {
    const token = localStorage.getItem('access');
    // 3. እዚህም ጋር URL መንገዱን በትክክል አስተካክል
    await axios.post(`${API_BASE}orders/${orderId}/update-status/`,
      { status: newStatus },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    fetchKitchenOrders();
  } catch (err) {
    console.error("ሁኔታውን መቀየር አልተቻለም", err.response?.data);
    alert("ሁኔታውን መቀየር አልተቻለም");
  }
};

  return (
    <div style={kdsContainer}>
      <header style={kdsHeader}>
        <div style={{display: 'flex', alignItems: 'center', gap: '15px'}}>
          <ChefHat size={32} color="#fff" />
          <h1 style={{color: '#fff', margin: 0}}>KITCHEN DISPLAY SYSTEM</h1>
        </div>
        <div style={statsBadge}>Active Orders: {orders.length}</div>
      </header>

      <main style={orderGrid}>
        <AnimatePresence>
          {orders.map(order => (
            <motion.div
              key={order.id}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              style={orderCard}
            >
              <div style={{...cardHeader, backgroundColor: order.status === 'pending' ? '#ef4444' : '#f59e0b'}}>
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
                  <button onClick={() => updateStatus(order.id, 'preparing')} style={prepBtn}>START COOKING</button>
                ) : (
                  <button onClick={() => updateStatus(order.id, 'ready')} style={readyBtn}>MARK AS READY</button>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </main>
    </div>
  );
};

// --- Styles ---
const kdsContainer = { minHeight: '100vh', backgroundColor: '#0f172a', paddingBottom: '50px' };
const kdsHeader = { backgroundColor: '#1e293b', padding: '20px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '4px solid #334155' };
const statsBadge = { backgroundColor: '#0ea5e9', color: '#fff', padding: '10px 20px', borderRadius: '30px', fontWeight: 'bold', fontSize: '18px' };
const orderGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '25px', padding: '30px' };
const orderCard = { backgroundColor: '#fff', borderRadius: '15px', overflow: 'hidden', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.3)', display: 'flex', flexDirection: 'column' };
const cardHeader = { padding: '15px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const tableNum = { fontSize: '22px', fontWeight: '900' };
const timeAgo = { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px', opacity: 0.9 };
const itemList = { padding: '20px', flex: 1 };
const foodItem = { display: 'flex', gap: '15px', fontSize: '18px', fontWeight: '700', marginBottom: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' };
const itemQty = { color: '#0ea5e9', minWidth: '30px' };
const itemName = { color: '#1e293b' };
const cardFooter = { padding: '15px' };
const prepBtn = { width: '100%', padding: '15px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer' };
const readyBtn = { width: '100%', padding: '15px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '800', cursor: 'pointer' };

export default KitchenDashboard;