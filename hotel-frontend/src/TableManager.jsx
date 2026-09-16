import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Plus, Edit, Trash2, CheckCircle, Users, Clock, X, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from './apiConfig';

const API_BASE = `${API_BASE_URL}/users/manage/`;

const TableManager = () => {
  const [tables, setTables] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    table_code: '',
    label_name: '',
    capacity: 4,
    status: 'available'
  });

  useEffect(() => { fetchTables(); }, []);

  const fetchTables = async () => {
    try {
      const res = await axios.get(API_BASE);
      setTables(res.data);
    } catch (err) { console.error("ዳታ መጫን አልተቻለም", err); }
  };

  // 1. መመዝገብ እና ማስተካከል (Create & Update)
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const dataToSend = { ...formData, capacity: parseInt(formData.capacity) };

      if (editingTable) {
        // Update (PUT)
        await axios.put(`${API_BASE}${editingTable.id}/`, dataToSend);
      } else {
        // Create (POST)
        await axios.post(API_BASE, dataToSend);
      }

      closeModal();
      fetchTables();
    } catch (err) {
      alert("ስህተት አጋጥሟል! እባክህ ደግመህ ሞክር።");
    } finally {
      setLoading(false);
    }
  };

  // 2. ማጥፋት (Delete)
  const handleDelete = async (id) => {
    if (window.confirm("ይህ ጠረጴዛ እንዲጠፋ እርግጠኛ ነህ?")) {
      try {
        await axios.delete(`${API_BASE}${id}/`);
        fetchTables();
      } catch (err) {
        alert("ማጥፋት አልተቻለም!");
      }
    }
  };

  // 3. ማስተካከያ ፎርሙን መክፈት (Open Edit Modal)
  const openEditModal = (table) => {
    setEditingTable(table);
    setFormData({
      table_code: table.table_code,
      label_name: table.label_name,
      capacity: table.capacity,
      status: table.status
    });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingTable(null);
    setFormData({ table_code: '', label_name: '', capacity: 4, status: 'available' });
  };

  const filteredTables = tables.filter(t =>
    t.table_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.label_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={containerStyle}>
      {/* Stats Cards */}
      <div style={statsGrid}>
        <div style={statCard}>
          <div style={{...iconCircle, backgroundColor: '#f0fdf4'}}><CheckCircle size={20} color="#166534" /></div>
          <div><p style={statLabel}>AVAILABLE</p><h3 style={statValue}>{tables.filter(t=>t.status==='available').length}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{...iconCircle, backgroundColor: '#fef2f2'}}><Users size={20} color="#991b1b" /></div>
          <div><p style={statLabel}>OCCUPIED</p><h3 style={statValue}>{tables.filter(t=>t.status==='occupied').length}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{...iconCircle, backgroundColor: '#fffbeb'}}><Clock size={20} color="#b45309" /></div>
          <div><p style={statLabel}>RESERVED</p><h3 style={statValue}>{tables.filter(t=>t.status==='reserved').length}</h3></div>
        </div>
      </div>

      <div style={headerActionRow}>
        <div>
          <h2 style={{ margin: 0, color: '#0f172a', fontSize: '28px', fontWeight: '800' }}>Table Management</h2>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '14px' }}>Monitor and assign restaurant tables.</p>
          <div style={searchContainer}>
            <Search size={16} style={searchIcon} />
            <input style={searchInput} placeholder="Search tables..." onChange={(e) => setSearchTerm(e.target.value)} />
          </div>
        </div>
        <button onClick={() => setIsModalOpen(true)} style={addBtn}><Plus size={18} /> Add New Table</button>
      </div>

      {/* Table Table */}
      <div style={tableWrapper}>
        <table style={tableStyle}>
          <thead>
            <tr style={theadRow}>
              <th style={th}>TABLE CODE</th>
              <th style={th}>LABEL</th>
              <th style={th}>CAPACITY</th>
              <th style={th}>STATUS</th>
              <th style={th}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {filteredTables.map((table) => (
              <tr key={table.id} style={tr}>
                <td style={{...td, color: '#0f766e', fontWeight: 'bold'}}>{table.table_code}</td>
                <td style={td}>{table.label_name}</td>
                <td style={td}><span style={capacityTag}>{table.capacity} Seats</span></td>
                <td style={td}>
                  <span style={{
                    ...statusBadge,
                    backgroundColor: table.status === 'available' ? '#f0fdf4' : table.status === 'occupied' ? '#fef2f2' : '#fffbeb',
                    color: table.status === 'available' ? '#166534' : table.status === 'occupied' ? '#991b1b' : '#b45309',
                  }}>
                    {table.status.toUpperCase()}
                  </span>
                </td>
                <td style={td}>
                  <div style={{display:'flex', gap:'15px', alignItems:'center'}}>
                    <Edit
                      size={18}
                      style={{cursor:'pointer', color:'#475569'}}
                      onClick={() => openEditModal(table)}
                    />
                    <Trash2
                      size={18}
                      style={{cursor:'pointer', color:'#ef4444'}}
                      onClick={() => handleDelete(table.id)}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal for Add & Edit */}
      <AnimatePresence>
        {isModalOpen && (
          <div style={modalOverlay}>
            <motion.div initial={{y:20, opacity:0}} animate={{y:0, opacity:1}} exit={{y:20, opacity:0}} style={modalContent}>
              <div style={modalHeader}>
                <h3 style={{margin:0, color: '#0f172a'}}>{editingTable ? "Edit Table" : "Register Table"}</h3>
                <X size={20} onClick={closeModal} style={{cursor:'pointer', color: '#64748b'}} />
              </div>
              <form onSubmit={handleSubmit} style={formStyle}>
                <input style={input} placeholder="Table Code" required value={formData.table_code} onChange={e=>setFormData({...formData, table_code: e.target.value})} />
                <input style={input} placeholder="Label Name" required value={formData.label_name} onChange={e=>setFormData({...formData, label_name: e.target.value})} />
                <div style={{display:'flex', gap:'10px'}}>
                   <input type="number" style={{...input, flex:1}} value={formData.capacity} onChange={e=>setFormData({...formData, capacity: e.target.value})} />
                   <select style={{...input, flex:1, cursor: 'pointer'}} value={formData.status} onChange={e=>setFormData({...formData, status: e.target.value})}>
                      <option value="available">Available</option>
                      <option value="occupied">Occupied</option>
                      <option value="reserved">Reserved</option>
                   </select>
                </div>
                <button type="submit" disabled={loading} style={saveBtn}>
                  {loading ? <Loader2 className="animate-spin" /> : (editingTable ? "Update Changes" : "Confirm & Save")}
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

// Styles
const containerStyle = { padding: '20px', color: '#0f172a' };
const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '40px' };
const statCard = { backgroundColor: '#fff', padding: '20px', borderRadius: '16px', display: 'flex', alignItems: 'center', gap: '20px', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' };
const iconCircle = { width: '45px', height: '45px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const statLabel = { margin: 0, fontSize: '12px', color: '#64748b', fontWeight: 'bold' };
const statValue = { margin: 0, color: '#0f172a', fontSize: '24px', fontWeight: '800' };
const headerActionRow = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '30px' };
const searchContainer = { position: 'relative', marginTop: '15px' };
const searchInput = { backgroundColor: '#fff', border: '1px solid rgba(148,163,184,0.2)', padding: '10px 15px 10px 40px', borderRadius: '10px', color: '#0f172a', width: '300px', outline: 'none' };
const searchIcon = { position: 'absolute', left: '12px', top: '12px', color: '#64748b' };
const addBtn = { backgroundColor: '#0f766e', color: '#fff', border: 'none', padding: '12px 24px', borderRadius: '12px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };
const tableWrapper = { backgroundColor: '#fff', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.16)', overflow: 'hidden', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' };
const tableStyle = { width: '100%', borderCollapse: 'collapse' };
const theadRow = { borderBottom: '1px solid rgba(148,163,184,0.16)', backgroundColor: '#f8fafc', textAlign: 'left' };
const th = { padding: '18px', fontSize: '11px', color: '#64748b', fontWeight: 'bold' };
const tr = { borderBottom: '1px solid #f1f5f9' };
const td = { padding: '18px', fontSize: '14px', color: '#0f172a' };
const capacityTag = { backgroundColor: '#eff6ff', padding: '4px 10px', borderRadius: '6px', fontSize: '12px', color: '#1d4ed8', fontWeight: '700' };
const statusBadge = { padding: '4px 12px', borderRadius: '6px', fontSize: '10px', fontWeight: 'bold' };
const modalOverlay = { position:'fixed', top:0, left:0, width:'100%', height:'100%', backgroundColor:'rgba(15,23,42,0.4)', backdropFilter: 'blur(4px)', zIndex:1000, display:'flex', justifyContent:'center', alignItems:'center' };
const modalContent = { backgroundColor:'#fff', padding:'30px', borderRadius:'20px', width:'400px', border:'1px solid rgba(148,163,184,0.16)', boxShadow: '0 20px 40px rgba(15,23,42,0.1)' };
const modalHeader = { display:'flex', justifyContent:'space-between', marginBottom:'20px', color:'#0f172a', alignItems: 'center' };
const formStyle = { display:'flex', flexDirection:'column', gap:'15px' };
const input = { backgroundColor:'#f1f5f9', border:'1px solid rgba(148,163,184,0.12)', padding:'12px', borderRadius:'10px', color:'#0f172a', outline:'none' };
const saveBtn = { backgroundColor:'#0f766e', color:'#fff', padding:'14px', borderRadius:'10px', border:'none', fontWeight:'bold', cursor:'pointer', marginTop:'10px', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };

export default TableManager;