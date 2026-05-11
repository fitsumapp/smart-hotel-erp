import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Plus, Pencil, Trash2, X, Check } from 'lucide-react';
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
  }, []);

  const fetchData = async () => {
    try {
      const [resItems, resCats] = await Promise.all([
        axios.get(`${API_BASE}menu-items/`),
        axios.get(`${API_BASE}categories/`)
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
        await axios.put(`${API_BASE}menu-items/${editingId}/`, formData);
      } else {
        // ADD (POST)
        await axios.post(`${API_BASE}menu-items/`, formData);
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
        await axios.delete(`${API_BASE}menu-items/${id}/`);
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
    <div style={{ padding: '20px', color: '#fff' }}>
      {/* Header */}
      <div style={headerCardStyle}>
        <div>
          <h2 style={{ margin: 0, fontSize: '28px' }}>Menu Items</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Manage and edit your food items.</p>
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
              <h4 style={{ margin: 0 }}>{item.name}</h4>
              <p style={descStyle}>{item.description}</p>
              <div style={cardFooter}>
                <div style={priceValue}>{item.price} <span style={{fontSize: '10px'}}>ETB</span></div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => startEdit(item)} style={actionBtn}><Pencil size={14} /></button>
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
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                <h3>{editingId ? 'Edit Menu Item' : 'Add New Item'}</h3>
                <X onClick={() => setIsModalOpen(false)} style={{ cursor: 'pointer' }} />
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

                <input type="file" onChange={e => setNewItem({...newItem, image: e.target.files[0]})} />

                <div style={{ display: 'flex', gap: '10px' }}>
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

// Styles (እንዳሉ ይቀጥላሉ...)
const headerCardStyle = { backgroundColor: '#111827', padding: '25px', borderRadius: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', border: '1px solid #1f2937' };
const addBtnStyle = { backgroundColor: '#365314', color: '#bef264', border: 'none', padding: '10px 20px', borderRadius: '10px', fontWeight: '700', cursor: 'pointer' };
const filterBarStyle = { display: 'flex', gap: '20px', marginBottom: '30px', alignItems: 'center' };
const searchContainer = { display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#1f2937', padding: '10px 15px', borderRadius: '12px', flex: 1, border: '1px solid #374151' };
const searchInputStyle = { background: 'none', border: 'none', color: '#fff', outline: 'none', width: '100%' };
const selectStyle = { backgroundColor: '#1f2937', color: '#fff', border: '1px solid #374151', padding: '10px', borderRadius: '12px' };
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '25px' };
const itemCardStyle = { backgroundColor: '#111827', borderRadius: '20px', overflow: 'hidden', border: '1px solid #1f2937' };
const imageWrapper = { position: 'relative', height: '180px' };
const itemImgStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const descStyle = { fontSize: '12px', color: '#64748b', margin: '10px 0' };
const cardFooter = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' };
const priceValue = { fontSize: '20px', fontWeight: '800', color: '#fff' };
const actionBtn = { backgroundColor: '#1f2937', border: 'none', padding: '8px', borderRadius: '8px', cursor: 'pointer' };
const modalOverlayStyle = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.8)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 };
const modalContentStyle = { backgroundColor: '#111827', padding: '30px', borderRadius: '20px', width: '400px', border: '1px solid #1f2937' };
const inputStyle = { backgroundColor: '#1f2937', border: '1px solid #374151', color: '#fff', padding: '12px', borderRadius: '10px' };
const saveBtnStyle = { flex: 1, backgroundColor: '#365314', color: '#bef264', border: 'none', padding: '12px', borderRadius: '10px', fontWeight: '700', cursor: 'pointer' };
const cancelBtnStyle = { flex: 1, backgroundColor: '#1f2937', color: '#94a3b8', border: 'none', padding: '12px', borderRadius: '10px', cursor: 'pointer' };

export default MenuManager;