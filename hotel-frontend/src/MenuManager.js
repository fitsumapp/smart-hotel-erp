import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Plus, Pencil, Trash2, X } from 'lucide-react';
import { API_BASE_URL, BASE_URL } from './apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;
const SERVER_URL = `${BASE_URL}/`;

const MenuManager = () => {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  // ለ Modal እና ለፎርም ስቴቶች
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null); // Edit ለማድረግ ID መያዣ
  const [newItem, setNewItem] = useState({ name: '', category: '', price: '', description: '', image: null });

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getHeaders = () => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchData = async () => {
    try {
      const [resItems, resCats] = await Promise.all([
        axios.get(`${API_BASE}menu-items/`, { headers: getHeaders() }),
        axios.get(`${API_BASE}categories/`, { headers: getHeaders() })
      ]);
      setItems(resItems.data);
      setCategories(resCats.data);
    } catch (error) {
      console.error("ዳታ መጫን አልተቻለም፦", error);
    }
  };

  // 1. SAVE (ADD & UPDATE) ተግባር
  const handleSaveItem = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('name', newItem.name);
    formData.append('category', newItem.category);
    formData.append('price', newItem.price);
    formData.append('description', newItem.description);

    // አዲስ ምስል ከተመረጠ ብቻ ጨምር
    if (newItem.image instanceof File) {
      formData.append('image', newItem.image);
    }

    try {
      if (editingId) {
        // UPDATE (PUT)
        await axios.put(`${API_BASE}menu-items/${editingId}/`, formData, {
          headers: getHeaders()
        });
      } else {
        // ADD (POST)
        await axios.post(`${API_BASE}menu-items/`, formData, {
          headers: getHeaders()
        });
      }

      setIsModalOpen(false);
      setEditingId(null);
      resetForm();
      fetchData();
    } catch (error) {
      console.error("ስህተት ተፈጥሯል:", error.response?.data);
      alert("ማስቀመጥ አልተቻለም። እባክህ ሁሉንም ቦታ መሙላትህን አረጋግጥ።");
    }
  };

  // 2. DELETE ተግባር
  const handleDelete = async (id) => {
    if (window.confirm("ይህንን ምግብ መሰረዝ ትፈልጋለህ?")) {
      try {
        await axios.delete(`${API_BASE}menu-items/${id}/`, {
          headers: getHeaders()
        });
        fetchData(); // ዝርዝሩን አድስ
      } catch (error) {
        console.error("መሰረዝ አልተቻለም:", error);
      }
    }
  };

  // 3. EDIT ለመጀመር (ዳታውን ወደ ፎርም መሙያ)
  const startEdit = (item) => {
    setEditingId(item.id);
    setNewItem({
      name: item.name,
      category: item.category, // ID መሆኑን አረጋግጥ
      price: item.price,
      description: item.description,
      image: item.image // ይህ URL ነው
    });
    setIsModalOpen(true);
  };

  const resetForm = () => {
    setNewItem({ name: '', category: '', price: '', description: '', image: null });
    setEditingId(null);
  };

  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
    (selectedCategory === "All" || item.category_name === selectedCategory)
  );

  return (
    <div style={{ padding: '20px', color: '#0f172a' }}>
      {/* Header */}
      <div style={headerCardStyle}>
        <div>
          <h2 style={{ margin: 0, fontSize: '28px', color: '#0f172a' }}>Menu Items</h2>
          <p style={{ color: '#64748b', fontSize: '14px' }}>Manage and edit your food items.</p>
        </div>
        <button onClick={() => { resetForm(); setIsModalOpen(true); }} style={addBtnStyle}>
          <Plus size={18} /> Add Item
        </button>
      </div>

      {/* Filter Bar */}
      <div style={filterBarStyle}>
        <div style={searchContainer}>
          <Search size={18} color="#64748b" />
          <input
            type="text"
            placeholder="Search items..."
            style={searchInputStyle}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <select style={selectStyle} onChange={(e) => setSelectedCategory(e.target.value)}>
          <option value="All">All Categories</option>
          {categories.map(cat => <option key={cat.id} value={cat.name}>{cat.name}</option>)}
        </select>
      </div>

      {/* Items Grid */}
      <div style={gridStyle}>
        {filteredItems.map(item => (
          <motion.div key={item.id} layout style={itemCardStyle}>
            <div style={imageWrapper}>
              <img
                src={item.image ? (item.image.startsWith('http') ? item.image : `${SERVER_URL}${item.image}`) : 'https://via.placeholder.com/300'}
                alt={item.name}
                style={itemImgStyle}
              />
            </div>
            <div style={{ padding: '15px' }}>
              <h4 style={{ margin: 0, color: '#0f172a' }}>{item.name}</h4>
              <p style={descStyle}>{item.description}</p>
              <div style={cardFooter}>
                <div style={priceValue}>{item.price} <span style={{fontSize: '10px'}}>ETB</span></div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => startEdit(item)} style={actionBtn}><Pencil size={14} color="#475569" /></button>
                  <button onClick={() => handleDelete(item.id)} style={{...actionBtn, color: '#ef4444'}}><Trash2 size={14} /></button>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Modal (Add & Edit) */}
      <AnimatePresence>
        {isModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }} style={modalContentStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px', alignItems: 'center' }}>
                <h3 style={{ margin: 0, color: '#0f172a' }}>{editingId ? 'Edit Menu Item' : 'Add New Item'}</h3>
                <X onClick={() => setIsModalOpen(false)} style={{ cursor: 'pointer', color: '#64748b' }} />
              </div>

              <form onSubmit={handleSaveItem} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <input
                  required
                  placeholder="Item Name"
                  value={newItem.name}
                  style={inputStyle}
                  onChange={e => setNewItem({...newItem, name: e.target.value})}
                />

                <select
                  required
                  value={newItem.category}
                  style={inputStyle}
                  onChange={e => setNewItem({...newItem, category: e.target.value})}
                >
                  <option value="">Select Category</option>
                  {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                </select>

                <input
                  required
                  type="number"
                  value={newItem.price}
                  placeholder="Price"
                  style={inputStyle}
                  onChange={e => setNewItem({...newItem, price: e.target.value})}
                />

                <textarea
                  placeholder="Description"
                  value={newItem.description}
                  style={{...inputStyle, height: '80px'}}
                  onChange={e => setNewItem({...newItem, description: e.target.value})}
                />

                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b' }}>Item Image</label>
                  <input type="file" onChange={e => setNewItem({...newItem, image: e.target.files[0]})} style={{ fontSize: '12px' }} />
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsModalOpen(false)} style={cancelBtnStyle}>Cancel</button>
                  <button type="submit" style={saveBtnStyle}>
                    {editingId ? 'Update Item' : 'Save Item'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

// Styles
const headerCardStyle = { backgroundColor: '#fff', padding: '25px', borderRadius: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 4px 20px rgba(15,23,42,0.03)' };
const addBtnStyle = { backgroundColor: '#0f766e', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '10px', fontWeight: '700', cursor: 'pointer', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };
const filterBarStyle = { display: 'flex', gap: '20px', marginBottom: '30px', alignItems: 'center' };
const searchContainer = { display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#fff', padding: '10px 15px', borderRadius: '12px', flex: 1, border: '1px solid rgba(148,163,184,0.2)' };
const searchInputStyle = { background: 'none', border: 'none', color: '#0f172a', outline: 'none', width: '100%' };
const selectStyle = { backgroundColor: '#fff', color: '#475569', border: '1px solid rgba(148,163,184,0.2)', padding: '10px', borderRadius: '12px', outline: 'none', cursor: 'pointer' };
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '25px' };
const itemCardStyle = { backgroundColor: '#fff', borderRadius: '20px', overflow: 'hidden', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' };
const imageWrapper = { position: 'relative', height: '180px' };
const itemImgStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const descStyle = { fontSize: '12px', color: '#64748b', margin: '10px 0' };
const cardFooter = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' };
const priceValue = { fontSize: '20px', fontWeight: '800', color: '#0f766e' };
const actionBtn = { backgroundColor: '#f1f5f9', border: 'none', padding: '8px', borderRadius: '8px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' };
const modalOverlayStyle = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(15,23,42,0.4)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 };
const modalContentStyle = { backgroundColor: '#fff', padding: '30px', borderRadius: '20px', width: '400px', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 20px 40px rgba(15,23,42,0.1)' };
const inputStyle = { backgroundColor: '#f1f5f9', border: '1px solid rgba(148,163,184,0.12)', color: '#0f172a', padding: '12px', borderRadius: '10px', outline: 'none' };
const saveBtnStyle = { flex: 1, backgroundColor: '#0f766e', color: '#fff', border: 'none', padding: '12px', borderRadius: '10px', fontWeight: '700', cursor: 'pointer', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };
const cancelBtnStyle = { flex: 1, backgroundColor: '#e2e8f0', color: '#475569', border: 'none', padding: '12px', borderRadius: '10px', cursor: 'pointer' };

export default MenuManager;