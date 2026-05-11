import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { QRCodeSVG } from 'qrcode.react';
import {
  Bell,
  CheckCircle2,
  ChefHat,
  CreditCard,
  Grid2x2,
  Info,
  LoaderCircle,
  Menu,
  Minus,
  Plus,
  Receipt,
  Search,
  Send,
  ShoppingBag,
  Trash2,
  User,
  UtensilsCrossed,
  Wallet,
  X,
} from 'lucide-react';
import { API_BASE_URL, BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

function WaiterDashboard({ userData, handleLogout }) {
  const [activeTab, setActiveTab] = useState('home');
  const [orders, setOrders] = useState([]);
  const [tables, setTables] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [categories, setCategories] = useState(['All']);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [cart, setCart] = useState([]);
  const [selectedTableId, setSelectedTableId] = useState('');
  const [detailsOrder, setDetailsOrder] = useState(null);
  const [checkoutOrder, setCheckoutOrder] = useState(null);
  const [checkoutSummary, setCheckoutSummary] = useState(null);
  const [paymentChoice, setPaymentChoice] = useState('Cash');
  const [digitalSession, setDigitalSession] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const prevNotifCount = useRef(0);

  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const [filterLimit, setFilterLimit] = useState(10);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('access_token')}` });
  const isMobile = windowWidth < 960;

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStartDate, filterEndDate, filterLimit]);

  const loadAllData = async () => {
    await Promise.all([fetchInitialData(), fetchDashboardData(), fetchNotifications()]);
  };

  const fetchInitialData = async () => {
    try {
      const res = await axios.get(`${API_BASE}categories/`, { headers: headers() });
      setCategories(['All', ...(res.data || []).map((cat) => cat.name)]);
    } catch (err) {
      console.error('Category fetch failed', err);
    }
  };

  const fetchDashboardData = async () => {
    try {
      const [resOrders, resTables, resMenu] = await Promise.all([
        axios.get(`${API_BASE}waiter/my-orders/?start_date=${filterStartDate}&end_date=${filterEndDate}&limit=${filterLimit}`, { headers: headers() }),
        axios.get(`${API_BASE}manage/`, { headers: headers() }),
        axios.get(`${API_BASE}menu-items/`, { headers: headers() }),
      ]);
      setOrders(resOrders.data || []);
      setTables(resTables.data || []);
      setMenuItems(resMenu.data || []);
    } catch (err) {
      console.error('Dashboard fetch failed', err);
    }
  };

  const fetchNotifications = async () => {
    try {
      const res = await axios.get(`${API_BASE}notifications/`, { headers: headers() });
      const nextNotifications = res.data || [];
      if (nextNotifications.length > prevNotifCount.current) {
        new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3').play().catch(() => {});
      }
      prevNotifCount.current = nextNotifications.length;
      setNotifications(nextNotifications);
    } catch (err) {
      console.error('Notification fetch failed', err);
    }
  };

  const openCheckout = async (order) => {
    setCheckoutOrder(order);
    setDigitalSession(null);
    setPaymentChoice('Cash');
    setIsBusy(true);
    try {
      const res = await axios.get(`${API_BASE}orders/${order.id}/payment-summary/`, { headers: headers() });
      setCheckoutSummary(res.data);
    } catch (err) {
      alert(err.response?.data?.error || 'Unable to load payment summary.');
    } finally {
      setIsBusy(false);
    }
  };

  const closeCheckout = () => {
    setCheckoutOrder(null);
    setCheckoutSummary(null);
    setDigitalSession(null);
    setPaymentChoice('Cash');
  };

  const confirmCashPayment = async () => {
    if (!checkoutOrder) return;
    setIsBusy(true);
    try {
      await axios.post(`${API_BASE}orders/${checkoutOrder.id}/cash-payment/`, {}, { headers: headers() });
      alert('Cash payment recorded successfully.');
      closeCheckout();
      await loadAllData();
    } catch (err) {
      alert(err.response?.data?.error || 'Cash payment failed');
    } finally {
      setIsBusy(false);
    }
  };

  const generateDigitalSession = async () => {
    if (!checkoutOrder) return;
    setIsBusy(true);
    try {
      const res = await axios.post(`${API_BASE}orders/${checkoutOrder.id}/digital-session/`, {}, { headers: headers() });
      setDigitalSession(res.data);
    } catch (err) {
      alert(err.response?.data?.error || 'Unable to create digital session');
    } finally {
      setIsBusy(false);
    }
  };

  const markServed = async (orderId) => {
    try {
      await axios.post(`${API_BASE}orders/${orderId}/mark-served/`, {}, { headers: headers() });
      await loadAllData();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to mark order as served.');
    }
  };

  const clearAllNotifications = async () => {
    if (!notifications.length) return;
    try {
      await axios.delete(`${API_BASE}notifications/`, { headers: headers() });
      setNotifications([]);
      prevNotifCount.current = 0;
    } catch (err) {
      alert('Unable to clear notifications.');
    }
  };

  const removeNotification = async (id) => {
    try {
      await axios.delete(`${API_BASE}notifications/${id}/`, { headers: headers() });
      const next = notifications.filter((note) => note.id !== id);
      setNotifications(next);
      prevNotifCount.current = next.length;
    } catch (err) {
      alert('Unable to remove notification.');
    }
  };

  const sendToKitchen = async () => {
    if (!cart.length || !selectedTableId) {
      alert('Select a table and at least one item.');
      return;
    }
    setIsBusy(true);
    try {
      await axios.post(
        `${API_BASE}orders/create/`,
        {
          table_id: selectedTableId,
          items: cart.map((item) => ({ id: item.id, quantity: item.quantity })),
        },
        { headers: headers() }
      );
      setCart([]);
      setSelectedTableId('');
      await loadAllData();
      setActiveTab('orders');
    } catch (err) {
      alert(err.response?.data?.error || 'Unable to send order to kitchen.');
    } finally {
      setIsBusy(false);
    }
  };

  const addToCart = (item) => {
    const existing = cart.find((cartItem) => cartItem.id === item.id);
    if (existing) {
      setCart(cart.map((cartItem) => cartItem.id === item.id ? { ...cartItem, quantity: cartItem.quantity + 1 } : cartItem));
      return;
    }
    setCart([...cart, { ...item, quantity: 1 }]);
  };

  const updateQty = (id, delta) => {
    setCart(
      cart
        .map((item) => item.id === id ? { ...item, quantity: Math.max(0, item.quantity + delta) } : item)
        .filter((item) => item.quantity > 0)
    );
  };

  const cartTotal = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.price || 0) * item.quantity, 0),
    [cart]
  );

  const filteredMenu = useMemo(
    () =>
      menuItems.filter((item) => {
        const byCategory = selectedCategory === 'All' || item.category_name === selectedCategory;
        const bySearch = item.name.toLowerCase().includes(searchQuery.toLowerCase());
        return byCategory && bySearch;
      }),
    [menuItems, searchQuery, selectedCategory]
  );

  const activeOrders = useMemo(
    () => orders.filter((order) => !['paid', 'cancelled'].includes(order.status)),
    [orders]
  );
  const readyOrders = useMemo(() => orders.filter((order) => order.status === 'ready'), [orders]);
  const payableOrders = useMemo(
    () => orders.filter((order) => order.status === 'served' && order.payment_status !== 'paid'),
    [orders]
  );
  const paidOrders = useMemo(() => orders.filter((order) => order.payment_status === 'paid'), [orders]);
  const occupiedTables = useMemo(() => tables.filter((table) => table.status === 'occupied'), [tables]);
  const availableTables = useMemo(() => tables.filter((table) => table.status !== 'occupied'), [tables]);
  const topMenuItems = useMemo(() => filteredMenu.slice(0, 8), [filteredMenu]);
  const pendingNotifications = notifications.slice(0, 5);
  const selectedTableLabel = tables.find((table) => String(table.id) === String(selectedTableId))?.table_code;

  const navItems = [
    { id: 'home', label: 'Overview', icon: Grid2x2 },
    { id: 'orders', label: 'Orders', icon: Receipt },
    { id: 'menu', label: 'Menu', icon: ShoppingBag },
    { id: 'notifications', label: 'Alerts', icon: Bell },
    { id: 'tips', label: 'Tips', icon: Wallet },
  ];

  return (
    <div style={styles.page}>
      <div style={styles.backgroundAuraA} />
      <div style={styles.backgroundAuraB} />

      <header style={styles.topBar}>
        <div style={styles.brandBlock}>
          <div style={styles.brandIcon}>W</div>
          <div>
            <div style={styles.brandTitle}>Waiter Command</div>
            <div style={styles.brandSub}>Dining floor operations and digital checkout</div>
          </div>
        </div>

        {isMobile ? (
          <button style={styles.iconButton} onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
            {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        ) : null}

        <div style={{ ...styles.topActions, ...(isMobile && !mobileMenuOpen ? styles.hiddenMobile : {}) }}>
          <div style={styles.alertPill}>
            <Bell size={15} />
            <span>{notifications.length} alerts</span>
          </div>
          <div style={styles.userPill}>
            <User size={15} />
            <span>{userData?.first_name || 'Waiter'}</span>
          </div>
          <button style={styles.logoutButton} onClick={handleLogout}>Logout</button>
        </div>
      </header>

      <div style={styles.layout}>
        <aside style={{ ...styles.sidebar, ...(isMobile && !mobileMenuOpen ? styles.hiddenMobile : {}) }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setMobileMenuOpen(false);
                }}
                style={activeTab === item.id ? styles.sidebarItemActive : styles.sidebarItem}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}

          <div style={styles.sidebarCard}>
            <div style={styles.sidebarCardLabel}>Shift Snapshot</div>
            <div style={styles.sidebarBigNumber}>{activeOrders.length}</div>
            <div style={styles.sidebarMuted}>orders in motion</div>
            <div style={styles.sidebarStatRow}>
              <span>Ready</span>
              <strong>{readyOrders.length}</strong>
            </div>
            <div style={styles.sidebarStatRow}>
              <span>Awaiting pay</span>
              <strong>{payableOrders.length}</strong>
            </div>
          </div>
        </aside>

        <main style={styles.main}>
          {activeTab === 'home' && (
            <>
              <section style={styles.hero}>
                <div>
                  <div style={styles.sectionKicker}>Floor Overview</div>
                  <h1 style={styles.heroTitle}>Everything you need for service, billing, and digital payment in one place.</h1>
                  <p style={styles.heroText}>
                    Track ready orders, collect payments, and open QR checkout without leaving the waiter dashboard.
                  </p>
                  <div style={styles.heroActions}>
                    <button style={styles.primaryButton} onClick={() => setActiveTab('orders')}>
                      <Receipt size={16} />
                      Open Orders
                    </button>
                    <button style={styles.ghostButton} onClick={() => setActiveTab('menu')}>
                      <ShoppingBag size={16} />
                      Create Order
                    </button>
                  </div>
                </div>

                <div style={styles.heroPanel}>
                  <div style={styles.heroPanelTitle}>Payment Readiness</div>
                  {payableOrders.length ? payableOrders.slice(0, 3).map((order) => (
                    <button key={order.id} style={styles.quickOrderCard} onClick={() => openCheckout(order)}>
                      <div>
                        <strong>ORD-{order.id}</strong>
                        <div style={styles.smallMuted}>Table {order.table_code}</div>
                      </div>
                      <span style={styles.quickOrderAmount}>ETB {Number(order.total_amount || 0).toFixed(2)}</span>
                    </button>
                  )) : (
                    <div style={styles.emptyCard}>No payment-ready orders right now.</div>
                  )}
                </div>
              </section>

              <section style={styles.metricGrid}>
                <MetricCard icon={<UtensilsCrossed size={18} />} label="Active Orders" value={activeOrders.length} tone="cyan" />
                <MetricCard icon={<ChefHat size={18} />} label="Ready To Serve" value={readyOrders.length} tone="amber" />
                <MetricCard icon={<CreditCard size={18} />} label="Payment Queue" value={payableOrders.length} tone="green" />
                <MetricCard icon={<Bell size={18} />} label="Unread Alerts" value={notifications.length} tone="rose" />
              </section>

              <section style={styles.dualGrid}>
                <div style={styles.panel}>
                  <div style={styles.panelHeader}>
                    <div>
                      <div style={styles.panelTitle}>Live Tables</div>
                      <div style={styles.panelSub}>Current floor availability</div>
                    </div>
                    <span style={styles.panelBadge}>{tables.length} total</span>
                  </div>
                  <div style={styles.tableChipGrid}>
                    {tables.map((table) => (
                      <div key={table.id} style={table.status === 'occupied' ? styles.tableChipBusy : styles.tableChipFree}>
                        <span>{table.table_code}</span>
                        <strong>{table.status}</strong>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={styles.panel}>
                  <div style={styles.panelHeader}>
                    <div>
                      <div style={styles.panelTitle}>Recent Alerts</div>
                      <div style={styles.panelSub}>Kitchen and cashier messages</div>
                    </div>
                    <button style={styles.inlineButton} onClick={() => setActiveTab('notifications')}>Open all</button>
                  </div>
                  <div style={styles.stack}>
                    {pendingNotifications.length ? pendingNotifications.map((note) => (
                      <div key={note.id} style={styles.notificationRow}>
                        <div style={styles.notificationTextBlock}>
                          <strong style={styles.notificationTitle}>{note.message}</strong>
                          <span style={styles.notificationTime}>{new Date(note.created_at).toLocaleString()}</span>
                        </div>
                        <button style={styles.iconButton} onClick={() => removeNotification(note.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )) : <div style={styles.emptyCard}>No alerts at the moment.</div>}
                  </div>
                </div>
              </section>
            </>
          )}

          {activeTab === 'orders' && (
            <>
              <section style={styles.sectionHeaderRow}>
                <div>
                  <div style={styles.sectionKicker}>Order Desk</div>
                  <h2 style={styles.sectionTitle}>Actionable orders and payment flow</h2>
                </div>
                <button style={styles.ghostButton} onClick={loadAllData}>
                  <LoaderCircle size={15} />
                  Refresh
                </button>
              </section>

              <section style={styles.panel}>
                <div style={styles.orderSummaryRow}>
                  <MiniSummary label="Ready" value={readyOrders.length} />
                  <MiniSummary label="Served" value={orders.filter((order) => order.status === 'served').length} />
                  <MiniSummary label="Completed" value={paidOrders.length} />
                </div>
              </section>

              <section style={styles.panel}>
                <div style={styles.panelHeader}>
                  <div>
                    <div style={styles.panelTitle}>Order Workflow</div>
                    <div style={styles.panelSub}>Serve orders, launch checkout, and review history</div>
                  </div>
                </div>
                <div style={{ ...styles.filterRow, padding: '0 20px 15px 20px', marginTop: 0 }}>
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
                <div style={styles.orderList}>
                  {orders.length ? orders.map((order) => (
                    <div key={order.id} style={styles.orderCard}>
                      <div style={styles.orderCardTop}>
                        <div>
                          <strong style={styles.orderId}>ORD-{order.id}</strong>
                          <div style={styles.smallMuted}>Table {order.table_code}</div>
                        </div>
                        <div style={styles.badgeRow}>
                          <span style={statusBadge(order.status)}>{order.status}</span>
                          <span style={paymentBadge(order.payment_status)}>{order.payment_status || 'pending'}</span>
                        </div>
                      </div>

                      <div style={styles.orderStatsLine}>
                        <span>{order.items?.length || 0} items</span>
                        <span>Grand total ETB {(Number(order.total_amount || 0) + Number(order.tip_amount || 0)).toFixed(2)}</span>
                        <span>Tip ETB {Number(order.tip_amount || 0).toFixed(2)}</span>
                      </div>

                      <div style={styles.orderActionRow}>
                        {order.status === 'ready' ? (
                          <button style={styles.smallPrimary} onClick={() => markServed(order.id)}>Mark Served</button>
                        ) : null}
                        {order.status === 'served' && order.payment_status !== 'paid' ? (
                          <button style={styles.smallSuccess} onClick={() => openCheckout(order)}>Open Checkout</button>
                        ) : null}
                        <button style={styles.smallGhost} onClick={() => setDetailsOrder(order)}>Details</button>
                      </div>
                    </div>
                  )) : <div style={styles.emptyCard}>No orders found yet.</div>}
                </div>
              </section>
            </>
          )}

          {activeTab === 'menu' && (
            <section style={styles.menuGridLayout}>
              <div style={styles.panel}>
                <div style={styles.panelHeader}>
                  <div>
                    <div style={styles.panelTitle}>Menu Composer</div>
                    <div style={styles.panelSub}>Build a new order and send it to the kitchen</div>
                  </div>
                </div>

                <div style={styles.searchShell}>
                  <Search size={16} />
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={styles.searchInput}
                    placeholder="Search by item name"
                  />
                </div>

                <div style={styles.categoryRow}>
                  {categories.map((category) => (
                    <button
                      key={category}
                      style={selectedCategory === category ? styles.categoryButtonActive : styles.categoryButton}
                      onClick={() => setSelectedCategory(category)}
                    >
                      {category}
                    </button>
                  ))}
                </div>

                <div style={styles.menuCards}>
                  {topMenuItems.length ? topMenuItems.map((item) => (
                    <button key={item.id} style={styles.menuCard} onClick={() => addToCart(item)}>
                      <div style={styles.menuCardImageWrapper}>
                        {item.image ? (
                          <img 
                            src={item.image.startsWith('http') ? item.image : `http://127.0.0.1:8000${item.image}`} 
                            alt={item.name} 
                            style={styles.menuCardImage}
                          />
                        ) : (
                          <div style={styles.menuCardPlaceholder}>
                            <UtensilsCrossed size={36} color="#cbd5e1" />
                          </div>
                        )}
                      </div>
                      <div style={styles.menuCardContent}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                          <strong style={{ fontSize: '16px', color: '#0f172a', lineHeight: '1.2', fontWeight: 800 }}>{item.name}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                          <div style={styles.smallMuted}>{item.category_name || 'Menu'}</div>
                          <span style={styles.pricePill}>ETB {Number(item.price || 0).toFixed(2)}</span>
                        </div>
                      </div>
                    </button>
                  )) : <div style={styles.emptyCard}>No menu items match the current filter.</div>}
                </div>
              </div>

              <div style={styles.cartPanel}>
                <div style={styles.panelHeader}>
                  <div>
                    <div style={styles.panelTitle}>Order Cart</div>
                    <div style={styles.panelSub}>Selected table: {selectedTableLabel || 'Not selected'}</div>
                  </div>
                </div>

                <div style={styles.cartItems}>
                  {cart.length ? cart.map((item) => (
                    <div key={item.id} style={styles.cartItem}>
                      <div>
                        <strong>{item.name}</strong>
                        <div style={styles.smallMuted}>ETB {Number(item.price || 0).toFixed(2)} each</div>
                      </div>
                      <div style={styles.cartControls}>
                        <button style={styles.iconButton} onClick={() => updateQty(item.id, -1)}><Minus size={14} /></button>
                        <span style={styles.qtyValue}>{item.quantity}</span>
                        <button style={styles.iconButton} onClick={() => updateQty(item.id, 1)}><Plus size={14} /></button>
                        <button style={styles.iconButton} onClick={() => updateQty(item.id, -item.quantity)}><Trash2 size={14} /></button>
                      </div>
                    </div>
                  )) : <div style={styles.emptyCard}>Your cart is empty.</div>}
                </div>

                <select value={selectedTableId} onChange={(e) => setSelectedTableId(e.target.value)} style={styles.select}>
                  <option value="">Choose table...</option>
                  {availableTables.map((table) => (
                    <option key={table.id} value={table.id}>
                      {table.table_code}
                    </option>
                  ))}
                  {occupiedTables.length ? (
                    <optgroup label="Occupied tables">
                      {occupiedTables.map((table) => (
                        <option key={`busy-${table.id}`} value={table.id} disabled>
                          {table.table_code} (occupied)
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </select>

                <div style={styles.cartFooter}>
                  <div>
                    <div style={styles.smallMuted}>Cart Total</div>
                    <div style={styles.cartTotal}>ETB {cartTotal.toFixed(2)}</div>
                  </div>
                  <button style={styles.primaryButton} onClick={sendToKitchen} disabled={isBusy || !cart.length || !selectedTableId}>
                    <Send size={16} />
                    Send To Kitchen
                  </button>
                </div>
              </div>
            </section>
          )}

          {activeTab === 'notifications' && (
            <section style={styles.panel}>
              <div style={styles.panelHeader}>
                <div>
                  <div style={styles.panelTitle}>Alerts Center</div>
                  <div style={styles.panelSub}>Clear messages after you act on them</div>
                </div>
                <button style={styles.inlineButton} onClick={clearAllNotifications}>Clear all</button>
              </div>

              <div style={styles.stack}>
                {notifications.length ? notifications.map((note) => (
                  <div key={note.id} style={styles.notificationCard}>
                    <div style={styles.notificationTextBlock}>
                      <strong style={styles.notificationTitle}>{note.message}</strong>
                      <span style={styles.notificationTime}>{new Date(note.created_at).toLocaleString()}</span>
                    </div>
                    <button style={styles.iconButton} onClick={() => removeNotification(note.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                )) : <div style={styles.emptyCard}>No alerts right now.</div>}
              </div>
            </section>
          )}

          {activeTab === 'tips' && (
            <section style={styles.panel}>
              <div style={styles.panelHeader}>
                <div>
                  <div style={styles.panelTitle}>Tip History</div>
                  <div style={styles.panelSub}>Orders with tips collected</div>
                </div>
              </div>
              <div style={styles.stack}>
                {paidOrders.filter(o => parseFloat(o.tip_amount || 0) > 0).length ? (
                  paidOrders.filter(o => parseFloat(o.tip_amount || 0) > 0).map((order) => (
                    <div key={order.id} style={styles.orderCard}>
                      <div style={styles.orderCardTop}>
                        <div>
                          <strong style={styles.orderId}>ORD-{order.id}</strong>
                          <div style={styles.smallMuted}>Table {order.table_code}</div>
                        </div>
                        <div style={styles.badgeRow}>
                          <span style={{...styles.badge, color: '#166534', background: '#dcfce7', fontWeight: 'bold'}}>Tip: ETB {Number(order.tip_amount).toFixed(2)}</span>
                        </div>
                      </div>
                      <div style={styles.orderStatsLine}>
                        <span>Date: {order.created_at ? new Date(order.created_at).toLocaleDateString() : 'N/A'}</span>
                        <span>Grand total ETB {(Number(order.total_amount || 0) + Number(order.tip_amount || 0)).toFixed(2)}</span>
                      </div>
                    </div>
                  ))
                ) : <div style={styles.emptyCard}>No tip history available at the moment.</div>}
              </div>
            </section>
          )}
        </main>
      </div>

      {detailsOrder ? (
        <Modal title={`Order Details / ORD-${detailsOrder.id}`} onClose={() => setDetailsOrder(null)}>
          <div style={styles.stack}>
            {(detailsOrder.items || []).map((item) => (
              <div key={`${detailsOrder.id}-${item.id}`} style={styles.detailRow}>
                <span>{item.menu_item_name} x{item.quantity}</span>
                <strong>ETB {(item.quantity * item.price_at_order).toFixed(2)}</strong>
              </div>
            ))}
            <div style={styles.detailSummaryBox}>
              <div style={styles.detailRow}><span>Sub-total</span><strong>ETB {Number(detailsOrder.sub_total || 0).toFixed(2)}</strong></div>
              <div style={styles.detailRow}><span>Service Charge</span><strong>ETB {Number(detailsOrder.service_charge_amount || 0).toFixed(2)}</strong></div>
              <div style={styles.detailRow}><span>VAT</span><strong>ETB {Number(detailsOrder.vat_amount || 0).toFixed(2)}</strong></div>
              <div style={styles.detailRow}><span>Tip Amount</span><strong style={{color: '#10b981'}}>ETB {Number(detailsOrder.tip_amount || 0).toFixed(2)}</strong></div>
              {detailsOrder.payment_reference ? (
                <div style={styles.detailRow}><span>Transaction #</span><strong style={{fontSize: '12px', color: '#64748b', wordBreak: 'break-all'}}>{detailsOrder.payment_reference}</strong></div>
              ) : null}
              <div style={styles.detailTotal}><span>Grand Total</span><strong>ETB {(Number(detailsOrder.total_amount || 0) + Number(detailsOrder.tip_amount || 0)).toFixed(2)}</strong></div>
            </div>
          </div>
        </Modal>
      ) : null}

      {checkoutOrder ? (
        <Modal title={`Checkout / ORD-${checkoutOrder.id}`} onClose={closeCheckout}>
          {checkoutSummary ? (
            <div style={styles.stack}>
              <div style={styles.checkoutSummary}>
                <div style={styles.detailRow}><span>Sub-total</span><strong>ETB {Number(checkoutSummary.sub_total || 0).toFixed(2)}</strong></div>
                <div style={styles.detailRow}><span>VAT (15%)</span><strong>ETB {Number(checkoutSummary.vat || 0).toFixed(2)}</strong></div>
                <div style={styles.detailRow}><span>Service Charge (10%)</span><strong>ETB {Number(checkoutSummary.service_charge || 0).toFixed(2)}</strong></div>
                <div style={styles.detailTotal}><span>Grand Total</span><strong>ETB {Number(checkoutSummary.grand_total || 0).toFixed(2)}</strong></div>
              </div>

              <div style={styles.paymentChoiceRow}>
                <button style={paymentChoice === 'Cash' ? styles.paymentChoiceActive : styles.paymentChoice} onClick={() => setPaymentChoice('Cash')}>
                  <Wallet size={15} />
                  Cash
                </button>
                <button style={paymentChoice === 'Digital' ? styles.paymentChoiceActive : styles.paymentChoice} onClick={() => setPaymentChoice('Digital')}>
                  <CreditCard size={15} />
                  Digital Payment
                </button>
              </div>

              {paymentChoice === 'Cash' ? (
                <button style={styles.primaryButton} onClick={confirmCashPayment} disabled={isBusy}>
                  {isBusy ? <LoaderCircle size={16} /> : <Wallet size={16} />}
                  {isBusy ? 'Recording...' : 'Confirm Cash Payment'}
                </button>
              ) : (
                <div style={styles.stack}>
                  {!digitalSession ? (
                    <button style={styles.primaryButton} onClick={generateDigitalSession} disabled={isBusy}>
                      {isBusy ? <LoaderCircle size={16} /> : <CreditCard size={16} />}
                      {isBusy ? 'Preparing...' : 'Generate Payment QR'}
                    </button>
                  ) : (
                    <div style={styles.qrShell}>
                      <div style={styles.qrCard}>
                        <QRCodeSVG value={digitalSession.payment_page_url} size={188} />
                      </div>
                      <div style={styles.helperText}>
                        Customer scans this QR, sees the locked grand total, optionally adds a tip, then continues to Chapa.
                      </div>
                      <a href={digitalSession.payment_page_url} target="_blank" rel="noreferrer" style={styles.deepLink}>
                        Open payment page
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div style={styles.emptyCard}>Loading payment summary...</div>
          )}
        </Modal>
      ) : null}
    </div>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div style={styles.modalOverlay}>
      <div style={styles.modalCard}>
        <div style={styles.modalHeader}>
          <strong>{title}</strong>
          <button style={styles.iconButton} onClick={onClose}>
            <X size={15} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

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

function MiniSummary({ label, value }) {
  return (
    <div style={styles.miniSummary}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const statusBadge = (status) => {
  const palette = {
    pending: { color: '#92400e', background: '#fef3c7' },
    preparing: { color: '#1d4ed8', background: '#dbeafe' },
    ready: { color: '#9a3412', background: '#ffedd5' },
    served: { color: '#0f766e', background: '#ccfbf1' },
    bill_requested: { color: '#6d28d9', background: '#ede9fe' },
    paid: { color: '#166534', background: '#dcfce7' },
  };
  const token = palette[status] || { color: '#334155', background: '#e2e8f0' };
  return {
    ...styles.badge,
    color: token.color,
    background: token.background,
  };
};

const paymentBadge = (status) => ({
  ...styles.badge,
  color: status === 'paid' ? '#166534' : '#9a3412',
  background: status === 'paid' ? '#dcfce7' : '#ffedd5',
});

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
  menuCards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 20 },
  menuCard: {
    border: '1px solid rgba(148,163,184,0.1)',
    borderRadius: 24,
    background: '#fff',
    cursor: 'pointer',
    textAlign: 'left',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: '0 10px 30px rgba(15,23,42,0.04)',
    padding: 0,
    outline: 'none',
  },
  menuCardImageWrapper: {
    width: '100%',
    height: 140,
    background: '#f8fafc',
    position: 'relative',
    borderBottom: '1px solid rgba(148,163,184,0.1)',
  },
  menuCardImage: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  menuCardPlaceholder: {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuCardContent: {
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
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
    background: 'rgba(255,255,255,0.92)',
    border: '1px solid rgba(148,163,184,0.18)',
    borderRadius: 28,
    padding: 20,
    boxShadow: '0 18px 40px rgba(15,23,42,0.06)',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    position: 'sticky',
    top: 104,
  },
  cartItems: { display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 320, overflowY: 'auto' },
  cartItem: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'center',
    paddingBottom: 12,
    borderBottom: '1px solid #e2e8f0',
  },
  cartControls: { display: 'flex', alignItems: 'center', gap: 6 },
  qtyValue: { minWidth: 18, textAlign: 'center', fontWeight: 800 },
  select: {
    border: '1px solid #cbd5e1',
    borderRadius: 16,
    padding: '12px 14px',
    background: '#fff',
    fontSize: 14,
    outline: 'none',
  },
  cartFooter: { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' },
  cartTotal: { fontWeight: 900, fontSize: 24 },
  smallMuted: { color: '#64748b', fontSize: 12 },
  detailRow: { display: 'flex', justifyContent: 'space-between', gap: 12 },
  detailSummaryBox: {
    padding: 16,
    borderRadius: 18,
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
  },
  detailTotal: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    paddingTop: 10,
    marginTop: 10,
    borderTop: '1px dashed #cbd5e1',
    fontWeight: 900,
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

export default WaiterDashboard;