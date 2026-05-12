import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  UserPlus, Search, Edit, Trash2, Shield, UserCheck, Check,
  Users, X, Camera, Phone, Mail, Lock, Briefcase
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from './apiConfig';

const USER_API = `${API_BASE_URL}/users/users/`;

const UserManager = () => {
  const [users, setUsers] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('All Roles');
  const [statusFilter, setStatusFilter] = useState('All Status');

  const [hotelSettings, setHotelSettings] = useState(null);
  const [formData, setFormData] = useState({
    full_name: '', email: '', role: 'Admin', phone_number: '', password: '', is_active: true, profile_picture: null
  });

  useEffect(() => { fetchUsers(); }, []);

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('access');
      const [usersRes, settingsRes] = await Promise.all([
        axios.get(USER_API, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API_BASE_URL}/users/settings/`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
      const settingsData = Array.isArray(settingsRes.data) ? settingsRes.data[0] : settingsRes.data;
      setHotelSettings(settingsData);
    } catch (err) {
      console.error("Fetch error:", err);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value, type, files } = e.target;
    if (type === 'file') {
      setFormData({ ...formData, [name]: files[0] });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm("Are you sure you want to delete this user?")) {
      try {
        const token = localStorage.getItem('access');
        await axios.delete(`${USER_API}${id}/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        fetchUsers();
      } catch (err) {
        alert("Error deleting user.");
      }
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || '';
    setFormData({
      full_name: fullName,
      email: user.email || '',
      role: user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'Waiter',
      phone_number: user.phone_number || '',
      password: '',
      is_active: user.is_active,
      profile_picture: null
    });
    setIsModalOpen(true);
  };

 const handleSubmit = async (e) => {
    e.preventDefault();
    const data = new FormData();
    const nameParts = formData.full_name.trim().split(' ');

    // 1. የኢሜይሉን የመጀመሪያ ክፍል ለዩዘርኔም እንጠቀም (Unique እንዲሆን)
    const generatedUsername = formData.email.split('@')[0];

    data.append('first_name', nameParts[0] || '');
    data.append('last_name', nameParts.slice(1).join(' ') || '');
    data.append('username', generatedUsername);
    data.append('email', formData.email);
    data.append('role', formData.role.toLowerCase());
    data.append('phone_number', formData.phone_number);

    if (formData.password) data.append('password', formData.password);

    // 2. Boolean ዋጋን ወደ String እንቀይረው (Django በ FormData ውስጥ እንዲረዳው)
    data.append('is_active', String(formData.is_active));

    if (formData.profile_picture instanceof File) {
      data.append('profile_picture', formData.profile_picture);
    }

    try {
      const token = localStorage.getItem('access');
      const config = {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}`
        }
      };

      if (editingUser) {
        // ኤዲት ሲደረግ
        await axios.patch(`${USER_API}${editingUser.id}/`, data, config);
        alert("ተጠቃሚው ተስተካክሏል!");
      } else {
        // *** ወሳኝ ማስተካከያ ***
        // አድሚን ስለሆንክ በቀጥታ ወደ USER_API (Viewset) ላክ እንጂ ወደ REGISTER_API አትላክ
        await axios.post(USER_API, data, config);
        alert("አዲስ ተጠቃሚ በተሳካ ሁኔታ ተፈጥሯል!");
      }

      setIsModalOpen(false);
      resetForm();
      fetchUsers();
    } catch (err) {
      console.error("Full Error details:", err.response?.data);
      // ስህተቱን ለተጠቃሚው በግልጽ ለማሳየት
      const errorMsg = err.response?.data
        ? JSON.stringify(err.response.data)
        : "Network error occurred";
      alert("Error saving: " + errorMsg);
    }
  };

  const resetForm = () => {
    setFormData({ full_name: '', email: '', role: 'Admin', phone_number: '', password: '', is_active: true, profile_picture: null });
    setEditingUser(null);
  };

  // --- Dynamic Roles Filtering ---
  const getAvailableRoles = () => {
    const enabled = hotelSettings?.enabled_features || [];
    let available = ['Admin'];
    
    if (enabled.includes('food_beverage')) {
      available.push('Cashier', 'Waiter', 'Kitchen', 'Bar');
    }
    
    if (enabled.includes('rooms')) {
      available.push('Reception');
    }
    
    // Add others if needed
    // available.push('Inventory', 'Delivery');
    
    return available;
  };

  const roles = getAvailableRoles();
  const statusOptions = ['Active', 'Inactive'];

  const getFilteredUsers = () => {
    return users.filter(user => {
      const nameMatch = `${user.first_name || ''} ${user.last_name || ''} ${user.username || ''}`.toLowerCase().includes(searchQuery.toLowerCase());
      const emailMatch = (user.email || "").toLowerCase().includes(searchQuery.toLowerCase());
      const queryMatch = nameMatch || emailMatch;
      const roleMatch = roleFilter === 'All Roles' || (user.role && user.role.toLowerCase() === roleFilter.toLowerCase());
      const statusMatch = statusFilter === 'All Status' || (statusFilter === 'Active' && user.is_active) || (statusFilter === 'Inactive' && !user.is_active);
      return queryMatch && roleMatch && statusMatch;
    });
  };

  const filteredUsers = getFilteredUsers();

  if (loading) return <div style={{padding: '20px'}}>Loading...</div>;

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div>
          <h1 style={titleStyle}>User Management</h1>
          <p style={subtitleStyle}>Manage your team members and their access levels.</p>
        </div>
        <button onClick={() => { resetForm(); setIsModalOpen(true); }} style={addBtnStyle}>
          <UserPlus size={18}/> Add New User
        </button>
      </div>

      {/* Stats */}
      <div style={statsGrid}>
        <StatCard label="Total Users" value={users.length} icon={<Users color="#3b82f6"/>} color="#3b82f6" />
        <StatCard label="Active Users" value={users.filter(u => u.is_active).length} icon={<UserCheck color="#10b981"/>} color="#10b981" />
        <StatCard label="Admins" value={users.filter(u => u.role === 'admin').length} icon={<Shield color="#f59e0b"/>} color="#f59e0b" />
        <StatCard label="New This Month" value="0" icon={<UserPlus color="#a0aec0"/>} color="#f8fafc" change="0.00%"/>
      </div>

      {/* Search & Table */}
      <div style={tableCardStyle}>
        <div style={filterHeaderStyle}>
          <div style={searchWrapperStyle}>
            <Search size={20} color="#a0aec0" />
            <input
              style={searchFieldStyle}
              placeholder="Search by name, email or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div style={filterWrapperStyle}>
            <label style={filterLabelStyle}>Role:</label>
            <Dropdown value={roleFilter} options={['All Roles', ...roles]} onChange={setRoleFilter} icon={<Briefcase size={16} color="#a0aec0"/>}/>
            <label style={filterLabelStyle}>Status:</label>
            <Dropdown value={statusFilter} options={['All Status', ...statusOptions]} onChange={setStatusFilter}/>
          </div>
        </div>

        <table style={tableStyle}>
          <thead>
            <tr style={thRowStyle}>
              <th style={thStyle}>User Info</th>
              <th style={thStyle}>Role</th>
              <th style={thStyle}>Status</th>
              <th style={{...thStyle, textAlign: 'center'}}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map(user => (
              <tr key={user.id} style={trStyle}>
                <td style={tdStyle}>
                  <div style={userInfoStyle}>
                    <div style={initialsAvatarStyle}>{`${user.first_name?.[0] || user.username?.[0] || 'U'}${user.last_name?.[0] || ''}`.toUpperCase()}</div>
                    <div>
                      <div style={userNameStyle}>{user.first_name || user.username} {user.last_name}</div>
                      <div style={userEmailStyle}>{user.email}</div>
                    </div>
                  </div>
                </td>
                <td style={tdStyle}><span style={getRoleBadgeStyle(user.role)}>{user.role}</span></td>
                <td style={tdStyle}><span style={getStatusBadgeStyle(user.is_active)}>{user.is_active ? 'Active' : 'Inactive'}</span></td>
                <td style={{...tdStyle, textAlign: 'center'}}>
                  <div style={actionButtonsWrapperStyle}>
                    <button onClick={() => handleEdit(user)} style={iconBtnStyle}><Edit size={18}/></button>
                    <button onClick={() => handleDelete(user.id)} style={{...iconBtnStyle, color: '#ef4444'}}><Trash2 size={18}/></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={footerStyle}>© 2026 ACRMA TECH SOLUTION.</div>

      {/* Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} style={modalContentStyle}>
              <div style={modalHeaderStyle}>
                <h2>{editingUser ? 'Edit User' : 'Create New User'}</h2>
                <X onClick={() => {setIsModalOpen(false); resetForm();}} style={{cursor:'pointer'}} color="#a0aec0"/>
              </div>

              <form onSubmit={handleSubmit} style={formLayoutStyle}>
                <div style={uploadSectionStyle}>
                  <label htmlFor="file-upload" style={photoCircleStyle}>
                    {formData.profile_picture ?
                      <img src={URL.createObjectURL(formData.profile_picture)} style={{width:'100%', height:'100%', borderRadius:'50%', objectFit:'cover'}} alt="preview"/> :
                      <Users size={36} color="#a0aec0" />
                    }
                    <div style={uploadIconCircleStyle}><Camera size={16} color="white"/></div>
                    <input id="file-upload" type="file" name="profile_picture" onChange={handleInputChange} style={{display:'none'}} />
                  </label>
                  <div style={photoTitleStyle}>Profile Photo</div>
                  <div style={uploadLabelStyle}>Click to upload or drag and drop</div>
                </div>

                <div style={formGridStyle}>
                  <InputBoxWithIcon label="Full Name" name="full_name" value={formData.full_name} onChange={handleInputChange} icon={<Users size={20} color="#a0aec0"/>} placeholder="John Doe" />
                  <InputBoxWithIcon label="Email Address" name="email" value={formData.email} onChange={handleInputChange} icon={<Mail size={20} color="#a0aec0"/>} placeholder="admin@som.com" success={formData.email && formData.email.includes('@')}/>
                  <div style={fieldGroupStyle}>
                    <label style={labelStyle}>Role</label>
                    <div style={inputInsideStyle}>
                      <Briefcase size={20} color="#a0aec0" style={{marginRight: '12px'}}/>
                      <select name="role" style={selectInputStyle} value={formData.role} onChange={handleInputChange}>
                        {roles.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                  </div>
                  <InputBoxWithIcon label="Phone Number" name="phone_number" value={formData.phone_number} onChange={handleInputChange} icon={<Phone size={20} color="#a0aec0"/>} placeholder="+251..." />
                </div>

                <div style={securitySectionTitleStyle}>SECURITY & ACCESS</div>

                <div style={formGridStyle}>
                   <InputBoxWithIcon label="Password" name="password" type="password" value={formData.password} onChange={handleInputChange} icon={<Lock size={20} color="#a0aec0"/>} placeholder="........" />
                   <div style={accountStatusWrapperStyle}>
                     <div style={statusInfoStyle}>
                       <Shield size={24} color="#10b981"/>
                       <div>
                         <div style={statusTitleStyle}>Account Status</div>
                         <div style={statusDescStyle}>{formData.is_active ? 'Active' : 'Inactive'}</div>
                       </div>
                     </div>
                     <Switch checked={formData.is_active} onChange={checked => setFormData({...formData, is_active: checked})} />
                   </div>
                </div>

                <div style={modalFooterStyle}>
                  <button type="button" onClick={() => {setIsModalOpen(false); resetForm();}} style={cancelBtnStyle}>Cancel</button>
                  <button type="submit" style={submitBtnStyle}>{editingUser ? 'Update User' : 'Create User'}</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

// --- Helper Components & Styles (እንዳሉ ይቀጥላሉ) ---
const StatCard = ({label, value, icon, color, change}) => (
  <div style={statCardStyle}>
    <div style={{...iconCircleStyle, backgroundColor: icon.props.color ? `${icon.props.color}15` : '#f1f5f9'}}>{icon}</div>
    <div>
      <p style={statLabelStyle}>{label}</p>
      <div style={{display:'flex', alignItems:'baseline', gap:'8px'}}>
        <h3 style={statValueStyle}>{value}</h3>
        {change && <span style={{fontSize:'12px', fontWeight:'600', color: '#10b981'}}>{change}</span>}
      </div>
    </div>
  </div>
);

const InputBoxWithIcon = ({label, icon, success, ...props}) => (
  <div style={fieldGroupStyle}>
    <label style={labelStyle}>{label}</label>
    <div style={inputInsideStyle}>
      <span style={{marginRight: '12px'}}>{icon}</span>
      <input style={rawInputStyle} {...props} />
      {success && <Check size={20} color="#10b981" style={{marginLeft: '12px'}}/>}
    </div>
  </div>
);

const Dropdown = ({value, options, onChange, icon}) => (
  <div style={dropdownWrapperStyle}>
    {icon && <span style={{marginRight:'8px'}}>{icon}</span>}
    <select value={value} onChange={e => onChange(e.target.value)} style={dropdownSelectStyle}>
      {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
    </select>
  </div>
);

const Switch = ({checked, onChange}) => (
  <div onClick={() => onChange(!checked)} style={{...switchBgStyle, backgroundColor: checked ? '#3f5d45' : '#cbd5e1'}}>
    <div style={{...switchHandleStyle, transform: checked ? 'translateX(20px)' : 'translateX(0px)'}} />
  </div>
);

const getRoleBadgeStyle = (role) => {
  const base = { padding: '4px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600' };
  switch (role?.toLowerCase()) {
    case 'admin': return { ...base, backgroundColor: '#f1f5f9', color: '#64748b' };
    case 'waiter': return { ...base, backgroundColor: '#fef3c7', color: '#b45309' };
    default: return { ...base, backgroundColor: '#f1f5f9', color: '#64748b' };
  }
};

const getStatusBadgeStyle = (isActive) => ({
  padding: '4px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600',
  backgroundColor: isActive ? '#ecfdf5' : '#fef2f2',
  color: isActive ? '#059669' : '#b91c1c'
});

const containerStyle = { padding: '30px', backgroundColor: '#f8fafc', color: '#1e293b', fontFamily: 'Inter, sans-serif' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' };
const titleStyle = { fontSize: '28px', fontWeight: '800', margin: 0 };
const subtitleStyle = { color: '#64748b', fontSize: '14px' };
const addBtnStyle = { backgroundColor: '#3f5d45', color: '#fff', border: 'none', padding: '12px 24px', borderRadius: '12px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' };
const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px', marginBottom: '30px' };
const statCardStyle = { backgroundColor: '#fff', padding: '24px', borderRadius: '20px', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '16px' };
const iconCircleStyle = { width: '48px', height: '48px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const statLabelStyle = { margin: 0, fontSize: '13px', color: '#64748b', fontWeight: '600' };
const statValueStyle = { margin: 0, fontSize: '28px', fontWeight: '800' };
const tableCardStyle = { backgroundColor: '#fff', borderRadius: '24px', border: '1px solid #e2e8f0', padding: '24px' };
const filterHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' };
const searchWrapperStyle = { display: 'flex', alignItems: 'center', backgroundColor: '#f1f5f9', padding: '10px 16px', borderRadius: '12px', width: '400px' };
const searchFieldStyle = { background: 'none', border: 'none', outline: 'none', color: '#1e293b', marginLeft: '12px', width: '100%', fontSize: '14px' };
const filterWrapperStyle = { display: 'flex', alignItems: 'center', gap: '12px' };
const filterLabelStyle = { fontSize: '13px', fontWeight: '600', color: '#64748b' };
const tableStyle = { width: '100%', borderCollapse: 'collapse' };
const thRowStyle = { borderBottom: '2px solid #e2e8f0' };
const thStyle = { textAlign: 'left', padding: '16px', color: '#64748b', fontSize: '13px', fontWeight: '700' };
const trStyle = { borderBottom: '1px solid #e2e8f0' };
const tdStyle = { padding: '16px' };
const userInfoStyle = { display: 'flex', alignItems: 'center', gap: '12px' };
const initialsAvatarStyle = { width: '40px', height: '40px', borderRadius: '50%', backgroundColor: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '700', color: '#64748b' };
const userNameStyle = { fontWeight: '700', fontSize: '14px' };
const userEmailStyle = { fontSize: '12px', color: '#64748b' };
const actionButtonsWrapperStyle = { display: 'flex', justifyContent: 'center', gap: '8px' };
const iconBtnStyle = { background: 'none', border: 'none', color: '#a0aec0', cursor: 'pointer', padding: '8px' };
const footerStyle = { textAlign: 'center', color: '#a0aec0', fontSize: '11px', marginTop: '40px' };
const dropdownWrapperStyle = { display: 'flex', alignItems: 'center', padding: '8px 12px', borderRadius: '12px', border: '1px solid #e2e8f0', backgroundColor: '#f8fafc' };
const dropdownSelectStyle = { background: 'none', border: 'none', outline: 'none', color: '#1e293b', fontSize: '13px', fontWeight: '600' };
const modalOverlayStyle = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 };
const modalContentStyle = { backgroundColor: '#fff', padding: '40px', borderRadius: '24px', width: '550px' };
const modalHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' };
const formLayoutStyle = { display: 'flex', flexDirection: 'column', gap: '24px' };
const uploadSectionStyle = { textAlign: 'center' };
const photoCircleStyle = { width: '100px', height: '100px', borderRadius: '50%', backgroundColor: '#f1f5f9', border: '2px solid #e2e8f0', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', position: 'relative' };
const uploadIconCircleStyle = { width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#3f5d45', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'absolute', bottom: '0', right: '0' };
const photoTitleStyle = { fontSize: '14px', fontWeight: '700', marginTop: '12px' };
const uploadLabelStyle = { fontSize: '12px', color: '#64748b' };
const formGridStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' };
const fieldGroupStyle = { display: 'flex', flexDirection: 'column', gap: '8px' };
const labelStyle = { fontSize: '13px', fontWeight: '700', color: '#64748b' };
const inputInsideStyle = { display: 'flex', alignItems: 'center', backgroundColor: '#f1f5f9', padding: '12px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' };
const rawInputStyle = { background: 'none', border: 'none', outline: 'none', color: '#1e293b', fontSize: '14px', width: '100%' };
const selectInputStyle = { background: 'none', border: 'none', outline: 'none', color: '#1e293b', fontSize: '14px', width: '100%' };
const securitySectionTitleStyle = { fontSize: '11px', fontWeight: '700', color: '#a0aec0', textAlign: 'center' };
const accountStatusWrapperStyle = { backgroundColor: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const statusInfoStyle = { display: 'flex', alignItems: 'center', gap: '12px' };
const statusTitleStyle = { fontSize: '14px', fontWeight: '700' };
const statusDescStyle = { fontSize: '12px', color: '#64748b' };
const modalFooterStyle = { display: 'flex', justifyContent: 'space-around', gap: '20px', marginTop: '30px' };
const cancelBtnStyle = { background: 'none', border: 'none', color: '#64748b', fontWeight: '700', cursor: 'pointer' };
const submitBtnStyle = { backgroundColor: '#3f5d45', color: '#fff', border: 'none', padding: '14px 40px', borderRadius: '12px', fontWeight: '800', cursor: 'pointer' };
const switchBgStyle = { width: '40px', height: '20px', borderRadius: '10px', padding: '2px', cursor: 'pointer', display: 'flex', alignItems: 'center' };
const switchHandleStyle = { width: '16px', height: '16px', backgroundColor: '#fff', borderRadius: '50%' };

export default UserManager;