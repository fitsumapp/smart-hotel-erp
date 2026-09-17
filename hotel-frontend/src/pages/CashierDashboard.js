import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  BarChart3, DollarSign, Receipt, CreditCard,
  Search, Bell, CheckCircle, X, Printer, User, LayoutGrid, Menu
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;
const TABLES_API = `${API_BASE}manage/`;
const PENDING_BILLS_API = `${API_BASE}cashier/pending-bills/`;
const COMPLETED_BILLS_API = `${API_BASE}cashier/completed-bills/`;
const SETTINGS_API = `${API_BASE}settings/`;
const CASHIER_RECEIPT_API = `${API_BASE}cashier/receipt/`;
const NOTIFICATIONS_API = `${API_BASE}notifications/`;

function MetricCard({ icon, label, value, tone }) {
  const toneMap = {
    cyan: { bg: 'rgba(12, 148, 136, 0.12)', color: '#0f766e' },
    amber: { bg: 'rgba(245, 158, 11, 0.15)', color: '#b45309' },
    green: { bg: 'rgba(34, 197, 94, 0.12)', color: '#15803d' },
    rose: { bg: 'rgba(244, 63, 94, 0.12)', color: '#be123c' },
  };
  const palette = toneMap[tone] || toneMap.cyan;
  return (
    <div style={styles.metricCard}>
      <div style={{ ...styles.metricIcon, background: palette.bg, color: palette.color }}>{icon}</div>
      <div>
        <div style={styles.metricLabel}>{label}</div>
        <div style={styles.metricValue}>{value}</div>
      </div>
    </div>
  );
}

const CashierDashboard = ({ userData, handleLogout }) => {
  const [activeTab, setActiveTab] = useState('orders');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [tables, setTables] = useState([]);
  const [pendingBills, setPendingBills] = useState([]);
  const [completedBills, setCompletedBills] = useState([]);
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  // Payment method selection removed — payment is handled by Waiter
  const [autoPrintOrderId, setAutoPrintOrderId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [toastNotification, setToastNotification] = useState(null);

  const [showReceipt, setShowReceipt] = useState(false);
  const [fiscalData, setFiscalData] = useState(null);
  const [isPrinting, setIsPrinting] = useState(false);
  const receiptRef = useRef(null);
  const knownNotificationIdsRef = useRef(new Set());
  const notificationsInitializedRef = useRef(false);
  const audioContextRef = useRef(null);

  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const [filterLimit, setFilterLimit] = useState(10);

  const [serviceRate, setServiceRate] = useState(10);
  const [vatRate, setVatRate] = useState(15);
  const [discountValue] = useState(0);

  useEffect(() => {
    fetchInitialData();
    const interval = setInterval(fetchDataUpdate, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStartDate, filterEndDate, filterLimit]);

  useEffect(() => {
    if (autoPrintOrderId) {
      const orderToPrint = completedBills.find(b => b.id === autoPrintOrderId) || pendingBills.find(b => b.id === autoPrintOrderId);
      if (orderToPrint) {
        const subTotal = orderToPrint.items?.reduce((sum, item) => sum + (item.quantity * item.price_at_order), 0) || 0;
        const discount = parseFloat(discountValue || 0);
        const afterDiscount = subTotal - discount;
        const serviceCharge = afterDiscount * (serviceRate / 100);
        const vat = afterDiscount * (vatRate / 100);
        const grandTotal = afterDiscount + serviceCharge + vat;

        setFiscalData({
          ...orderToPrint,
          table_code: orderToPrint.table_code || (orderToPrint.table?.table_code ? orderToPrint.table.table_code : (orderToPrint.table ? `Table ${orderToPrint.table}` : 'N/A')),
          waiter_name: orderToPrint.waiter_name || orderToPrint.waiter_username || 'N/A',
          summary: {
             sub_total: subTotal,
             vat: vat,
             service_charge: serviceCharge,
             grand_total: orderToPrint.total_amount || grandTotal,
             tip_amount: orderToPrint.tip_amount || 0,
          },
          tin: settings?.tin_number || "0000000000",
          address: settings?.address || "Addis Ababa, Ethiopia",
          phone: settings?.phone_number || "",
          machineId: settings?.fiscal_machine_no || "FG-000000",
          fiscalNumber: "FS" + Math.floor(Math.random() * 1000000),
          dateTime: new Date().toLocaleString()
        });
        setSelectedOrder(orderToPrint);
        setShowReceipt(true);
        setAutoPrintOrderId(null);
      }
    }
  }, [autoPrintOrderId, completedBills, pendingBills, settings, discountValue, serviceRate, vatRate]);

  const fetchInitialData = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      const [resBills, resCompleted, resNotifications, resSettings, resTables] = await Promise.all([
        axios.get(PENDING_BILLS_API, { headers }),
        axios.get(`${COMPLETED_BILLS_API}?start_date=${filterStartDate}&end_date=${filterEndDate}&limit=${filterLimit}`, { headers }),
        axios.get(NOTIFICATIONS_API, { headers }),
        axios.get(SETTINGS_API, { headers }),
        axios.get(TABLES_API, { headers })
      ]);

      setPendingBills(resBills.data || []);
      setCompletedBills(resCompleted.data || []);
      syncNotifications(resNotifications.data || []);
      const settingsData = Array.isArray(resSettings.data) ? resSettings.data[0] : resSettings.data;
      setSettings(settingsData);
      setTables(resTables.data || []);
      calculateDashboardStats(resBills.data || [], resCompleted.data || []);

      if (settingsData) {
        setVatRate(settingsData.vat_enabled ? (settingsData.vat_percentage || 15) : 0);
        setServiceRate(settingsData.service_charge_enabled ? (settingsData.service_charge_percentage || 10) : 0);
      }
    } catch (err) { console.error("Initial load failed:", err); }
  };

  const fetchDataUpdate = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      const [resBills, resCompleted, resNotifications] = await Promise.all([
        axios.get(PENDING_BILLS_API, { headers }),
        axios.get(`${COMPLETED_BILLS_API}?start_date=${filterStartDate}&end_date=${filterEndDate}&limit=${filterLimit}`, { headers }),
        axios.get(NOTIFICATIONS_API, { headers }),
      ]);
      setPendingBills(resBills.data || []);
      setCompletedBills(resCompleted.data || []);
      syncNotifications(resNotifications.data || []);
      calculateDashboardStats(resBills.data || [], resCompleted.data || []);
    } catch (err) { console.error("Refresh failed:", err); }
  };

  const calculateDashboardStats = (bills, completed = []) => {
    const revenue = bills.reduce((sum, order) => sum + parseFloat(order.total_amount || 0), 0);
    const completedRevenue = completed.reduce((sum, order) => sum + parseFloat(order.total_amount || 0), 0);
    const completedTips = completed.reduce((sum, order) => sum + parseFloat(order.tip_amount || 0), 0);
    setStats({
      revenueToday: revenue,
      billsGenerated: bills.length,
      avgBillValue: bills.length > 0 ? (revenue / bills.length) : 0,
      completedCount: completed.length,
      completedRevenue,
      completedTips,
    });
  };

  const playNotificationSound = () => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioCtx();
      }
      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(880, ctx.currentTime);
      gainNode.gain.setValueAtTime(0.0001, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      oscillator.start();
      oscillator.stop(ctx.currentTime + 0.36);
    } catch (err) {
      console.error("Notification sound failed:", err);
    }
  };

  const syncNotifications = (incomingNotifications) => {
    const data = incomingNotifications || [];
    setNotifications(data);

    const currentIds = new Set(data.map(n => n.id));
    if (!notificationsInitializedRef.current) {
      knownNotificationIdsRef.current = currentIds;
      notificationsInitializedRef.current = true;
      return;
    }

    const newNotifications = data.filter(n => !knownNotificationIdsRef.current.has(n.id));
    knownNotificationIdsRef.current = currentIds;
    if (newNotifications.length > 0) {
      const topNote = newNotifications[0];
      setToastNotification(topNote);
      playNotificationSound();
      
      // Auto-trigger receipt on "Order Served" or "Order Paid" notifications
      if (topNote.message && (topNote.message.includes("Order Served") || topNote.message.includes("Order Paid - Print Receipt"))) {
        const match = topNote.message.match(/ORD-(\d+)/);
        if (match && match[1]) {
          setAutoPrintOrderId(parseInt(match[1]));
        }
      }
      setTimeout(() => setToastNotification(null), 3500);
    }
  };

  const handleClearAllNotifications = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      await axios.delete(NOTIFICATIONS_API, { headers });
      setNotifications([]);
      knownNotificationIdsRef.current = new Set();
    } catch (err) {
      alert("Unable to clear notifications.");
    }
  };

  const handleDeleteNotification = async (id) => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      await axios.delete(`${NOTIFICATIONS_API}${id}/`, { headers });
      const updated = notifications.filter(n => n.id !== id);
      setNotifications(updated);
      knownNotificationIdsRef.current = new Set(updated.map(n => n.id));
    } catch (err) {
      alert("Unable to remove notification.");
    }
  };

  const calculateFinalTotal = (order) => {
    if (!order) return { subTotal: 0, serviceCharge: 0, vat: 0, grandTotal: 0 };
    const subTotal = order.items?.reduce((sum, item) => sum + (item.quantity * item.price_at_order), 0) || 0;
    const discount = parseFloat(discountValue || 0);
    const afterDiscount = subTotal - discount;
    const serviceCharge = afterDiscount * (serviceRate / 100);
    const vat = afterDiscount * (vatRate / 100);
    const grandTotal = afterDiscount + serviceCharge + vat;
    return { subTotal, discount, serviceCharge, vat, grandTotal: grandTotal > 0 ? grandTotal : 0 };
  };

  const billSummary = calculateFinalTotal(selectedOrder);

  // --- v3.3.0 ትክክለኛው አጠቃቀም ---
  const handlePrint = () => {
    if (!receiptRef.current) return;
    const printContent = receiptRef.current.innerHTML;
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    const paperSize = settings?.printer_paper_size || '80mm';

    printWindow.document.write(`
      <html>
        <head>
          <title>Order Receipt</title>
          <style>
            @page { size: auto; margin: 0; }
            body { 
              margin: 0; 
              padding: 0; 
              background: #fff; 
              color: #000; 
              font-family: 'Courier New', Courier, monospace; 
              -webkit-print-color-adjust: exact;
            }
            * { font-family: inherit; }
            .thermal-receipt {
              width: ${paperSize};
              margin: 0;
              padding: 2mm;
              text-transform: uppercase;
              line-height: 1.2;
              font-size: 12px;
            }
            .dashed-divider {
              border-top: 1px dashed #000 !important;
              margin: 5px 0 !important;
              width: 100% !important;
            }
            .item-row {
              display: flex !important;
              justify-content: space-between !important;
              margin: 2px 0 !important;
            }
            .centered {
              text-align: center !important;
            }
            .bold {
              font-weight: bold !important;
            }
            table { width: 100% !important; border-collapse: collapse !important; }
            th { text-align: left !important; border-bottom: 1px dashed #000 !important; padding: 2px 0 !important; }
            td { padding: 2px 0 !important; }
          </style>
        </head>
        <body>
          <div class="thermal-receipt">
            ${printContent}
          </div>
          <script>
            window.onload = function() {
              window.focus();
              window.print();
              setTimeout(() => { 
                window.close();
              }, 500);
            };
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
    
    setShowReceipt(false);
    setSelectedOrder(null);
    setFiscalData(null);
    fetchDataUpdate();
  };

  // handleProcessPayment removed — Cashier no longer confirms payment

  const handlePrintNow = async () => {
    if (!fiscalData?.id) return;

    setIsPrinting(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${CASHIER_RECEIPT_API}${fiscalData.id}/`, { headers });
      const receipt = response.data || {};

      setFiscalData((prev) => ({
        ...(prev || {}),
        id: receipt.order_id ?? prev?.id,
        table_code: receipt.table_code ?? prev?.table_code,
        items: receipt.items ?? prev?.items ?? [],
        summary: {
          sub_total: Number(receipt.sub_total ?? prev?.summary?.sub_total ?? 0),
          vat: Number(receipt.vat ?? prev?.summary?.vat ?? 0),
          service_charge: Number(receipt.service_charge ?? prev?.summary?.service_charge ?? 0),
          grand_total: Number(receipt.grand_total ?? prev?.summary?.grand_total ?? 0),
          tip_amount: Number(receipt.tip_amount ?? prev?.summary?.tip_amount ?? 0),
        },
        payment_method: receipt.payment_method ?? prev?.payment_method,
        payment_reference: receipt.payment_reference ?? prev?.payment_reference,
        tin: receipt.tin_number ?? settings?.tin_number ?? prev?.tin,
        address: receipt.address ?? settings?.address ?? prev?.address,
        phone: receipt.phone_number ?? settings?.phone_number ?? prev?.phone,
        machineId: receipt.fiscal_machine_no ?? settings?.fiscal_machine_no ?? prev?.machineId,
        fiscalNumber: receipt.fiscal_number ?? prev?.fiscalNumber,
        dateTime: receipt.processed_at ? new Date(receipt.processed_at).toLocaleString() : prev?.dateTime,
      }));

      setTimeout(() => handlePrint(), 0);
    } catch (err) {
      alert("Print failed: " + (err.response?.data?.error || "Unable to fetch receipt data from backend"));
    } finally {
      setIsPrinting(false);
    }
  };

  const filteredOrders = pendingBills.filter(b =>
    b.table_code?.toLowerCase().includes(searchQuery.toLowerCase()) || String(b.id).includes(searchQuery)
  );
  const filteredCompletedOrders = completedBills.filter(b =>
    b.table_code?.toLowerCase().includes(searchQuery.toLowerCase()) || String(b.id).includes(searchQuery)
  );
  const isCompletedOrder = selectedOrder?.status === 'completed' || selectedOrder?.status === 'paid';

  return (
    <div style={styles.page}>
      <div style={styles.backgroundAuraA} />
      <div style={styles.backgroundAuraB} />

      {mobileMenuOpen && (
        <div className="role-sidebar-overlay open" onClick={() => setMobileMenuOpen(false)} />
      )}

      <div className="role-topbar">
        <div style={{ ...styles.brandBlock, flex: 1 }}>
          <div style={styles.brandIcon}>C</div>
          <div>
            <div style={styles.brandTitle}>ACRMA <span style={{ fontWeight: 400 }}>POS</span></div>
            <div style={styles.brandSub}>Cashier Control Center</div>
          </div>
        </div>

        <button className="role-hamburger" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Toggle menu">
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        <div style={styles.topActions}>
          <div style={{ position: 'relative' }}>
            <button style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative' }} onClick={() => setShowNotifications(!showNotifications)}>
              <Bell size={24} color="#0f172a" />
              {notifications.length > 0 && <span style={styles.notificationBadge}>{notifications.length}</span>}
            </button>
            {showNotifications && (
              <div style={styles.notificationPanel}>
                <div style={styles.notificationHeader}>
                  <span style={{ fontWeight: '700' }}>Notifications</span>
                  <button style={styles.clearBtn} onClick={handleClearAllNotifications}>Clear all</button>
                </div>
                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  {notifications.length > 0 ? notifications.map(note => (
                    <div key={note.id} style={styles.notificationRow}>
                      <div style={styles.notificationTextBlock}>
                        <div style={styles.notificationTitle}>{note.message}</div>
                        <div style={styles.notificationTime}>Just now</div>
                      </div>
                      <button style={styles.deleteNoteBtn} onClick={() => handleDeleteNotification(note.id)}><X size={14} /></button>
                    </div>
                  )) : (
                    <div style={{ padding: '16px', fontSize: '13px', color: '#64748b', textAlign: 'center' }}>No notifications</div>
                  )}
                </div>
              </div>
            )}
          </div>
          <div style={styles.userPill}>
            <User size={16} /> <span className="user-pill-text">{userData?.first_name || 'Cashier'}</span>
          </div>
          <button style={styles.logoutButton} onClick={handleLogout}>Logout</button>
        </div>
      </div>

      <div className="role-layout">
        <div className={`role-sidebar${mobileMenuOpen ? ' open' : ''}`}>
          <button className="role-hamburger" style={{ marginBottom: 12, alignSelf: 'flex-end' }} onClick={() => setMobileMenuOpen(false)} aria-label="Close">
            <X size={20} />
          </button>
          <div style={activeTab === 'home' ? styles.sidebarItemActive : styles.sidebarItem} onClick={() => { setActiveTab('home'); setMobileMenuOpen(false); }}>
            <BarChart3 size={18} /> System Overview
          </div>
          <div style={activeTab === 'tables' ? styles.sidebarItemActive : styles.sidebarItem} onClick={() => { setActiveTab('tables'); setMobileMenuOpen(false); }}>
            <LayoutGrid size={18} /> Tables
          </div>
          <div style={activeTab === 'orders' ? styles.sidebarItemActive : styles.sidebarItem} onClick={() => { setActiveTab('orders'); setMobileMenuOpen(false); }}>
            <Receipt size={18} /> Billing & Checkout
          </div>
          <div style={activeTab === 'tips' ? styles.sidebarItemActive : styles.sidebarItem} onClick={() => { setActiveTab('tips'); setMobileMenuOpen(false); }}>
            <CreditCard size={18} /> Tips History
          </div>

          <div style={{ flex: 1 }} />
        </div>

        <main style={styles.main}>


          <AnimatePresence mode="wait">
            {activeTab === 'home' && (
              <motion.div key="home" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={styles.sectionHeaderRow}>
                  <div>
                    <div style={styles.sectionKicker}>OVERVIEW</div>
                    <h1 style={styles.sectionTitle}>System Analytics</h1>
                  </div>
                </div>

                <div style={{ ...styles.metricGrid, marginTop: '20px' }}>
                  <MetricCard icon={<Receipt size={24} />} label="Unpaid Bills" value={pendingBills.length} tone="rose" />
                  <MetricCard icon={<DollarSign size={24} />} label="Hotel Revenue" value={`${settings?.currency_symbol || 'ETB'} ${(stats?.completedRevenue || 0).toFixed(2)}`} tone="green" />
                  <MetricCard icon={<CheckCircle size={24} />} label="Completed Orders" value={stats?.completedCount || 0} tone="cyan" />
                  <MetricCard icon={<CreditCard size={24} />} label="Waiter Tips" value={`${settings?.currency_symbol || 'ETB'} ${(stats?.completedTips || 0).toFixed(2)}`} tone="amber" />
                </div>

                <div style={{ ...styles.panel, marginTop: '30px' }}>
                  <div style={styles.panelHeader}>
                    <h3 style={styles.panelTitle}>Completed Orders</h3>
                  </div>
                  {completedBills.length > 0 ? (
                    <div style={styles.orderList}>
                      {completedBills.slice(0, 8).map(order => (
                        <div key={order.id} style={styles.orderCard}>
                          <div style={styles.orderCardTop}>
                            <strong style={styles.orderId}>ORD-{order.id}</strong>
                            <span style={styles.pricePill}>{settings?.currency_symbol || 'ETB'} {Number(Number(order.total_amount) + Number(order.tip_amount || 0)).toFixed(2)}</span>
                          </div>
                          <div style={styles.orderStatsLine}>
                            <span>Table {order.table_code}</span> • <span>{order.waiter_name}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={styles.emptyState}>No completed orders yet.</div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === 'tables' && (
              <motion.div key="tables" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={styles.sectionHeaderRow}>
                  <div>
                    <div style={styles.sectionKicker}>REALTIME</div>
                    <h1 style={styles.sectionTitle}>Table Overview</h1>
                  </div>
                </div>
                <div style={{ ...styles.panel, marginTop: '20px' }}>
                  <div style={styles.tableChipGrid}>
                    {tables.map(table => {
                      const orderForTable = pendingBills.find(bill => bill.table === table.id);
                      const isBusy = orderForTable || table.status === 'occupied';
                      return (
                        <div key={table.id} onClick={() => orderForTable && (setSelectedOrder(orderForTable), setActiveTab('orders'))}
                          style={isBusy ? { ...styles.tableChipBusy, cursor: orderForTable ? 'pointer' : 'default' } : styles.tableChipFree}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ fontSize: 16 }}>{table.table_code}</strong>
                            <span style={statusBadge(orderForTable ? 'pending' : (isBusy ? 'occupied' : 'ready'))}>
                              {orderForTable ? 'Paying' : (isBusy ? 'Busy' : 'Free')}
                            </span>
                          </div>
                          {orderForTable && <div style={{ fontSize: 13, fontWeight: 800, marginTop: 4, color: '#9a3412' }}>{settings?.currency_symbol || 'ETB'} {orderForTable.total_amount}</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'orders' && (
              <motion.div key="orders" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', height: '100%', gap: '20px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={styles.sectionHeaderRow}>
                      <div>
                        <div style={styles.sectionKicker}>TRANSACTIONS</div>
                        <h1 style={styles.sectionTitle}>Billing & Checkout</h1>
                      </div>
                      <div style={styles.searchBox}>
                        <Search size={18} color="#94a3b8" />
                        <input type="text" placeholder="Search table or order ID..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={styles.searchInput} />
                      </div>
                    </div>

                    <div style={{ ...styles.panel, flex: 1, overflowY: 'auto' }}>
                      <div style={styles.panelHeader}><h3 style={styles.panelTitle}>Pending Bills</h3></div>
                      {filteredOrders.length > 0 ? (
                        <div style={styles.orderList}>
                          {filteredOrders.map(bill => (
                            <div key={bill.id} onClick={() => setSelectedOrder(bill)}
                              style={{ ...styles.orderCard, borderLeft: selectedOrder?.id === bill.id ? '4px solid #10b981' : 'none', background: selectedOrder?.id === bill.id ? '#f0fdf4' : '#fff', cursor: 'pointer' }}>
                              <div style={styles.orderCardTop}>
                                <strong style={styles.orderId}>ORD-{bill.id}</strong>
                                <span style={styles.pricePill}>{settings?.currency_symbol || 'ETB'} {bill.total_amount}</span>
                              </div>
                              <div style={styles.orderStatsLine}>
                                <span>Table {bill.table_code}</span> • <span>{bill.waiter_name}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={styles.emptyState}>No pending bills.</div>
                      )}

                      <div style={{ ...styles.panelHeader, marginTop: '20px', flexDirection: 'column', alignItems: 'stretch' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <h3 style={styles.panelTitle}>Completed Bills</h3>
                        </div>
                        <div style={styles.filterRow}>
                          <input type="date" value={filterStartDate} onChange={e => setFilterStartDate(e.target.value)} style={styles.filterInput} />
                          <span style={{ fontSize: 12, color: '#94a3b8' }}>to</span>
                          <input type="date" value={filterEndDate} onChange={e => setFilterEndDate(e.target.value)} style={styles.filterInput} />
                          <select value={filterLimit} onChange={e => setFilterLimit(e.target.value)} style={styles.filterSelect}>
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                            <option value={500}>500</option>
                          </select>
                        </div>
                      </div>
                      {filteredCompletedOrders.length > 0 ? (
                        <div style={styles.orderList}>
                          {filteredCompletedOrders.map(bill => (
                            <div key={bill.id} onClick={() => setSelectedOrder(bill)}
                              style={{ ...styles.orderCard, borderLeft: selectedOrder?.id === bill.id ? '4px solid #3b82f6' : 'none', background: selectedOrder?.id === bill.id ? '#eff6ff' : '#fff', cursor: 'pointer' }}>
                              <div style={styles.orderCardTop}>
                                <strong style={styles.orderId}>ORD-{bill.id}</strong>
                                <span style={styles.pricePill}>{settings?.currency_symbol || 'ETB'} {Number(Number(bill.total_amount) + Number(bill.tip_amount || 0)).toFixed(2)}</span>
                              </div>
                              <div style={styles.orderStatsLine}>
                                <span>Table {bill.table_code}</span> • <span>Completed</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={styles.emptyState}>No completed bills.</div>
                      )}
                    </div>
                  </div>

                  <div style={styles.cartPanel}>
                    {selectedOrder ? (
                      <motion.div initial={{ x: 20 }} animate={{ x: 0 }}>
                        <div style={styles.cartHeader}>
                          <div>
                            <div style={{ fontSize: '13px', color: '#64748b', fontWeight: '600' }}>Table Checkout</div>
                            <div style={{ fontSize: '20px', fontWeight: '800', color: '#0f172a' }}>{selectedOrder.table_code}</div>
                          </div>
                          <button onClick={() => setSelectedOrder(null)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={20} color="#94a3b8" /></button>
                        </div>
                        <div style={styles.cartItems}>
                          {selectedOrder.items?.map((item, i) => (
                            <div key={i} style={styles.cartItemRow}>
                              <div style={styles.cartItemInfo}>
                                <div style={styles.cartItemName}>{item.menu_item_name}</div>
                                <div style={styles.cartItemPrice}>{settings?.currency_symbol || 'ETB'} {item.price_at_order}</div>
                              </div>
                              <div style={{ fontSize: '12px', fontWeight: 'bold' }}>x{item.quantity}</div>
                              <div style={styles.cartItemTotal}>{(item.quantity * item.price_at_order).toFixed(2)}</div>
                            </div>
                          ))}
                        </div>
                        <div style={styles.cartSummary}>
                          <div style={styles.summaryRow}><span>Sub-Total</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.sub_total || 0) : billSummary.subTotal).toFixed(2)}</span></div>
                          <div style={styles.summaryRow}><span>Service ({serviceRate}%)</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.service_charge_amount || 0) : billSummary.serviceCharge).toFixed(2)}</span></div>
                          <div style={styles.summaryRow}><span>VAT ({vatRate}%)</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.vat_amount || 0) : billSummary.vat).toFixed(2)}</span></div>
                          {isCompletedOrder && <div style={styles.summaryRow}><span>Tip Amount</span><span style={{ color: '#10b981', fontWeight: 'bold' }}>{settings?.currency_symbol || 'ETB'} {Number(selectedOrder.tip_amount || 0).toFixed(2)}</span></div>}
                          <div style={styles.grandTotalRow}><span>Grand Total</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? (Number(selectedOrder.total_amount || 0) + Number(selectedOrder.tip_amount || 0)) : billSummary.grandTotal).toFixed(2)}</span></div>
                        </div>

                        {!isCompletedOrder ? (
                          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', background: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
                            <div style={{ color: '#0f766e', fontSize: '13px', fontWeight: '700', background: 'rgba(16,185,129,0.1)', padding: '8px 16px', borderRadius: '8px' }}>Awaiting Payment from Waiter</div>
                            <button onClick={() => setAutoPrintOrderId(selectedOrder?.id)} style={{ padding: '12px 20px', background: '#0f172a', color: '#fff', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}><Printer size={16} /> Print Receipt Now</button>
                          </div>
                        ) : (
                          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', background: '#f8fafc' }}>
                            <div style={{ color: '#64748b', fontSize: '14px', fontWeight: 'bold' }}>Order Complete</div>
                            <button onClick={() => setAutoPrintOrderId(selectedOrder?.id)} style={{ padding: '10px 16px', background: '#0f172a', color: '#fff', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}><Printer size={16} style={{marginRight: 6, verticalAlign: 'middle'}}/> Print Receipt Now</button>
                          </div>
                        )}
                      </motion.div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}><Receipt size={48} style={{ opacity: 0.2, marginBottom: '10px' }} /><p style={{ fontSize: '13px' }}>Select an order</p></div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
            {activeTab === 'tips' && (
              <motion.div key="tips" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={styles.sectionHeaderRow}>
                  <div>
                    <div style={styles.sectionKicker}>ANALYTICS</div>
                    <h1 style={styles.sectionTitle}>Tips History</h1>
                  </div>
                </div>
                <div style={{ ...styles.metricGrid, marginTop: '20px' }}>
                  <MetricCard icon={<CreditCard size={24} />} label="Total Tips Collected" value={`${settings?.currency_symbol || 'ETB'} ${(stats?.completedTips || 0).toFixed(2)}`} tone="amber" />
                </div>
                <div style={{ ...styles.panel, marginTop: '30px' }}>
                  <div style={{ ...styles.panelHeader, flexDirection: 'column', alignItems: 'stretch' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={styles.panelTitle}>Completed Orders with Tips</h3>
                    </div>
                    <div style={styles.filterRow}>
                      <input type="date" value={filterStartDate} onChange={e => setFilterStartDate(e.target.value)} style={styles.filterInput} />
                      <span style={{ fontSize: 12, color: '#94a3b8' }}>to</span>
                      <input type="date" value={filterEndDate} onChange={e => setFilterEndDate(e.target.value)} style={styles.filterInput} />
                      <select value={filterLimit} onChange={e => setFilterLimit(e.target.value)} style={styles.filterSelect}>
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={500}>500</option>
                      </select>
                    </div>
                  </div>
                  {completedBills.filter(o => parseFloat(o.tip_amount || 0) > 0).length > 0 ? (
                    <div style={styles.orderList}>
                      {completedBills.filter(o => parseFloat(o.tip_amount || 0) > 0).map(order => (
                        <div key={order.id} style={styles.orderCard}>
                          <div style={styles.orderCardTop}>
                            <strong style={styles.orderId}>ORD-{order.id}</strong>
                            <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#10b981', background: '#dcfce7', padding: '4px 8px', borderRadius: '40px' }}>
                              Tip: {settings?.currency_symbol || 'ETB'} {Number(order.tip_amount).toFixed(2)}
                            </span>
                          </div>
                          <div style={styles.orderStatsLine}>
                            <span>Table {order.table_code}</span> • <span>{order.waiter_name}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={styles.emptyState}>No tips collected yet.</div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {showReceipt && (
              <div style={styles.modalOverlay}>
                <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} style={styles.receiptModal}>
                  <div ref={receiptRef} style={styles.thermalContainer} className={`thermal-receipt print-paper-${settings?.printer_paper_size || '80mm'}`}>
                    <div className="centered">
                      <h3 style={{ margin: '0', fontSize: '16px' }}>{settings?.hotel_name || "ATLAS INTERNATIONAL"}</h3>
                      <p style={{ fontSize: '10px', margin: '2px 0' }}>{fiscalData?.address || "Bole Sub-City, Addis Ababa"}</p>
                      <p style={{ fontSize: '10px', margin: '2px 0' }}>TIN: {fiscalData?.tin}</p>
                      <p style={{ fontSize: '10px', margin: '2px 0' }}>TEL: {fiscalData?.phone}</p>
                      <div className="dashed-divider" />
                      <p style={{ fontSize: '11px', margin: '2px 0' }}>*** NON-FISCAL ***</p>
                      <div className="dashed-divider" />
                      <p className="bold" style={{ fontSize: '12px', margin: '5px 0' }}>OFFICIAL RECEIPT</p>
                      <div className="dashed-divider" />
                    </div>

                    <div style={{ fontSize: '11px', marginBottom: '10px' }}>
                      <div className="item-row"><span>ORD ID:</span><span>#ORD-{fiscalData?.id}</span></div>
                      <div className="item-row"><span>TABLE:</span><span>{fiscalData?.table_code || (fiscalData?.table ? `Table ${fiscalData.table}` : 'N/A')}</span></div>
                      <div className="item-row"><span>WAITER:</span><span>{(fiscalData?.waiter_name || fiscalData?.waiter_username || 'N/A').toUpperCase()}</span></div>
                      <div className="item-row"><span>DATE:</span><span>{fiscalData?.dateTime}</span></div>
                      <div className="item-row"><span>CSHR:</span><span>{userData?.first_name?.toUpperCase() || userData?.username?.toUpperCase() || 'CASHIER'}</span></div>
                    </div>

                    <table style={styles.receiptTable}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: 'left' }}>ITEM</th>
                          <th style={{ textAlign: 'center' }}>QTY</th>
                          <th style={{ textAlign: 'right' }}>PRICE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {fiscalData?.items.map((item, i) => (
                          <tr key={i}>
                            <td style={{ padding: '2px 0' }}>{item.menu_item_name?.toUpperCase()}</td>
                            <td style={{ textAlign: 'center' }}>{item.quantity}</td>
                            <td style={{ textAlign: 'right' }}>*{(item.quantity * item.price_at_order).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div className="dashed-divider" />
                    
                    <div className="item-row"><span>TXBL1 (15%)</span><span>*{(Number(fiscalData?.summary?.sub_total || 0)).toFixed(2)}</span></div>
                    <div className="item-row"><span>TAX1 (15%)</span><span>*{(Number(fiscalData?.summary?.vat || 0)).toFixed(2)}</span></div>
                    <div className="item-row"><span>SRV CHG (10%)</span><span>*{(Number(fiscalData?.summary?.service_charge || 0)).toFixed(2)}</span></div>
                    <div className="item-row"><span>TIP AMNT</span><span>*{(Number(fiscalData?.summary?.tip_amount || 0)).toFixed(2)}</span></div>
                    
                    <div className="dashed-divider" />
                    <div className="item-row bold" style={{ fontSize: '14px' }}>
                      <span>TOTAL</span>
                      <span>*{(Number(fiscalData?.summary.grand_total || 0) + Number(fiscalData?.summary.tip_amount || 0)).toFixed(2)}</span>
                    </div>
                    <div className="dashed-divider" />

                    <div className="centered" style={{ marginTop: '10px' }}>
                      <p style={{ fontSize: '10px' }}>*** NON-FISCAL ***</p>
                      <p className="bold" style={{ fontSize: '10px', marginTop: '5px' }}>FISCAL DATA SECURE</p>
                      <p style={{ fontSize: '9px' }}>FS NO: {fiscalData?.fiscalNumber || 'NF00006105'}</p>
                      <p style={{ fontSize: '9px' }}>MACHINE: {fiscalData?.machineId || 'FG10004841'}</p>
                      <p style={{ fontSize: '10px', marginTop: '10px' }}>*** THANK YOU ***</p>
                    </div>
                  </div>
                  <div style={styles.modalButtons}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
                      <button
                        onClick={handlePrintNow}
                        style={{ ...styles.finalPrintBtn, opacity: isPrinting ? 0.7 : 1, cursor: isPrinting ? 'not-allowed' : 'pointer' }}
                        disabled={isPrinting}
                      >
                        {isPrinting ? 'Preparing Receipt...' : 'Print Now'}
                      </button>
                      <div style={{ padding: '8px 12px', backgroundColor: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8 }}>
                        <p style={{ margin: 0, fontSize: '11px', color: '#b45309', lineHeight: 1.4, textAlign: 'center' }}>
                          💡 <strong>TIP:</strong> For professional receipts, set <strong>Scale: 100%</strong> and <strong>Margins: None</strong> in the print dialog.
                        </p>
                      </div>
                      <button onClick={() => setShowReceipt(false)} style={styles.cancelPrintBtn}>Close Window</button>
                    </div>
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {toastNotification && (
              <motion.div
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                style={styles.toastPopup}
              >
                <strong>New Bill Request</strong>
                <div style={{ fontSize: '12px' }}>{toastNotification.message}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};
const statusBadge = (s) => {
  const map = {
    pending: { bg: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d', padding: '4px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: 'bold' },
    occupied: { bg: '#fef2f2', color: '#b91c1c', border: '1px solid #fca5a5', padding: '4px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: 'bold' },
    ready: { bg: '#f0fdf4', color: '#15803d', border: '1px solid #86efac', padding: '4px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: 'bold' },
  };
  return map[s] || map.ready;
};

const styles = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #f4fbff 0%, #f8fafc 42%, #f2f7f5 100%)',
    color: '#0f172a',
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    position: 'relative',
    overflow: 'hidden',
  },
  backgroundAuraA: {
    position: 'absolute',
    top: -180,
    right: -120,
    width: 420,
    height: 420,
    background: 'radial-gradient(circle, rgba(16,185,129,0.15), rgba(16,185,129,0))',
    pointerEvents: 'none',
  },
  backgroundAuraB: {
    position: 'absolute',
    left: -140,
    top: 120,
    width: 320,
    height: 320,
    background: 'radial-gradient(circle, rgba(59,130,246,0.12), rgba(59,130,246,0))',
    pointerEvents: 'none',
  },
  topBar: {
    position: 'sticky',
    top: 0,
    zIndex: 20,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 16,
    padding: '18px 24px',
    backdropFilter: 'blur(16px)',
    background: 'rgba(255,255,255,0.76)',
    borderBottom: '1px solid rgba(148,163,184,0.16)',
  },
  brandBlock: { display: 'flex', alignItems: 'center', gap: 14 },
  brandIcon: {
    width: 42,
    height: 42,
    borderRadius: 14,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #0f766e, #2563eb)',
    color: '#fff',
    fontWeight: 900,
  },
  brandTitle: { fontSize: 20, fontWeight: 900, letterSpacing: '-0.02em' },
  brandSub: { color: '#64748b', fontSize: 13 },
  topActions: { display: 'flex', alignItems: 'center', gap: 10 },
  alertPill: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 12px',
    borderRadius: 999,
    background: '#fff7ed',
    color: '#c2410c',
    border: '1px solid #fed7aa',
    fontWeight: 700,
    fontSize: 13,
  },
  userPill: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 12px',
    borderRadius: 999,
    background: '#eff6ff',
    color: '#1d4ed8',
    border: '1px solid #bfdbfe',
    fontWeight: 700,
    fontSize: 13,
  },
  logoutButton: {
    border: 'none',
    borderRadius: 999,
    padding: '10px 14px',
    background: '#0f172a',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 800,
  },
  layout: {
    position: 'relative',
    zIndex: 1,
    display: 'grid',
    gridTemplateColumns: '280px 1fr',
    gap: 22,
    padding: 24,
  },
  sidebar: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  sidebarItem: {
    border: '1px solid #dbeafe',
    background: 'rgba(255,255,255,0.82)',
    borderRadius: 18,
    padding: '14px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    cursor: 'pointer',
    color: '#334155',
    fontWeight: 700,
  },
  sidebarItemActive: {
    border: '1px solid #0f766e',
    background: 'linear-gradient(135deg, #ecfeff, #eef2ff)',
    borderRadius: 18,
    padding: '14px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    cursor: 'pointer',
    color: '#0f766e',
    fontWeight: 800,
    boxShadow: '0 14px 30px rgba(15,118,110,0.10)',
  },
  sidebarCard: {
    marginTop: 8,
    borderRadius: 28,
    padding: 20,
    background: 'linear-gradient(145deg, #0f172a, #0f766e)',
    color: '#fff',
    boxShadow: '0 18px 40px rgba(15,23,42,0.24)',
  },
  sidebarCardLabel: { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.08em', opacity: 0.7 },
  sidebarBigNumber: { fontSize: 42, fontWeight: 900, marginTop: 10 },
  sidebarMuted: { opacity: 0.8, marginBottom: 18 },
  sidebarStatRow: { display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 14 },
  main: {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  hero: {
    display: 'grid',
    gridTemplateColumns: '1.4fr 0.9fr',
    gap: 20,
    padding: 28,
    borderRadius: 32,
    background: 'linear-gradient(135deg, #ffffff, #eef8ff 50%, #f0fdf4)',
    border: '1px solid rgba(148,163,184,0.18)',
    boxShadow: '0 22px 60px rgba(15,23,42,0.08)',
  },
  sectionKicker: {
    color: '#0f766e',
    fontWeight: 900,
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: '0.12em',
    marginBottom: 10,
  },
  heroTitle: { margin: 0, fontSize: 34, lineHeight: 1.1, maxWidth: 760 },
  heroText: { color: '#475569', fontSize: 15, lineHeight: 1.6, maxWidth: 620, marginTop: 14, marginBottom: 20 },
  heroActions: { display: 'flex', flexWrap: 'wrap', gap: 12 },
  primaryButton: {
    border: 'none',
    borderRadius: 16,
    padding: '13px 18px',
    background: 'linear-gradient(135deg, #0f766e, #2563eb)',
    color: '#fff',
    fontWeight: 800,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    cursor: 'pointer',
    boxShadow: '0 16px 30px rgba(37,99,235,0.18)',
  },
  ghostButton: {
    border: '1px solid #cbd5e1',
    borderRadius: 16,
    padding: '13px 18px',
    background: '#fff',
    color: '#0f172a',
    fontWeight: 800,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    cursor: 'pointer',
  },
  heroPanel: {
    borderRadius: 26,
    padding: 20,
    background: '#0f172a',
    color: '#fff',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  heroPanelTitle: { fontWeight: 900, fontSize: 18 },
  quickOrderCard: {
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 18,
    background: 'rgba(255,255,255,0.04)',
    color: '#fff',
    padding: '14px 16px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
  },
  quickOrderAmount: { fontWeight: 800, color: '#93c5fd' },
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    gap: 16,
  },
  metricCard: {
    background: 'rgba(255,255,255,0.86)',
    border: '1px solid rgba(148,163,184,0.16)',
    borderRadius: 24,
    padding: 20,
    display: 'flex',
    gap: 14,
    alignItems: 'center',
    boxShadow: '0 12px 28px rgba(15,23,42,0.05)',
  },
  metricIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  metricLabel: { fontSize: 13, color: '#64748b', fontWeight: 700 },
  metricValue: { fontSize: 28, fontWeight: 900, marginTop: 4 },
  dualGrid: { display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 20 },
  panel: {
    background: 'rgba(255,255,255,0.88)',
    border: '1px solid rgba(148,163,184,0.18)',
    borderRadius: 28,
    padding: 20,
    boxShadow: '0 18px 40px rgba(15,23,42,0.06)',
  },
  panelHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 16,
  },
  panelTitle: { fontWeight: 900, fontSize: 20 },
  panelSub: { color: '#64748b', fontSize: 13, marginTop: 4 },
  panelBadge: {
    padding: '8px 10px',
    borderRadius: 999,
    background: '#eef2ff',
    color: '#4338ca',
    fontWeight: 800,
    fontSize: 12,
  },
  tableChipGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: 12,
  },
  tableChipFree: {
    borderRadius: 18,
    padding: 14,
    border: '1px solid #bbf7d0',
    background: '#f0fdf4',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  tableChipBusy: {
    borderRadius: 18,
    padding: 14,
    border: '1px solid #fdba74',
    background: '#fff7ed',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  inlineButton: {
    border: 'none',
    background: '#eff6ff',
    color: '#1d4ed8',
    borderRadius: 12,
    padding: '10px 12px',
    cursor: 'pointer',
    fontWeight: 800,
  },
  stack: { display: 'flex', flexDirection: 'column', gap: 12 },
  notificationRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 14,
    alignItems: 'center',
    padding: 14,
    background: '#fff',
    borderRadius: 18,
    border: '1px solid #e2e8f0',
  },
  notificationCard: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 14,
    alignItems: 'center',
    padding: 16,
    background: '#fff',
    borderRadius: 18,
    border: '1px solid #e2e8f0',
  },
  notificationTextBlock: { display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 },
  notificationTitle: { fontSize: 14, lineHeight: 1.45 },
  notificationTime: { color: '#64748b', fontSize: 12 },
  sectionHeaderRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    gap: 16,
  },
  sectionTitle: { margin: 0, fontSize: 28, lineHeight: 1.15 },
  orderSummaryRow: { display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 },
  miniSummary: {
    padding: 16,
    borderRadius: 18,
    background: '#fff',
    border: '1px solid #e2e8f0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontWeight: 700,
  },
  orderList: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 },
  orderCard: {
    borderRadius: 22,
    background: 'linear-gradient(180deg, #ffffff, #f8fafc)',
    border: '1px solid #e2e8f0',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  orderCardTop: { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' },
  orderId: { fontSize: 18 },
  badgeRow: { display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'flex-end' },
  badge: {
    padding: '6px 10px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 900,
    textTransform: 'uppercase',
  },
  orderStatsLine: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 12,
    color: '#475569',
    fontSize: 13,
  },
  orderActionRow: { display: 'flex', flexWrap: 'wrap', gap: 10 },
  smallPrimary: {
    border: 'none',
    borderRadius: 12,
    padding: '10px 12px',
    background: '#2563eb',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 800,
  },
  smallWarning: {
    border: 'none',
    borderRadius: 12,
    padding: '10px 12px',
    background: '#ea580c',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 800,
  },
  smallSuccess: {
    border: 'none',
    borderRadius: 12,
    padding: '10px 12px',
    background: '#059669',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 800,
  },
  smallGhost: {
    border: '1px solid #cbd5e1',
    borderRadius: 12,
    padding: '10px 12px',
    background: '#fff',
    color: '#334155',
    cursor: 'pointer',
    fontWeight: 800,
  },
  menuGridLayout: {
    display: 'grid',
    gridTemplateColumns: '1.35fr 0.85fr',
    gap: 20,
    alignItems: 'start',
  },
  searchShell: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    borderRadius: 18,
    padding: '12px 14px',
    background: '#fff',
    border: '1px solid #e2e8f0',
    marginBottom: 14,
  },
  searchInput: { border: 'none', outline: 'none', width: '100%', background: 'transparent', fontSize: 14 },
  categoryRow: { display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 16 },
  categoryButton: {
    border: '1px solid #cbd5e1',
    borderRadius: 999,
    background: '#fff',
    padding: '9px 14px',
    cursor: 'pointer',
    fontWeight: 700,
  },
  categoryButtonActive: {
    border: '1px solid #0f766e',
    borderRadius: 999,
    background: '#ccfbf1',
    color: '#115e59',
    padding: '9px 14px',
    cursor: 'pointer',
    fontWeight: 800,
  },
  menuCards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 },
  menuCard: {
    border: '1px solid #dbeafe',
    borderRadius: 20,
    background: '#fff',
    padding: 16,
    cursor: 'pointer',
    textAlign: 'left',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  menuCardTop: { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' },
  pricePill: {
    padding: '6px 8px',
    borderRadius: 999,
    background: '#eff6ff',
    color: '#1d4ed8',
    fontWeight: 800,
    fontSize: 12,
    whiteSpace: 'nowrap',
  },
  cartPanel: {
    background: 'linear-gradient(180deg, #ffffff, #f8fafc)',
    border: '1px solid rgba(148,163,184,0.18)',
    borderRadius: 24,
    padding: 24,
    boxShadow: '0 20px 45px rgba(15,23,42,0.08)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    position: 'sticky',
    top: 104,
  },
  cartHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: 16,
    borderBottom: '1px solid #f1f5f9',
    marginBottom: 8,
  },
  cartItems: { display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 360, overflowY: 'auto', paddingRight: 4 },
  cartItemRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 14px',
    background: '#fff',
    borderRadius: 16,
    border: '1px solid #f1f5f9',
    boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
  },
  cartItemInfo: { flex: 1, minWidth: 0 },
  cartItemName: { fontSize: '14px', fontWeight: 'bold', color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  cartItemPrice: { fontSize: '13px', color: '#64748b', marginTop: 4 },
  cartItemTotal: { fontSize: '15px', fontWeight: '900', color: '#0f766e', minWidth: 60, textAlign: 'right' },
  cartSummary: {
    background: '#f8fafc',
    borderRadius: 20,
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    border: '1px solid #e2e8f0',
  },
  summaryRow: { display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: '#475569', fontWeight: '600' },
  grandTotalRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '18px',
    color: '#0f172a',
    fontWeight: '900',
    paddingTop: 12,
    marginTop: 6,
    borderTop: '2px dashed #cbd5e1',
  },

  checkoutSummary: {
    padding: 16,
    borderRadius: 18,
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
  },
  paymentChoiceRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  paymentChoice: {
    border: '1px solid #cbd5e1',
    borderRadius: 16,
    background: '#fff',
    padding: '12px 16px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    fontWeight: 800,
    cursor: 'pointer',
  },
  paymentChoiceActive: {
    border: '1px solid #0f766e',
    borderRadius: 16,
    background: '#ccfbf1',
    color: '#115e59',
    padding: '12px 16px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    fontWeight: 900,
    cursor: 'pointer',
  },
  qrShell: { display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' },
  qrCard: {
    padding: 18,
    borderRadius: 24,
    background: '#fff',
    border: '1px solid #dbeafe',
    boxShadow: '0 16px 40px rgba(15,23,42,0.08)',
  },
  helperText: { color: '#475569', lineHeight: 1.6, textAlign: 'center', fontSize: 13 },
  deepLink: { color: '#1d4ed8', fontWeight: 800, textDecoration: 'none' },
  modalOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(15,23,42,0.42)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    zIndex: 100,
    backdropFilter: 'blur(8px)',
  },
  receiptModal: {
    width: '100%',
    maxWidth: 380,
    background: '#fff',
    borderRadius: 8,
    border: '1px solid #e2e8f0',
    padding: 20,
    boxShadow: '0 30px 80px rgba(15,23,42,0.18)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  thermalContainer: {
    fontFamily: "'Courier New', Courier, monospace",
    color: '#000',
    background: '#fff',
    padding: '10px',
    margin: '0 auto',
  },
  thermalHeader: {
    textAlign: 'center',
    marginBottom: '10px',
    lineHeight: '1.2',
  },
  receiptTable: {
    width: '100%',
    fontSize: '12px',
    borderCollapse: 'collapse',
    marginTop: '5px',
    marginBottom: '5px',
  },
  receiptDivider: {
    borderTop: '1px dashed #000',
    margin: '8px 0',
  },
  receiptRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    marginBottom: '2px',
  },
  thermalFooter: {
    textAlign: 'center',
    marginTop: '10px',
    fontSize: '10px',
    lineHeight: '1.4',
  },
  modalButtons: { display: 'flex', gap: 10, marginTop: 20, width: '100%', justifyContent: 'center' },
  finalPrintBtn: {
    padding: '10px 20px', background: '#0f172a', color: '#fff', fontWeight: 800, borderRadius: 8, border: 'none', cursor: 'pointer'
  },
  cancelPrintBtn: {
    padding: '10px 20px', background: '#e2e8f0', color: '#334155', fontWeight: 800, borderRadius: 8, border: 'none', cursor: 'pointer'
  },
  modalCard: {
    width: '100%',
    maxWidth: 560,
    background: '#fff',
    borderRadius: 28,
    border: '1px solid rgba(148,163,184,0.2)',
    padding: 20,
    boxShadow: '0 30px 80px rgba(15,23,42,0.18)',
  },
  modalHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  iconButton: {
    border: '1px solid #dbeafe',
    background: '#fff',
    width: 34,
    height: 34,
    borderRadius: 12,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyCard: {
    padding: 18,
    borderRadius: 18,
    background: '#fff',
    border: '1px dashed #cbd5e1',
    color: '#64748b',
    textAlign: 'center',
  },
  notificationPanel: {
    position: 'absolute',
    top: '130%',
    right: 0,
    width: 340,
    background: 'rgba(255,255,255,0.96)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(148,163,184,0.15)',
    boxShadow: '0 30px 60px rgba(15,23,42,0.15)',
    borderRadius: 24,
    zIndex: 50,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  notificationHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    background: '#f8fafc',
    borderBottom: '1px solid #e2e8f0',
  },
  notificationBadge: {
    position: 'absolute',
    top: -6,
    right: -4,
    background: '#ef4444',
    color: '#fff',
    fontSize: 10,
    fontWeight: 'bold',
    width: 18,
    height: 18,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 4px 10px rgba(239,68,68,0.4)',
  },
  clearBtn: {
    fontSize: 12,
    color: '#0f766e',
    background: 'rgba(15,118,110,0.1)',
    padding: '6px 12px',
    borderRadius: 40,
    border: 'none',
    cursor: 'pointer',
    fontWeight: 'bold',
    transition: 'all 0.2s',
  },
  deleteNoteBtn: {
    background: '#fef2f2',
    color: '#ef4444',
    border: '1px solid #fee2e2',
    borderRadius: 10,
    width: 28,
    height: 28,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  filterRow: { display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 },
  filterInput: { padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 13, outline: 'none' },
  filterSelect: { padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 13, outline: 'none', background: '#fff' },
  hiddenMobile: {},
};

if (typeof window !== 'undefined' && window.innerWidth < 960) {
  styles.layout.gridTemplateColumns = '1fr';
  styles.hero.gridTemplateColumns = '1fr';
  styles.metricGrid.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
  styles.dualGrid.gridTemplateColumns = '1fr';
  styles.menuGridLayout.gridTemplateColumns = '1fr';
  styles.orderSummaryRow.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
}

export default CashierDashboard;