import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Pencil, Trash2, X, Check, Image as ImageIcon, Upload } from 'lucide-react';
import { API_BASE_URL } from './apiConfig';

const CATEGORY_API_BASE = `${API_BASE_URL}/users/categories/`;

const CategoryManager = () => {
  const stations = [{ id: 1, name: 'Kitchen' }, { id: 2, name: 'Bar' }];
  const [categories, setCategories] = useState([]);
  const [formData, setFormData] = useState({ name: '', station: 'Kitchen', description: '', image: null });
  const [imageFile, setImageFile] = useState(null);
  const [editingId, setEditingId] = useState(null);

  const getHeaders = () => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // 1. ዳታ ከመረጃ ቋቱ (Database) ለማምጣት
  const fetchCategories = async () => {
    try {
      const response = await axios.get(CATEGORY_API_BASE, {
        headers: getHeaders()
      });
      const data = Array.isArray(response.data) ? response.data : (response.data?.results || []);
      console.log("Categories Loaded:", data);
      setCategories(data);
    } catch (error) {
      console.error("ዳታ መጫን አልተቻለም:", error);
      if (error.response?.status === 401) {
        alert("Session ጊዜው አልቋል (Session Expired)። እባክዎ Logout ብለው መልሰው Login ያድርጉ።");
      }
    }
  };

  useEffect(() => {
    fetchCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file); // ለ Django ለመላክ
      setFormData({ ...formData, image: URL.createObjectURL(file) }); // ለ preview
    }
  };

  const handleSave = async () => {
    if (!formData.name) return;

    // ምስል ስላለን FormData object መጠቀም አለብን
    const data = new FormData();
    data.append('name', formData.name);
    data.append('station', formData.station);
    data.append('description', formData.description);
    if (imageFile) {
      data.append('image', imageFile);
    }

    try {
      if (editingId) {
        await axios.put(`${CATEGORY_API_BASE}${editingId}/`, data, {
          headers: getHeaders()
        });
      } else {
        await axios.post(CATEGORY_API_BASE, data, {
          headers: getHeaders()
        });
      }
      fetchCategories(); // ዳታውን እንደገና አድስ
      resetForm();
    } catch (error) {
      console.error("መመዝገብ አልተቻለም:", error);
      if (error.response?.status === 401) {
        alert("Session ጊዜው አልቋል (Session Expired)። እባክዎ Logout ብለው መልሰው Login ያድርጉ።");
      } else {
        const msg = error.response?.data?.error?.message || error.response?.data?.name?.[0] || error.response?.data?.detail || "ካቴጎሪ መመዝገብ አልተቻለም።";
        alert("ስህተት፦ " + msg);
      }
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setFormData({ name: '', station: 'Kitchen', description: '', image: null });
    setImageFile(null);
  };

  const deleteCategory = async (id) => {
    if (window.confirm("Are you sure?")) {
      try {
        await axios.delete(`${CATEGORY_API_BASE}${id}/`, {
          headers: getHeaders()
        });
        fetchCategories();
      } catch (error) {
        console.error("መሰረዝ አልተቻለም:", error);
      }
    }
  };

  const startEdit = (cat) => {
    setEditingId(cat.id);
    setFormData({
      name: cat.name,
      station: cat.station,
      description: cat.description,
      image: cat.image // ይህ ከ Django የሚመጣ URL ነው
    });
  };

  return (
    <div style={containerStyle}>
      <h2 style={titleStyle}>{editingId ? 'Edit Category' : 'Manage Categories'}</h2>

      {/* Form Card */}
      <div style={formCardStyle}>
        <div style={uploadBoxStyle}>
          <input type="file" id="cat-img" hidden onChange={handleImageChange} accept="image/*" />
          <label htmlFor="cat-img" style={uploadLabel}>
            {formData.image ? (
              <img src={formData.image} alt="preview" style={previewStyle} />
            ) : (
              <div style={uploadPlaceholder}>
                <Upload size={20} color="#64748b" />
                <span style={{fontSize: '10px', color: '#64748b', marginTop: '5px'}}>IMAGE</span>
              </div>
            )}
          </label>
        </div>

        <div style={inputGroup}>
          <label style={labelStyle}>Category Name</label>
          <input
            type="text"
            placeholder="e.g. Appetizers"
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            style={inputStyle}
          />
        </div>

        <div style={inputGroup}>
          <label style={labelStyle}>Station</label>
          <select
            value={formData.station}
            onChange={(e) => setFormData({...formData, station: e.target.value})}
            style={selectStyle}
          >
            {stations.map(s => <option key={s.id} value={s.name}>{s.name}</option>)}
          </select>
        </div>

        <div style={{...inputGroup, flex: 2}}>
          <label style={labelStyle}>Description</label>
          <input
            type="text"
            placeholder="Brief details..."
            value={formData.description}
            onChange={(e) => setFormData({...formData, description: e.target.value})}
            style={inputStyle}
          />
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={handleSave} style={{...addButtonStyle, backgroundColor: editingId ? '#16a34a' : '#0f766e', color: '#fff'}}>
            {editingId ? <Check size={18} /> : <Plus size={18} />}
          </button>
          {editingId && <button onClick={resetForm} style={cancelButtonStyle}><X size={18} /></button>}
        </div>
      </div>

      {/* List Display */}
      <div style={listGridStyle}>
        <AnimatePresence>
          {categories.map(cat => (
            <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={cat.id} style={categoryCardStyle}>
              <div style={catImageBox}>
                {cat.image ? (
                  <img src={cat.image} alt={cat.name} style={catImgStyle} />
                ) : (
                  <ImageIcon size={24} color="#64748b" />
                )}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={catNameStyle}>{cat.name}</h4>
                  <small style={stationBadgeStyle}>{cat.station}</small>
                </div>
                <p style={descStyle}>{cat.description}</p>
              </div>

              <div style={actionGroupStyle}>
                <button onClick={() => startEdit(cat)} style={actionButtonStyle}><Pencil size={12} color="#475569" /></button>
                <button onClick={() => deleteCategory(cat.id)} style={actionButtonStyle}><Trash2 size={12} color="#ef4444" /></button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

// --- Styles ---
const containerStyle = { padding: '10px' };
const titleStyle = { color: '#0f172a', fontSize: '22px', fontWeight: '800', marginBottom: '22px' };
const formCardStyle = { display: 'flex', gap: '15px', alignItems: 'flex-end', backgroundColor: '#fff', padding: '20px', borderRadius: '16px', marginBottom: '30px', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 4px 20px rgba(15,23,42,0.03)' };
const uploadBoxStyle = { width: '60px', height: '60px', borderRadius: '12px', border: '2px dashed #cbd5e1', overflow: 'hidden', cursor: 'pointer', backgroundColor: '#f8fafc' };
const uploadLabel = { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' };
const uploadPlaceholder = { display: 'flex', flexDirection: 'column', alignItems: 'center' };
const previewStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const inputGroup = { display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 };
const labelStyle = { color: '#64748b', fontSize: '10px', fontWeight: '800', textTransform: 'uppercase' };
const inputStyle = { backgroundColor: '#f1f5f9', border: '1px solid rgba(148,163,184,0.12)', borderRadius: '10px', padding: '10px', color: '#0f172a', fontSize: '13px', outline: 'none' };
const selectStyle = { ...inputStyle, cursor: 'pointer' };
const addButtonStyle = { color: '#fff', padding: '10px', borderRadius: '10px', border: 'none', fontWeight: '800', cursor: 'pointer', height: '42px', width: '50px', display: 'flex', justifyContent: 'center', alignItems: 'center', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };
const cancelButtonStyle = { backgroundColor: '#e2e8f0', color: '#475569', padding: '10px', borderRadius: '10px', border: 'none', cursor: 'pointer', height: '42px' };
const listGridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '20px' };
const categoryCardStyle = { backgroundColor: '#fff', padding: '20px', borderRadius: '18px', display: 'flex', gap: '15px', border: '1px solid rgba(148,163,184,0.16)', alignItems: 'center', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' };
const catImageBox = { width: '70px', height: '70px', backgroundColor: '#f1f5f9', borderRadius: '14px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const catImgStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const catNameStyle = { margin: 0, fontSize: '16px', fontWeight: '700', color: '#0f172a' };
const descStyle = { margin: '5px 0 0 0', fontSize: '12px', color: '#64748b' };
const stationBadgeStyle = { color: '#0f766e', backgroundColor: '#ccfbf1', padding: '2px 8px', borderRadius: '6px', fontSize: '10px', fontWeight: '800', textTransform: 'uppercase' };
const actionGroupStyle = { display: 'flex', flexDirection: 'column', gap: '5px' };
const actionButtonStyle = { backgroundColor: '#f1f5f9', border: 'none', padding: '8px', borderRadius: '8px', cursor: 'pointer' };

export default CategoryManager;