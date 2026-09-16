import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  ShoppingCart, Printer, X, Search, Clock, User,
  DollarSign, TrendingUp, AlertCircle, Calendar,
  ArrowRight, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;
const ORDERS_API = `${API_BASE}orders/`;
const UPDATE_STATUS_API = (id) => `${API_BASE}orders/${id}/update-status/`;
const PROCESS_PAYMENT_API = (id) => `${API_BASE}cashier/process/${id}/`;
const SETTINGS_API = `${API_BASE}settings/`;

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

export default function OrdersManager({ userData }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const limit = 50;
  const [settings, setSettings] = useState(null);
  
  // Payment states
  const [paymentMethod, setPaymentMethod] = useState('Cash');
  const [paymentReference, setPaymentReference] = useState('');
  
  // Receipt Printing states
  const [showReceipt, setShowReceipt] = useState(false);
  const [fiscalData, setFiscalData] = useState(null);
  const receiptRef = useRef(null);

  const getHeaders = () => {
    const token = localStorage.getItem('access_token');
    return { Authorization: `Bearer ${token}` };
  };

  const fetchOrders = async (showLoader = false) => {
    if (showLoader) setLoading(true);
    try {
      let url = `${ORDERS_API}?limit=${limit}&_cb=${new Date().getTime()}`;
      if (statusFilter !== 'all') url += `&status=${statusFilter}`;
      if (startDate) url += `&start_date=${startDate}`;
      if (endDate) url += `&end_date=${endDate}`;
      
      const res = await axios.get(url, { 
        headers: {
          ...getHeaders(),
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        } 
      });
      setOrders(res.data || []);
      
      // If selectedOrder exists, update it with fresh data
      if (selectedOrder) {
        const updated = res.data.find(o => o.id === selectedOrder.id);
        if (updated) setSelectedOrder(updated);
      }
    } catch (err) {
      console.error('Failed to fetch orders:', err);
    } finally {
      if (showLoader) setLoading(false);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await axios.get(SETTINGS_API, { headers: getHeaders() });
      const data = Array.isArray(res.data) ? res.data[0] : res.data;
      setSettings(data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  useEffect(() => {
    fetchSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchOrders(true);
    const interval = setInterval(() => fetchOrders(false), 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, startDate, endDate, limit]);

  const handleUpdateStatus = async (orderId, newStatus) => {
    try {
      await axios.post(UPDATE_STATUS_API(orderId), { status: newStatus }, { headers: getHeaders() });
      fetchOrders(false);
    } catch (err) {
      alert('Failed to update status: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleProcessPayment = async () => {
    if (!selectedOrder) return;
    try {
      const payload = {
        payment_method: paymentMethod,
        payment_reference: paymentReference || `ADMIN-PAY-${selectedOrder.id}-${new Date().getTime()}`
      };
      const res = await axios.post(PROCESS_PAYMENT_API(selectedOrder.id), payload, { headers: getHeaders() });
      
      setFiscalData({
        ...selectedOrder,
        summary: res.data.receipt_data || res.data,
        tin: settings?.tin_number || "0002915740",
        address: settings?.address || "Bole Sub-City, Addis Ababa",
        phone: settings?.phone_number || "0116187432",
        machineId: settings?.fiscal_machine_no || "FG10004841",
        fiscalNumber: "FS" + Math.floor(100000 + Math.random() * 900000),
        dateTime: new Date().toLocaleString()
      });

      setShowReceipt(true);
      setPaymentReference('');
      fetchOrders(false);
    } catch (err) {
      alert('Payment processing failed: ' + (err.response?.data?.error || err.message));
    }
  };

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
  };

  const handleOpenPrintPreview = (order) => {
    setFiscalData({
      ...order,
      summary: {
        sub_total: order.sub_total,
        vat: order.vat_amount,
        service_charge: order.service_charge_amount,
        grand_total: order.total_amount,
        tip_amount: order.tip_amount || 0,
      },
      tin: settings?.tin_number || "0002915740",
      address: settings?.address || "Bole Sub-City, Addis Ababa",
      phone: settings?.phone_number || "0116187432",
      machineId: settings?.fiscal_machine_no || "FG10004841",
      fiscalNumber: "FS" + Math.floor(100000 + Math.random() * 900000),
      dateTime: new Date(order.created_at).toLocaleString()
    });
    setShowReceipt(true);
  };

  // Compute stats
  const metrics = React.useMemo(() => {
    const total = orders.length;
    const active = orders.filter(o => ['pending', 'preparing', 'ready', 'served'].includes(o.status)).length;
    const paidOrders = orders.filter(o => o.payment_status === 'paid');
    const revenue = paidOrders.reduce((sum, o) => sum + parseFloat(o.total_amount || 0), 0);
    const cancelled = orders.filter(o => o.status === 'cancelled').length;
    return { total, active, revenue, cancelled };
  }, [orders]);

  // Filter & Search list
  const filteredOrdersList = orders.filter(o => {
    const matchesSearch = o.table_code?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.waiter_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(o.id).includes(searchQuery);
    return matchesSearch;
  });

  const getStatusStyle = (status) => {
    switch (status) {
      case 'pending':
        return { bg: '#fffbeb', color: '#d97706', border: '1px solid #fde68a' };
      case 'preparing':
        return { bg: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' };
      case 'ready':
        return { bg: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0' };
      case 'served':
        return { bg: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe' };
      case 'bill_requested':
        return { bg: '#fff5f5', color: '#e11d48', border: '1px solid #fecaca' };
      case 'paid':
        return { bg: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' };
      case 'cancelled':
        return { bg: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' };
      default:
        return { bg: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' };
    }
  };

  const currency = settings?.currency_symbol || 'ETB';

  return (
    <div style={styles.container}>
      <div style={styles.backgroundAuraA} />
      <div style={styles.backgroundAuraB} />

      <div style={styles.header}>
        <div>
          <div style={styles.kicker}>ADMINISTRATION</div>
          <h1 style={styles.title}>Order Management Dashboard</h1>
        </div>
        <button onClick={() => fetchOrders(true)} style={styles.refreshBtn} title="Force Refresh">
          <RefreshCw size={18} />
        </button>
      </div>

      {/* Metrics Row */}
      <div style={styles.metricGrid}>
        <MetricCard icon={<ShoppingCart size={24} />} label="Total Orders" value={metrics.total} tone="cyan" />
        <MetricCard icon={<Clock size={24} />} label="Active Orders" value={metrics.active} tone="amber" />
        <MetricCard icon={<DollarSign size={24} />} label="Total Revenue (Paid)" value={`${currency} ${metrics.revenue.toFixed(2)}`} tone="green" />
        <MetricCard icon={<AlertCircle size={24} />} label="Cancelled Orders" value={metrics.cancelled} tone="rose" />
      </div>

      <div style={styles.contentGrid}>
        {/* Left column: Orders listing & filters */}
        <div style={styles.panel}>
          <div style={styles.filterBar}>
            <div style={styles.searchBox}>
              <Search size={18} color="#94a3b8" />
              <input 
                type="text" 
                placeholder="Search by ID, table, or waiter..." 
                value={searchQuery} 
                onChange={(e) => setSearchQuery(e.target.value)} 
                style={styles.searchInput} 
              />
            </div>
            
            <div style={styles.dateFilters}>
              <div style={styles.dateField}>
                <Calendar size={14} color="#64748b" />
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={styles.dateInput} />
              </div>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>to</span>
              <div style={styles.dateField}>
                <Calendar size={14} color="#64748b" />
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={styles.dateInput} />
              </div>
            </div>
          </div>

          {/* Status Tabs */}
          <div style={styles.tabsRow}>
            {['all', 'pending', 'preparing', 'ready', 'served', 'bill_requested', 'paid', 'cancelled'].map(tab => (
              <button
                key={tab}
                onClick={() => setStatusFilter(tab)}
                style={{
                  ...styles.tabBtn,
                  ...(statusFilter === tab ? styles.tabBtnActive : {})
                }}
              >
                {tab.replace('_', ' ')}
              </button>
            ))}
          </div>

          {loading ? (
            <div style={styles.centeredState}>
              <div style={styles.spinner} />
              <span style={{ marginTop: 10, color: '#64748b', fontSize: 14 }}>Loading orders...</span>
            </div>
          ) : filteredOrdersList.length === 0 ? (
            <div style={styles.emptyState}>
              <ShoppingCart size={40} style={{ opacity: 0.2, marginBottom: 12 }} />
              <p>No orders found matching criteria.</p>
            </div>
          ) : (
            <div style={styles.ordersList}>
              {filteredOrdersList.map(order => {
                const sStyle = getStatusStyle(order.status);
                const isSelected = selectedOrder?.id === order.id;
                return (
                  <div
                    key={order.id}
                    onClick={() => setSelectedOrder(order)}
                    style={{
                      ...styles.orderCard,
                      borderLeft: isSelected ? '4px solid #0f766e' : '4px solid transparent',
                      backgroundColor: isSelected ? 'rgba(236, 254, 255, 0.6)' : '#ffffff'
                    }}
                  >
                    <div style={styles.cardHeader}>
                      <span style={styles.orderId}>ORD-{order.id}</span>
                      <span style={{
                        backgroundColor: sStyle.bg,
                        color: sStyle.color,
                        border: sStyle.border,
                        ...styles.statusBadge
                      }}>
                        {order.status}
                      </span>
                    </div>
                    <div style={styles.cardBody}>
                      <span style={styles.cardMeta}>Table: <strong>{order.table_code}</strong></span>
                      <span style={styles.cardMeta}>Waiter: <strong>{order.waiter_name || 'System'}</strong></span>
                      <span style={styles.cardMeta}>{new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div style={styles.cardFooter}>
                      <span style={styles.cardItemCount}>{order.items?.length || 0} item(s)</span>
                      <span style={styles.cardPrice}>{currency} {Number(order.total_amount).toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right column: Selected order details */}
        <div style={styles.detailsPanel}>
          {selectedOrder ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={styles.detailsHeader}>
                <div>
                  <h3 style={styles.detailsTitle}>Order details</h3>
                  <span style={styles.detailsSubtitle}>ORD-{selectedOrder.id} • Table {selectedOrder.table_code}</span>
                </div>
                <button onClick={() => setSelectedOrder(null)} style={styles.closeBtn}>
                  <X size={20} />
                </button>
              </div>

              <div style={styles.detailsContent}>
                {/* Meta details */}
                <div style={styles.metaBox}>
                  <div style={styles.metaItem}><User size={16} color="#64748b" /> <span>Waiter: <strong>{selectedOrder.waiter_name || 'System'}</strong></span></div>
                  <div style={styles.metaItem}><Clock size={16} color="#64748b" /> <span>Time: <strong>{new Date(selectedOrder.created_at).toLocaleString()}</strong></span></div>
                  <div style={styles.metaItem}><TrendingUp size={16} color="#64748b" /> <span>Payment Status: <strong style={{ color: selectedOrder.payment_status === 'paid' ? '#16a34a' : '#d97706' }}>{selectedOrder.payment_status.toUpperCase()}</strong></span></div>
                  {selectedOrder.payment_method && (
                    <div style={styles.metaItem}><DollarSign size={16} color="#64748b" /> <span>Method: <strong>{selectedOrder.payment_method} ({selectedOrder.payment_reference || 'N/A'})</strong></span></div>
                  )}
                </div>

                {/* Items list */}
                <div style={styles.itemsSection}>
                  <div style={styles.sectionHeader}>Order items</div>
                  <div style={styles.itemsList}>
                    {selectedOrder.items?.map((item, idx) => (
                      <div key={idx} style={styles.itemRow}>
                        <div style={styles.itemNameCol}>
                          <span style={styles.itemName}>{item.menu_item_name}</span>
                          <span style={styles.itemPriceDetail}>{currency} {item.price_at_order} each</span>
                        </div>
                        <span style={styles.itemQty}>x{item.quantity}</span>
                        <span style={styles.itemTotal}>{currency} {(item.quantity * item.price_at_order).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Bill Breakdown */}
                <div style={styles.billingSection}>
                  <div style={styles.billRow}><span>Sub-Total</span><span>{currency} {Number(selectedOrder.sub_total).toFixed(2)}</span></div>
                  <div style={styles.billRow}><span>Service Charge (10%)</span><span>{currency} {Number(selectedOrder.service_charge_amount).toFixed(2)}</span></div>
                  <div style={styles.billRow}><span>VAT (15%)</span><span>{currency} {Number(selectedOrder.vat_amount).toFixed(2)}</span></div>
                  {Number(selectedOrder.tip_amount) > 0 && (
                    <div style={styles.billRow}><span>Tip Amount</span><span style={{ color: '#16a34a', fontWeight: 'bold' }}>{currency} {Number(selectedOrder.tip_amount).toFixed(2)}</span></div>
                  )}
                  <div style={styles.billTotalRow}>
                    <span>Grand Total</span>
                    <span>{currency} {(Number(selectedOrder.total_amount) + Number(selectedOrder.tip_amount || 0)).toFixed(2)}</span>
                  </div>
                </div>

                {/* Status-specific action buttons */}
                {selectedOrder.payment_status !== 'paid' && selectedOrder.status !== 'cancelled' && (
                  <div style={styles.actionsSection}>
                    <div style={styles.sectionHeader}>Admin actions</div>
                    
                    {/* State workflow buttons */}
                    <div style={styles.actionBtnGrid}>
                      {selectedOrder.status === 'pending' && (
                        <button onClick={() => handleUpdateStatus(selectedOrder.id, 'preparing')} style={styles.actionBtn}>
                          Start Preparing <ArrowRight size={16} />
                        </button>
                      )}
                      {selectedOrder.status === 'preparing' && (
                        <button onClick={() => handleUpdateStatus(selectedOrder.id, 'ready')} style={styles.actionBtn}>
                          Set to Ready <ArrowRight size={16} />
                        </button>
                      )}
                      {selectedOrder.status === 'ready' && (
                        <button onClick={() => handleUpdateStatus(selectedOrder.id, 'served')} style={styles.actionBtn}>
                          Mark Served <ArrowRight size={16} />
                        </button>
                      )}

                      {/* Manual Payment Section */}
                      {['served', 'bill_requested', 'ready'].includes(selectedOrder.status) && (
                        <div style={styles.paymentBox}>
                          <div style={{ fontSize: 13, fontWeight: '700', marginBottom: 8, color: '#334155' }}>Process cash payment:</div>
                          <div style={styles.payMethods}>
                            {['Cash', 'Telebirr', 'Card'].map(m => (
                              <button 
                                key={m} 
                                onClick={() => setPaymentMethod(m)} 
                                style={{
                                  ...styles.payMethodBtn,
                                  backgroundColor: paymentMethod === m ? '#1e293b' : '#ffffff',
                                  color: paymentMethod === m ? '#ffffff' : '#1e293b'
                                }}
                              >
                                {m}
                              </button>
                            ))}
                          </div>
                          {paymentMethod !== 'Cash' && (
                            <input 
                              type="text" 
                              placeholder="Reference / Transaction ID" 
                              value={paymentReference} 
                              onChange={(e) => setPaymentReference(e.target.value)} 
                              style={styles.payInput} 
                            />
                          )}
                          <button onClick={handleProcessPayment} style={styles.payConfirmBtn}>
                            Confirm Payment & Check out
                          </button>
                        </div>
                      )}

                      {/* Cancel Order */}
                      <button onClick={() => handleUpdateStatus(selectedOrder.id, 'cancelled')} style={styles.cancelOrderBtn}>
                        Cancel Order
                      </button>
                    </div>
                  </div>
                )}

                {/* Print Receipt Section */}
                {selectedOrder.payment_status === 'paid' && (
                  <div style={styles.printSection}>
                    <div style={{ fontSize: 13, color: '#64748b', fontWeight: 'bold' }}>Order finalized successfully.</div>
                    <button onClick={() => handleOpenPrintPreview(selectedOrder)} style={styles.printReceiptBtn}>
                      <Printer size={16} /> Print Official Receipt
                    </button>
                  </div>
                )}
              </div>
            </motion.div>
          ) : (
            <div style={styles.centeredState}>
              <ShoppingCart size={48} style={{ opacity: 0.15, marginBottom: 12 }} />
              <span style={{ fontSize: 14, color: '#64748b' }}>Select an order from the list to view its details.</span>
            </div>
          )}
        </div>
      </div>

      {/* Invoice Thermal Receipt modal overlay */}
      <AnimatePresence>
        {showReceipt && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} style={styles.receiptModal}>
              <div ref={receiptRef} style={styles.thermalContainer}>
                <div className="centered" style={{ textAlign: 'center' }}>
                  <h3 style={{ margin: '0 0 5px 0', fontSize: '15px', fontWeight: 'bold' }}>{settings?.hotel_name || "ATLAS INTERNATIONAL HOTEL PLC"}</h3>
                  <p style={{ fontSize: '10px', margin: '2px 0' }}>{fiscalData?.address || "Bole Sub-City, Woreda 03, H.No 033"}</p>
                  <p style={{ fontSize: '10px', margin: '2px 0' }}>TIN: {fiscalData?.tin || "0002915740"}</p>
                  <p style={{ fontSize: '10px', margin: '2px 0' }}>TEL: {fiscalData?.phone || "0116187432"}</p>
                  <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                  <p style={{ fontSize: '11px', margin: '2px 0', fontWeight: 'bold' }}>*** NON-FISCAL ***</p>
                  <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                  <p className="bold" style={{ fontSize: '12px', margin: '5px 0', fontWeight: 'bold' }}>OFFICIAL RECEIPT</p>
                  <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                </div>

                <div style={{ fontSize: '11px', margin: '10px 0', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>ORD ID:</span><span>#ORD-{fiscalData?.id}</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>TABLE:</span><span>{fiscalData?.table_code}</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>DATE:</span><span>{fiscalData?.dateTime}</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>WAITER:</span><span>{fiscalData?.waiter_name?.toUpperCase() || 'SYSTEM'}</span></div>
                </div>

                <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                
                <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px dashed #000' }}>
                      <th style={{ textAlign: 'left', padding: '3px 0' }}>ITEM</th>
                      <th style={{ textAlign: 'center', padding: '3px 0' }}>QTY</th>
                      <th style={{ textAlign: 'right', padding: '3px 0' }}>TOTAL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fiscalData?.items?.map((item, i) => (
                      <tr key={i}>
                        <td style={{ padding: '3px 0' }}>{item.menu_item_name?.toUpperCase()}</td>
                        <td style={{ textAlign: 'center', padding: '3px 0' }}>{item.quantity}</td>
                        <td style={{ textAlign: 'right', padding: '3px 0' }}>*{(item.quantity * item.price_at_order).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                
                <div style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>SUB-TOTAL</span><span>*{(Number(fiscalData?.summary?.sub_total || 0)).toFixed(2)}</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>SERVICE (10%)</span><span>*{(Number(fiscalData?.summary?.service_charge || 0)).toFixed(2)}</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>VAT (15%)</span><span>*{(Number(fiscalData?.summary?.vat || 0)).toFixed(2)}</span></div>
                  {Number(fiscalData?.summary?.tip_amount) > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>TIP AMOUNT</span><span>*{(Number(fiscalData?.summary?.tip_amount || 0)).toFixed(2)}</span></div>
                  )}
                  
                  <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 'bold' }}>
                    <span>TOTAL ({currency})</span>
                    <span>*{(Number(fiscalData?.summary?.grand_total || 0) + Number(fiscalData?.summary?.tip_amount || 0)).toFixed(2)}</span>
                  </div>
                </div>

                <div className="dashed-divider" style={{ borderTop: '1px dashed #000', margin: '5px 0' }} />

                <div className="centered" style={{ textAlign: 'center', marginTop: '10px', fontSize: '10px' }}>
                  <p style={{ margin: '2px 0' }}>*** NON-FISCAL ***</p>
                  <p style={{ margin: '2px 0', fontWeight: 'bold' }}>FISCAL DATA SECURE</p>
                  <p style={{ margin: '2px 0' }}>FS NO: {fiscalData?.fiscalNumber || 'NF00006105'}</p>
                  <p style={{ margin: '2px 0' }}>MACHINE: {fiscalData?.machineId || 'FG10004841'}</p>
                  <p style={{ margin: '10px 0 0 0', fontWeight: 'bold' }}>*** THANK YOU ***</p>
                </div>
              </div>

              <div style={styles.modalButtons}>
                <button onClick={handlePrint} style={styles.modalPrintBtn}>
                  Print Receipt
                </button>
                <button onClick={() => setShowReceipt(false)} style={styles.modalCloseBtn}>
                  Close Window
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
    position: 'relative',
    fontFamily: "'Plus Jakarta Sans', sans-serif",
  },
  backgroundAuraA: {
    position: 'absolute',
    top: -100,
    right: -100,
    width: 350,
    height: 350,
    background: 'radial-gradient(circle, rgba(15, 118, 110, 0.08) 0%, rgba(255,255,255,0) 70%)',
    zIndex: 0,
    pointerEvents: 'none'
  },
  backgroundAuraB: {
    position: 'absolute',
    bottom: -100,
    left: -100,
    width: 300,
    height: 300,
    background: 'radial-gradient(circle, rgba(37, 99, 235, 0.06) 0%, rgba(255,255,255,0) 70%)',
    zIndex: 0,
    pointerEvents: 'none'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    zIndex: 1,
  },
  kicker: {
    color: '#0f766e',
    fontWeight: 900,
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: '0.12em',
    marginBottom: 4
  },
  title: {
    margin: 0,
    fontSize: 28,
    fontWeight: 800,
    color: '#0f172a',
    letterSpacing: '-0.02em'
  },
  refreshBtn: {
    backgroundColor: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: 12,
    width: 40,
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    color: '#64748b',
    transition: 'all 0.2s',
    boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)'
  },
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    gap: 16,
    zIndex: 1,
  },
  metricCard: {
    background: 'rgba(255, 255, 255, 0.8)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(226, 232, 240, 0.8)',
    borderRadius: 20,
    padding: '18px 20px',
    display: 'flex',
    gap: 14,
    alignItems: 'center',
    boxShadow: '0 10px 25px -5px rgba(0,0,0,0.03)'
  },
  metricIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  metricLabel: {
    fontSize: 12,
    color: '#64748b',
    fontWeight: '700'
  },
  metricValue: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0f172a',
    marginTop: 2
  },
  contentGrid: {
    display: 'grid',
    gridTemplateColumns: '1.2fr 1fr',
    gap: 20,
    zIndex: 1,
  },
  panel: {
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(226, 232, 240, 0.8)',
    borderRadius: 24,
    padding: 20,
    boxShadow: '0 20px 40px -15px rgba(0,0,0,0.04)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16
  },
  filterBar: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap'
  },
  searchBox: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    flex: 1,
    minWidth: 240
  },
  searchInput: {
    width: '100%',
    padding: '10px 14px 10px 38px',
    border: '1px solid #e2e8f0',
    borderRadius: 14,
    fontSize: 13,
    backgroundColor: '#ffffff',
    outline: 'none',
    transition: 'all 0.2s',
    fontFamily: 'inherit'
  },
  dateFilters: {
    display: 'flex',
    alignItems: 'center',
    gap: 8
  },
  dateField: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: 12,
    padding: '6px 10px',
    gap: 6
  },
  dateInput: {
    border: 'none',
    outline: 'none',
    fontSize: 12,
    color: '#334155',
    fontFamily: 'inherit'
  },
  tabsRow: {
    display: 'flex',
    gap: 6,
    overflowX: 'auto',
    paddingBottom: 4,
    borderBottom: '1px solid #e2e8f0'
  },
  tabBtn: {
    border: 'none',
    background: 'none',
    padding: '6px 12px',
    fontSize: 12,
    fontWeight: '700',
    color: '#64748b',
    borderRadius: 8,
    cursor: 'pointer',
    textTransform: 'capitalize',
    whiteSpace: 'nowrap',
    transition: 'all 0.15s'
  },
  tabBtnActive: {
    backgroundColor: '#0f766e',
    color: '#ffffff'
  },
  ordersList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    maxHeight: 520,
    overflowY: 'auto',
    paddingRight: 4
  },
  orderCard: {
    backgroundColor: '#ffffff',
    border: '1px solid #f1f5f9',
    borderRadius: 16,
    padding: 14,
    cursor: 'pointer',
    transition: 'all 0.2s',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    boxShadow: '0 2px 4px rgba(0,0,0,0.01)'
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  orderId: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0f172a'
  },
  statusBadge: {
    padding: '2px 8px',
    borderRadius: 20,
    fontSize: 10,
    fontWeight: 'bold',
    textTransform: 'uppercase'
  },
  cardBody: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap'
  },
  cardMeta: {
    fontSize: 12,
    color: '#64748b'
  },
  cardFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTop: '1px solid #f8fafc',
    paddingTop: 8
  },
  cardItemCount: {
    fontSize: 11,
    color: '#94a3b8',
    fontWeight: '600'
  },
  cardPrice: {
    fontSize: 13,
    fontWeight: '800',
    color: '#0f766e'
  },
  detailsPanel: {
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(226, 232, 240, 0.8)',
    borderRadius: 24,
    padding: 20,
    boxShadow: '0 20px 40px -15px rgba(0,0,0,0.04)',
  },
  detailsHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #f1f5f9',
    paddingBottom: 12
  },
  detailsTitle: {
    margin: 0,
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a'
  },
  detailsSubtitle: {
    fontSize: 12,
    color: '#64748b'
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  detailsContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    marginTop: 16,
    overflowY: 'auto',
    maxHeight: 520,
    paddingRight: 4
  },
  metaBox: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 8,
    backgroundColor: '#f8fafc',
    padding: 12,
    borderRadius: 14,
  },
  metaItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    color: '#334155'
  },
  itemsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10
  },
  sectionHeader: {
    fontSize: 13,
    fontWeight: '800',
    color: '#475569',
    textTransform: 'uppercase',
    letterSpacing: '0.04em'
  },
  itemsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  itemRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    border: '1px solid #f1f5f9',
    padding: '8px 12px',
    borderRadius: 10
  },
  itemNameCol: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1
  },
  itemName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a'
  },
  itemPriceDetail: {
    fontSize: 10,
    color: '#94a3b8'
  },
  itemQty: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#334155',
    marginRight: 16
  },
  itemTotal: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a'
  },
  billingSection: {
    borderTop: '1px dashed #cbd5e1',
    borderBottom: '1px dashed #cbd5e1',
    padding: '12px 0',
    display: 'flex',
    flexDirection: 'column',
    gap: 6
  },
  billRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 12,
    color: '#64748b'
  },
  billTotalRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 14,
    fontWeight: '800',
    color: '#0f766e',
    marginTop: 4
  },
  actionsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10
  },
  actionBtnGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  actionBtn: {
    border: 'none',
    backgroundColor: '#0f766e',
    color: '#ffffff',
    borderRadius: 12,
    padding: 12,
    fontWeight: '700',
    fontSize: 13,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    transition: 'opacity 0.2s',
  },
  cancelOrderBtn: {
    border: '1px solid #fca5a5',
    backgroundColor: '#fffbeb',
    color: '#b91c1c',
    borderRadius: 12,
    padding: 10,
    fontWeight: '700',
    fontSize: 12,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  paymentBox: {
    backgroundColor: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: 14,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  payMethods: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 6
  },
  payMethodBtn: {
    border: '1px solid #cbd5e1',
    borderRadius: 8,
    padding: '6px 4px',
    fontSize: 11,
    fontWeight: '700',
    cursor: 'pointer',
    outline: 'none',
    transition: 'all 0.2s'
  },
  payInput: {
    padding: '8px 10px',
    fontSize: 11,
    borderRadius: 8,
    border: '1px solid #cbd5e1',
    outline: 'none',
    fontFamily: 'inherit'
  },
  payConfirmBtn: {
    border: 'none',
    backgroundColor: '#16a34a',
    color: '#ffffff',
    borderRadius: 10,
    padding: 10,
    fontSize: 12,
    fontWeight: '700',
    cursor: 'pointer'
  },
  printSection: {
    backgroundColor: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: 14,
    padding: 14,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 10
  },
  printReceiptBtn: {
    border: 'none',
    backgroundColor: '#0f172a',
    color: '#ffffff',
    borderRadius: 10,
    padding: '10px 16px',
    fontWeight: '700',
    fontSize: 12,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 6
  },
  centeredState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '240px',
    color: '#94a3b8'
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '240px',
    color: '#94a3b8',
    textAlign: 'center'
  },
  spinner: {
    width: 28,
    height: 28,
    border: '3px solid rgba(15, 118, 110, 0.1)',
    borderTop: '3px solid #0f766e',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite'
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.4)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    padding: 20
  },
  receiptModal: {
    backgroundColor: '#ffffff',
    borderRadius: 24,
    padding: 20,
    maxWidth: 380,
    width: '100%',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16
  },
  thermalContainer: {
    maxHeight: 420,
    overflowY: 'auto',
    padding: '10px 14px',
    border: '1px solid #f1f5f9',
    borderRadius: 12,
    fontFamily: "'Courier New', Courier, monospace",
    backgroundColor: '#fafafa',
    color: '#000000'
  },
  modalButtons: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  modalPrintBtn: {
    border: 'none',
    backgroundColor: '#0f766e',
    color: '#ffffff',
    borderRadius: 12,
    padding: 12,
    fontWeight: '800',
    fontSize: 13,
    cursor: 'pointer'
  },
  modalCloseBtn: {
    border: '1px solid #cbd5e1',
    backgroundColor: '#ffffff',
    color: '#475569',
    borderRadius: 12,
    padding: 12,
    fontWeight: '700',
    fontSize: 13,
    cursor: 'pointer'
  }
};
