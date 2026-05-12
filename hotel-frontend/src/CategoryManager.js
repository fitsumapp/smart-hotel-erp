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

  // 1. ዳታ ከመረጃ ቋቱ (Database) ለማምጣት
  const fetchCategories = async () => {
  try {
    const response = await axios.get(CATEGORY_API_BASE);
    // በደንብ እንዲታይ ዳታውን log አድርገው
    console.log("Categories Loaded:", response.data);
    setCategories(response.data);
  } catch (error) {
    console.error("ዳታ መጫን አልተቻለም:", error);
  }
};

  useEffect(() => {
    fetchCategories();
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
        await axios.put(`${CATEGORY_API_BASE}${editingId}/`, data);
      } else {
        await axios.post(CATEGORY_API_BASE, data);
      }
      fetchCategories(); // ዳታውን እንደገና አድስ
      resetForm();
    } catch (error) {
      console.error("መመዝገብ አልተቻለም:", error);
      alert("Error saving category. Check if Django is running and CORS is enabled.");
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
        await axios.delete(`${CATEGORY_API_BASE}${id}/`);
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
          <button onClick={handleSave} style={{...addButtonStyle, backgroundColor: editingId ? '#10b981' : '#0ff'}}>
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
                  <ImageIcon size={24} color="#1f2937" />
                )}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <h4 style={catNameStyle}>{cat.name}</h4>
                  <small style={stationBadgeStyle}>{cat.station}</small>
                </div>
                <p style={descStyle}>{cat.description}</p>
              </div>

              <div style={actionGroupStyle}>
                <button onClick={() => startEdit(cat)} style={actionButtonStyle}><Pencil size={12} color="#94a3b8" /></button>
                <button onClick={() => deleteCategory(cat.id)} style={actionButtonStyle}><Trash2 size={12} color="#ef4444" /></button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

// --- Styles (ካለህበት ይቀጥላሉ) ---
const containerStyle = { padding: '10px' };
const titleStyle = { color: '#fff', fontSize: '22px', fontWeight: '800', marginBottom: '25px' };
const formCardStyle = { display: 'flex', gap: '15px', alignItems: 'flex-end', backgroundColor: '#111827', padding: '15px', borderRadius: '15px', marginBottom: '30px', border: '1px solid #1f2937' };
const uploadBoxStyle = { width: '60px', height: '60px', borderRadius: '12px', border: '2px dashed #374151', overflow: 'hidden', cursor: 'pointer' };
const uploadLabel = { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' };
const uploadPlaceholder = { display: 'flex', flexDirection: 'column', alignItems: 'center' };
const previewStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const inputGroup = { display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 };
const labelStyle = { color: '#94a3b8', fontSize: '10px', fontWeight: '800', textTransform: 'uppercase' };
const inputStyle = { backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '10px', padding: '10px', color: '#fff', fontSize: '13px', outline: 'none' };
const selectStyle = { ...inputStyle, cursor: 'pointer' };
const addButtonStyle = { color: '#000', padding: '10px', borderRadius: '10px', border: 'none', fontWeight: '800', cursor: 'pointer', height: '42px', width: '50px', display: 'flex', justifyContent: 'center', alignItems: 'center' };
const cancelButtonStyle = { backgroundColor: '#374151', color: '#fff', padding: '10px', borderRadius: '10px', border: 'none', cursor: 'pointer', height: '42px' };
const listGridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '20px' };
const categoryCardStyle = { backgroundColor: '#111827', padding: '15px', borderRadius: '18px', display: 'flex', gap: '15px', border: '1px solid #1f2937', alignItems: 'center' };
const catImageBox = { width: '70px', height: '70px', backgroundColor: '#1f2937', borderRadius: '14px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const catImgStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const catNameStyle = { margin: 0, fontSize: '16px', fontWeight: '700', color: '#fff' };
const descStyle = { margin: '5px 0 0 0', fontSize: '12px', color: '#64748b' };
const stationBadgeStyle = { color: '#0ff', fontSize: '10px', fontWeight: '800', textTransform: 'uppercase' };
const actionGroupStyle = { display: 'flex', flexDirection: 'column', gap: '5px' };
const actionButtonStyle = { backgroundColor: '#1f2937', border: 'none', padding: '8px', borderRadius: '8px', cursor: 'pointer' };

export default CategoryManager;