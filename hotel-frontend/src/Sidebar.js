import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';
import { API_BASE_URL, BASE_URL } from './apiConfig';
import {
  LayoutDashboard, ShoppingCart, CreditCard, Utensils,
  Tags, TableProperties, BedDouble, BarChart3, Users,
  Settings, LogOut, ChevronDown, ChevronRight, CalendarDays,
  ClipboardList, FileBarChart2
} from 'lucide-react';

const menuItems = [
  { id: 'dashboard', title: 'Dashboard', icon: <LayoutDashboard size={20}/>, pkg: 'dashboard' },
  { id: 'orders', title: 'Orders', icon: <ShoppingCart size={20}/>, pkg: 'orders' },
  { id: 'payments', title: 'Payments', icon: <CreditCard size={20}/>, pkg: 'payments' },
  { 
    id: 'food_beverage', 
    title: 'Food and Beverage', 
    icon: <Utensils size={20}/>, 
    pkg: 'food_beverage',
    children: [
      { id: 'menus', title: 'Menus', icon: <Utensils size={18}/> },
      { id: 'categories', title: 'Categories', icon: <Tags size={18}/> },
      { id: 'tables', title: 'Tables', icon: <TableProperties size={18}/> },
    ]
  },
  { 
    id: 'rooms_pkg', 
    title: 'Front Office & Rooms', 
    icon: <BedDouble size={20}/>, 
    pkg: 'rooms',
    children: [
      { id: 'rooms', title: 'Rooms', icon: <BedDouble size={18}/> },
      { id: 'reservation_booking', title: 'Reservation and Booking', icon: <CalendarDays size={18}/> },
      { id: 'checkin_checkout', title: 'Check In / Check Out', icon: <Users size={18}/> },
      { id: 'night_audit', title: 'Night Audit', icon: <BarChart3 size={18}/> },
      { id: 'bookings', title: 'Bookings Manager', icon: <ClipboardList size={18}/> },
      { id: 'reports', title: 'Reports Center', icon: <FileBarChart2 size={18}/> },
    ]
  },
  { id: 'analytics', title: 'Analytics', icon: <BarChart3 size={20}/>, pkg: 'analytics' },
  { id: 'users', title: 'Users', icon: <Users size={20}/>, pkg: 'users' },
  { id: 'settings', title: 'Settings', icon: <Settings size={20}/>, pkg: 'settings' },
];

const Sidebar = ({ activeTab, setActiveTab, handleLogout }) => {
  const [hotelSettings, setHotelSettings] = useState(null);
  const [openSubmenu, setOpenSubmenu] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      axios.get(`${API_BASE_URL}/users/settings/`, { headers: { Authorization: `Bearer ${token}` } })
        .then(res => {
          const data = Array.isArray(res.data) ? res.data[0] : res.data;
          setHotelSettings(data);
        })
        .catch(err => console.error("Failed to load hotel settings:", err));
    }
  }, []);

  const enabledFeatures = hotelSettings?.enabled_features || [];

  const toggleSubmenu = (id) => {
    setOpenSubmenu(openSubmenu === id ? null : id);
  };

  return (
    <motion.div
      initial={{ x: -260 }}
      animate={{ x: 0 }}
      transition={{ duration: 0.5, type: 'spring' }}
      style={sidebarStyle}
      className="no-print"
    >
      <div style={logoSectionStyle}>
        {hotelSettings?.logo && (
          <img 
            src={hotelSettings.logo.startsWith('http') ? hotelSettings.logo : `${BASE_URL}${hotelSettings.logo}`} 
            alt="Hotel Logo" 
            style={{ 
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              objectFit: 'cover',
              marginBottom: '15px',
              border: '2px solid #0ff',
              boxShadow: '0 0 15px rgba(0,255,255,0.3)',
              backgroundColor: '#fff'
            }} 
          />
        )}
        <h1 style={logoStyle}>
          <span style={{color: '#fff'}}>
            {hotelSettings?.hotel_name ? hotelSettings.hotel_name.split(' ')[0] : 'SMART'}
          </span>
          {' '}{hotelSettings?.hotel_name ? hotelSettings.hotel_name.split(' ').slice(1).join(' ') : 'HOTEL'}
        </h1>
        <small style={subLogoStyle}>ERP SYSTEM</small>
      </div>

      <nav style={navStyle}>
        {menuItems.map((item, index) => {
          // Filter by enabled features
          if (item.pkg && !enabledFeatures.includes(item.pkg)) {
            return null;
          }

          if (item.type === 'divider') {
            return <div key={`divider-${index}`} style={dividerStyle} />;
          }

          const isActive = activeTab === item.id || (item.children && item.children.some(c => c.id === activeTab));
          const isSubmenuOpen = openSubmenu === item.id;

          return (
            <div key={item.id || index}>
              <motion.div
                onClick={() => item.children ? toggleSubmenu(item.id) : setActiveTab(item.id)}
                whileHover={{ x: 5, backgroundColor: 'rgba(255,255,255,0.05)' }}
                whileTap={{ scale: 0.95 }}
                style={{
                  ...navItemStyle,
                  backgroundColor: (isActive && !item.children) ? '#1a2236' : 'transparent',
                  color: isActive ? '#0ff' : '#a0aec0',
                  borderLeft: (isActive && !item.children) ? '4px solid #0ff' : '4px solid transparent'
                }}
              >
                {item.icon}
                <span style={{ marginLeft: '15px', fontWeight: isActive ? '600' : '400', flex: 1 }}>
                  {item.title}
                </span>
                {item.children && (isSubmenuOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />)}
              </motion.div>

              {item.children && isSubmenuOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  style={{ marginLeft: '25px', marginTop: '5px' }}
                >
                  {item.children.map(child => (
                    <motion.div
                      key={child.id}
                      onClick={() => setActiveTab(child.id)}
                      whileHover={{ x: 5, color: '#0ff' }}
                      style={{
                        ...navItemStyle,
                        padding: '10px 18px',
                        fontSize: '14px',
                        color: activeTab === child.id ? '#0ff' : '#a0aec0',
                        backgroundColor: activeTab === child.id ? 'rgba(0,255,255,0.05)' : 'transparent',
                        borderRadius: '8px'
                      }}
                    >
                      {child.icon}
                      <span style={{ marginLeft: '12px' }}>{child.title}</span>
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Logout button አሁን በ props የመጣውን handleLogout ይጠቀማል */}
      <motion.div
        whileHover={{ backgroundColor: '#2d1a1a', color: '#ef4444' }}
        onClick={handleLogout}
        style={logoutSectionStyle}
      >
        <LogOut size={20} />
        <span style={{ marginLeft: '12px', fontWeight: '600' }}>Logout</span>
      </motion.div>
    </motion.div>
  );
};

// --- Styles ---
const sidebarStyle = {
  width: '260px',
  height: '100vh',
  backgroundColor: '#111827',
  color: 'white',
  position: 'fixed',
  left: 0,
  top: 0,
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '5px 0 15px rgba(0,0,0,0.3)',
  zIndex: 100,
  borderRight: '1px solid #1f2937'
};

const logoSectionStyle = {
  padding: '35px 20px',
  textAlign: 'center',
  borderBottom: '1px solid #1f2937',
  backgroundColor: '#0f172a',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center'
};

const logoStyle = { color: '#0ff', margin: 0, fontSize: '18px', fontWeight: '800', letterSpacing: '0.5px', lineHeight: '1.2' };
const subLogoStyle = { color: '#a0aec0', fontSize: '11px', letterSpacing: '1px', textTransform: 'uppercase' };
const navStyle = { padding: '20px 15px', flex: 1, overflowY: 'auto' };
const navItemStyle = { display: 'flex', alignItems: 'center', padding: '12px 18px', marginBottom: '8px', borderRadius: '10px', cursor: 'pointer', position: 'relative', transition: 'all 0.3s ease' };
const dividerStyle = { height: '1px', backgroundColor: '#1f2937', margin: '15px 0', opacity: 0.5 };
const activeIndicatorStyle = { position: 'absolute', right: '10px', width: '6px', height: '6px', backgroundColor: '#0ff', borderRadius: '50%', boxShadow: '0 0 10px #0ff' };
const logoutSectionStyle = { marginTop: 'auto', padding: '20px 25px', borderTop: '1px solid #1f2937', display: 'flex', alignItems: 'center', cursor: 'pointer', color: '#feb2b2', transition: 'all 0.3s' };

export default Sidebar;
