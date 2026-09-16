import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { API_BASE_URL, BASE_URL } from './apiConfig';
import {
  LayoutDashboard, ShoppingCart, Utensils,
  Tags, TableProperties, BedDouble, Users,
  Settings, ChevronDown, CalendarDays,
  ClipboardList, FileBarChart2, Package, TrendingUp,
  Hotel, BookOpen, Moon, BarChart2, Shield, BarChart3,
  Activity, Layers, BookMarked, X
} from 'lucide-react';

// ── Menu structure with section groupings ─────────────────────────────────────
const menuGroups = [
  {
    section: 'OVERVIEW',
    items: [
      { id: 'dashboard', title: 'Dashboard',       icon: <LayoutDashboard size={17} />, pkg: 'dashboard' },
      { id: 'orders',    title: 'Orders',           icon: <ShoppingCart    size={17} />, pkg: 'orders'    },
    ]
  },
  {
    section: 'OPERATIONS',
    items: [
      {
        id: 'food_beverage',
        title: 'Food & Beverage',
        icon: <Utensils size={17} />,
        pkg: 'food_beverage',
        children: [
          { id: 'menus',      title: 'Menus',       icon: <BookOpen        size={15} /> },
          { id: 'categories', title: 'Categories',  icon: <Tags            size={15} /> },
          { id: 'tables',     title: 'Tables',      icon: <TableProperties size={15} /> },
        ]
      },
      {
        id: 'rooms_pkg',
        title: 'Front Office & Rooms',
        icon: <Hotel size={17} />,
        pkg: 'rooms',
        children: [
          { id: 'rooms',               title: 'Rooms',                icon: <BedDouble     size={15} /> },
          { id: 'reservation_booking', title: 'Reservations',         icon: <CalendarDays  size={15} /> },
          { id: 'checkin_checkout',    title: 'Check In / Check Out', icon: <Users         size={15} /> },
          { id: 'night_audit',         title: 'Night Audit',          icon: <Moon          size={15} /> },
          { id: 'bookings',            title: 'Bookings Manager',     icon: <ClipboardList size={15} /> },
          { id: 'reports',             title: 'Reports Center',       icon: <FileBarChart2 size={15} /> },
        ]
      },
      { id: 'inventory', title: 'Inventory Control', icon: <Package size={17} /> },
    ]
  },
  {
    section: 'FINANCE',
    items: [
      { id: 'finance', title: 'Finance & Accounts', icon: <TrendingUp size={17} />, pkg: 'finance' },
    ]
  },
  {
    section: 'REPORTS',
    items: [
      {
        id: 'all_reports',
        title: 'All Reports',
        icon: <BarChart3 size={17} />,
        children: [
          { id: 'report_police',    title: 'Police Report',       icon: <Shield        size={15} /> },
          { id: 'report_xreport',  title: 'X-Report (Daily)',     icon: <Activity      size={15} /> },
          { id: 'report_zreport',  title: 'Z-Report (Close Day)', icon: <BarChart2     size={15} /> },
          { id: 'report_occupancy',title: 'Occupancy & Revenue',  icon: <Hotel         size={15} /> },
          { id: 'report_bookings', title: 'Bookings Report',      icon: <BookMarked    size={15} /> },
          { id: 'report_inventory',title: 'Inventory Report',     icon: <Layers        size={15} /> },
        ]
      },
    ]
  },
  {
    section: 'ADMIN',
    items: [
      { id: 'users',    title: 'Users',    icon: <Users    size={17} />, pkg: 'users'    },
      { id: 'settings', title: 'Settings', icon: <Settings size={17} />, pkg: 'settings' },
    ]
  },
];

// ── Color palette for icon backgrounds ────────────────────────────────────────
const iconColors = {
  dashboard:    { bg: 'rgba(99,102,241,0.14)',  color: '#818cf8' },
  orders:       { bg: 'rgba(34,211,238,0.14)',  color: '#22d3ee' },
  food_beverage:{ bg: 'rgba(251,146,60,0.14)',  color: '#fb923c' },
  rooms_pkg:    { bg: 'rgba(139,92,246,0.14)',  color: '#a78bfa' },
  inventory:    { bg: 'rgba(251,191,36,0.14)',  color: '#fbbf24' },
  finance:      { bg: 'rgba(52,211,153,0.14)',  color: '#34d399' },
  all_reports:  { bg: 'rgba(244,63,94,0.14)',   color: '#fb7185' },
  users:        { bg: 'rgba(96,165,250,0.14)',  color: '#60a5fa' },
  settings:     { bg: 'rgba(148,163,184,0.16)', color: '#94a3b8' },
};

// ─────────────────────────────────────────────────────────────────────────────
const Sidebar = ({ activeTab, setActiveTab, handleLogout, isOpen, setIsOpen }) => {
  const [hotelSettings, setHotelSettings] = useState(null);
  const [openSubmenu, setOpenSubmenu]     = useState(null);
  const [isMobile, setIsMobile]           = useState(window.innerWidth <= 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const savedUser = localStorage.getItem('user');
  const userRole  = savedUser ? JSON.parse(savedUser).role?.toLowerCase().trim() : null;

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      axios.get(`${API_BASE_URL}/users/settings/`, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(res => {
          const data = Array.isArray(res.data) ? res.data[0] : res.data;
          setHotelSettings(data);
        })
        .catch(err => console.error('Failed to load hotel settings:', err));
    }
  }, []);

  // Auto-open submenu if a child is currently active
  useEffect(() => {
    menuGroups.forEach(group => {
      group.items.forEach(item => {
        if (item.children?.some(c => c.id === activeTab)) {
          setOpenSubmenu(item.id);
        }
      });
    });
  }, [activeTab]);

  const enabledFeatures = hotelSettings?.enabled_features?.length > 0
    ? hotelSettings.enabled_features
    : ['dashboard', 'orders', 'finance', 'food_beverage', 'rooms', 'inventory', 'users', 'settings'];

  const toggleSubmenu = (id) => setOpenSubmenu(openSubmenu === id ? null : id);

  const isItemVisible = (item) => {
    if (item.pkg) {
      const enabled = enabledFeatures.includes(item.pkg) ||
        (item.pkg === 'finance' && enabledFeatures.includes('payments'));
      if (!enabled) return false;
    }
    if (userRole === 'finance' && !['dashboard', 'finance', 'inventory'].includes(item.id)) return false;
    return true;
  };

  const hotelName    = hotelSettings?.hotel_name || 'Smart Hotel';
  const hotelNameArr = hotelName.split(' ');
  const firstName    = hotelNameArr[0];
  const restName     = hotelNameArr.slice(1).join(' ');

  return (
    <div
      style={sidebarStyle}
      className={`sidebar-container no-print ${isOpen ? 'open' : ''}`}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700&display=swap');

        .sb-nav::-webkit-scrollbar { width: 3px; }
        .sb-nav::-webkit-scrollbar-track { background: transparent; }
        .sb-nav::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.18); border-radius: 99px; }
        .sb-nav::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.35); }

        .sb-item { transition: all 0.18s ease; }
        .sb-item:hover .sb-icon-wrap { transform: scale(1.08); }
      `}</style>

      {/* ── LOGO / BRAND ─────────────────────────────────────────────────── */}
      <div style={logoSectionStyle}>
        {isMobile && (
          <button
            onClick={() => setIsOpen && setIsOpen(false)}
            style={{
              position: 'absolute', top: '16px', right: '16px',
              background: 'none', border: 'none', color: '#94a3b8',
              cursor: 'pointer', padding: '6px', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '50%'
            }}
          >
            <X size={18} />
          </button>
        )}
        {hotelSettings?.logo ? (
          <motion.img
            whileHover={{ scale: 1.06, rotate: 4 }}
            src={hotelSettings.logo.startsWith('http') ? hotelSettings.logo : `${BASE_URL}${hotelSettings.logo}`}
            alt="Hotel Logo"
            style={{
              width: '58px', height: '58px', borderRadius: '16px', objectFit: 'cover',
              marginBottom: '12px', border: '2.5px solid rgba(99,102,241,0.5)',
              boxShadow: '0 6px 20px rgba(99,102,241,0.25)', backgroundColor: '#fff'
            }}
          />
        ) : (
          <div style={{
            width: '58px', height: '58px', borderRadius: '16px',
            background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '12px', boxShadow: '0 6px 20px rgba(99,102,241,0.35)',
            fontSize: '24px', fontWeight: '900', color: '#fff',
            fontFamily: "'Playfair Display', serif"
          }}>
            {firstName?.charAt(0) || 'H'}
          </div>
        )}
        <h1 style={logoStyle}>
          <span style={{ color: '#e2e8f0' }}>{firstName}</span>
          {restName && <span style={{ color: '#818cf8' }}> {restName}</span>}
        </h1>
        <div style={erpBadgeStyle}>
          <span>ERP</span>
          <span style={{ width: '4px', height: '4px', borderRadius: '50%', backgroundColor: '#34d399', display: 'inline-block', margin: '0 5px' }} />
          <span>SYSTEM</span>
        </div>
      </div>

      {/* ── NAVIGATION ───────────────────────────────────────────────────── */}
      <nav style={navStyle} className="sb-nav">
        {menuGroups.map((group) => {
          const visibleItems = group.items.filter(isItemVisible);
          if (visibleItems.length === 0) return null;

          return (
            <div key={group.section} style={{ marginBottom: '6px' }}>
              {visibleItems.map((item) => {
                const isDirectActive = activeTab === item.id;
                const isParentActive = item.children?.some(c => c.id === activeTab);
                const isActive       = isDirectActive || isParentActive;
                const isSubmenuOpen  = openSubmenu === item.id;
                const ic             = iconColors[item.id] || { bg: 'rgba(148,163,184,0.12)', color: '#94a3b8' };

                return (
                  <div key={item.id} style={{ marginBottom: '2px' }}>
                    {/* ── Main nav item ──────────────────────────────────── */}
                    <motion.div
                      className="sb-item"
                      onClick={() => {
                        if (item.children) {
                          toggleSubmenu(item.id);
                        } else {
                          setActiveTab(item.id);
                          if (setIsOpen) setIsOpen(false);
                        }
                      }}
                      whileTap={{ scale: 0.97 }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '9px 10px',
                        borderRadius: '12px',
                        cursor: 'pointer',
                        position: 'relative',
                        background: isDirectActive && !item.children
                          ? 'linear-gradient(135deg, #6366f1 0%, #818cf8 100%)'
                          : isParentActive
                            ? 'rgba(99,102,241,0.1)'
                            : 'transparent',
                        boxShadow: isDirectActive && !item.children
                          ? '0 4px 14px rgba(99,102,241,0.35)'
                          : 'none',
                      }}
                      whileHover={{
                        backgroundColor: isActive ? undefined : 'rgba(99,102,241,0.07)',
                      }}
                    >
                      {/* Active indicator bar */}
                      {isActive && (
                        <motion.div
                          layoutId="activeBar"
                          style={{
                            position: 'absolute', left: 0, top: '20%', bottom: '20%',
                            width: '3px', borderRadius: '0 3px 3px 0',
                            background: isDirectActive && !item.children ? '#fff' : '#6366f1',
                          }}
                        />
                      )}

                      {/* Icon box */}
                      <div
                        className="sb-icon-wrap"
                        style={{
                          width: '34px', height: '34px', borderRadius: '10px',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          flexShrink: 0,
                          backgroundColor: isDirectActive && !item.children ? 'rgba(255,255,255,0.2)' : ic.bg,
                          color: isDirectActive && !item.children ? '#ffffff' : ic.color,
                          transition: 'transform 0.18s ease'
                        }}
                      >
                        {item.icon}
                      </div>

                      {/* Title */}
                      <span style={{
                        marginLeft: '11px',
                        flex: 1,
                        fontSize: '13.5px',
                        fontWeight: isActive ? '700' : '500',
                        color: isDirectActive && !item.children
                          ? '#ffffff'
                          : isParentActive ? '#c7d2fe' : '#cbd5e1',
                        letterSpacing: '0.1px',
                        fontFamily: "'Plus Jakarta Sans', sans-serif",
                      }}>
                        {item.title}
                      </span>

                      {/* Chevron for parent items */}
                      {item.children && (
                        <motion.span
                          animate={{ rotate: isSubmenuOpen ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                          style={{ color: isParentActive ? '#818cf8' : '#475569', display: 'flex' }}
                        >
                          <ChevronDown size={14} />
                        </motion.span>
                      )}
                    </motion.div>

                    {/* ── Sub-items ──────────────────────────────────────── */}
                    <AnimatePresence initial={false}>
                      {item.children && isSubmenuOpen && (
                        <motion.div
                          key="sub"
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.22, ease: 'easeInOut' }}
                          style={{ overflow: 'hidden' }}
                        >
                          <div style={{
                            marginLeft: '16px',
                            marginTop: '3px',
                            marginBottom: '4px',
                            paddingLeft: '12px',
                            borderLeft: '1.5px solid rgba(99,102,241,0.2)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '1px'
                          }}>
                            {item.children.map(child => {
                              const isChildActive = activeTab === child.id;
                              return (
                                <motion.div
                                  key={child.id}
                                  onClick={() => {
                                    setActiveTab(child.id);
                                    if (setIsOpen) setIsOpen(false);
                                  }}
                                  whileHover={{ x: 3, backgroundColor: isChildActive ? undefined : 'rgba(99,102,241,0.07)' }}
                                  whileTap={{ scale: 0.97 }}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    padding: '8px 10px',
                                    borderRadius: '9px',
                                    cursor: 'pointer',
                                    background: isChildActive
                                      ? 'linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(129,140,248,0.1) 100%)'
                                      : 'transparent',
                                    border: isChildActive
                                      ? '1px solid rgba(99,102,241,0.25)'
                                      : '1px solid transparent',
                                  }}
                                >
                                  <span style={{
                                    color: isChildActive ? '#818cf8' : '#64748b',
                                    display: 'inline-flex', alignItems: 'center',
                                    transition: 'color 0.15s'
                                  }}>
                                    {child.icon}
                                  </span>
                                  <span style={{
                                    marginLeft: '9px',
                                    fontSize: '12.5px',
                                    fontWeight: isChildActive ? '700' : '500',
                                    color: isChildActive ? '#c7d2fe' : '#94a3b8',
                                    fontFamily: "'Plus Jakarta Sans', sans-serif",
                                  }}>
                                    {child.title}
                                  </span>
                                  {isChildActive && (
                                    <div style={{
                                      marginLeft: 'auto',
                                      width: '6px', height: '6px', borderRadius: '50%',
                                      backgroundColor: '#818cf8',
                                      boxShadow: '0 0 6px rgba(129,140,248,0.8)'
                                    }} />
                                  )}
                                </motion.div>
                              );
                            })}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          );
        })}
      </nav>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const sidebarStyle = {
  width: '258px',
  height: '100vh',
  background: 'linear-gradient(180deg, #0f172a 0%, #111827 60%, #0f172a 100%)',
  color: '#e2e8f0',
  position: 'fixed',
  left: 0,
  top: 0,
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '6px 0 40px rgba(0,0,0,0.35)',
  zIndex: 100,
  borderRight: '1px solid rgba(99,102,241,0.12)',
  fontFamily: "'Plus Jakarta Sans', sans-serif",
};

const logoSectionStyle = {
  padding: '26px 20px 20px',
  textAlign: 'center',
  borderBottom: '1px solid rgba(99,102,241,0.1)',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  background: 'linear-gradient(180deg, rgba(99,102,241,0.06) 0%, transparent 100%)',
};

const logoStyle = {
  fontFamily: "'Playfair Display', serif",
  margin: 0,
  fontSize: '18px',
  fontWeight: '800',
  letterSpacing: '0.3px',
  lineHeight: '1.25',
};

const erpBadgeStyle = {
  display: 'flex',
  alignItems: 'center',
  marginTop: '8px',
  padding: '3px 10px',
  borderRadius: '20px',
  backgroundColor: 'rgba(99,102,241,0.12)',
  border: '1px solid rgba(99,102,241,0.2)',
  fontSize: '9px',
  fontWeight: '700',
  color: '#818cf8',
  letterSpacing: '1.5px',
  textTransform: 'uppercase',
};

const navStyle = {
  padding: '14px 10px',
  flex: 1,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
};

export default Sidebar;
