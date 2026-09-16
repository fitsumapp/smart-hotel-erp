import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Package, LogOut, AlertTriangle, CheckCircle, RefreshCw,
  Plus, Users, DollarSign, ArrowRight,
  ShoppingCart, Truck, Printer, Trash2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const InventoryDashboard = ({ userData, handleLogout }) => {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Tab states: 'overview', 'items', 'actions', 'recipes', 'ledger', 'categories', 'suppliers', 'reports'
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedReport, setSelectedReport] = useState(null);

  // Report filter states
  const [reportValCategory, setReportValCategory] = useState('');
  const [reportValSearch, setReportValSearch] = useState('');
  const [reportLowCategory, setReportLowCategory] = useState('');
  const [reportLowSupplier, setReportLowSupplier] = useState('');
  const [reportConsumptionDept, setReportConsumptionDept] = useState('');
  
  // Set default dates for consumption report (past 30 days)
  const [reportConsumptionStart, setReportConsumptionStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split('T')[0];
  });
  const [reportConsumptionEnd, setReportConsumptionEnd] = useState(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [reportRecipeMarginFilter, setReportRecipeMarginFilter] = useState('all');
  const [reportRecipeCategory, setReportRecipeCategory] = useState('');

  // Modal / Form trigger states
  const [isItemModalOpen, setIsItemModalOpen] = useState(false);
  const [isSupplierModalOpen, setIsSupplierModalOpen] = useState(false);
  const [isRecipeModalOpen, setIsRecipeModalOpen] = useState(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);

  // Edit modal states
  const [editItem, setEditItem] = useState(null);
  const [editCategory, setEditCategory] = useState(null);
  const [editSupplier, setEditSupplier] = useState(null);

  // Form states
  const [newItem, setNewItem] = useState({ item_code: '', name: '', category: '', unit: 'pcs', min_reorder_level: '5.00', unit_cost: '0.00', selling_price: '0.00', last_supplier: '' });
  const [newSupplier, setNewSupplier] = useState({ name: '', contact_person: '', phone: '', email: '', address: '', tin_number: '', supplied_categories: [], supply_items: '' });
  const [newCategory, setNewCategory] = useState({ name: '', description: '', category_type: 'f_and_b' });
  const [newGRN, setNewGRN] = useState({ item: '', quantity: '', unit_cost: '', supplier: '', reference_number: '', notes: '' });
  const [newDispatch, setNewDispatch] = useState({ item: '', quantity: '', department: 'Kitchen', room: '', notes: '' });
  const [selectedRecipeMenu, setSelectedRecipeMenu] = useState('');
  const [recipeRows, setRecipeRows] = useState([{ ingredient: '', quantity_required: '' }]);
  const [rooms, setRooms] = useState([]);
  const [itemsTypeFilter, setItemsTypeFilter] = useState('all');
  const [dispatchTargetType, setDispatchTargetType] = useState('department');

  useEffect(() => {
    if (selectedRecipeMenu) {
      const existing = recipes.filter(r => r.menu_item === parseInt(selectedRecipeMenu));
      if (existing.length > 0) {
        setRecipeRows(existing.map(r => ({
          id: r.id, // optional: to track existing row id
          ingredient: r.ingredient.toString(),
          quantity_required: r.quantity_required.toString()
        })));
      } else {
        setRecipeRows([{ ingredient: '', quantity_required: '' }]);
      }
    } else {
      setRecipeRows([{ ingredient: '', quantity_required: '' }]);
    }
  }, [selectedRecipeMenu, recipes]);


  const getHeaders = () => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [itemsRes, catsRes, supsRes, menusRes, recipesRes, ledgerRes, statsRes, roomsRes] = await Promise.all([
        axios.get(`${API_BASE}inventory-items/`, { headers }),
        axios.get(`${API_BASE}inventory-categories/`, { headers }),
        axios.get(`${API_BASE}suppliers/`, { headers }),
        axios.get(`${API_BASE}menu-items/`, { headers }),
        axios.get(`${API_BASE}recipes/`, { headers }),
        axios.get(`${API_BASE}stock-transactions/`, { headers }),
        axios.get(`${API_BASE}inventory/dashboard-stats/`, { headers }),
        axios.get(`${API_BASE}rooms/`, { headers }).catch(() => ({ data: [] }))
      ]);
      setItems(itemsRes.data || []);
      setCategories(catsRes.data || []);
      setSuppliers(supsRes.data || []);
      setMenuItems(menusRes.data || []);
      setRecipes(recipesRes.data || []);
      setLedger(ledgerRes.data || []);
      setStats(statsRes.data || null);
      setRooms(roomsRes.data || []);
    } catch (err) {
      console.error('Inventory fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // -- API Submissions --

  const handleCreateItem = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...newItem,
        last_supplier: newItem.last_supplier || null
      };
      await axios.post(`${API_BASE}inventory-items/`, payload, { headers: getHeaders() });
      setIsItemModalOpen(false);
      setNewItem({ item_code: '', name: '', category: '', unit: 'pcs', min_reorder_level: '5.00', unit_cost: '0.00', selling_price: '0.00', last_supplier: '' });
      fetchData();
    } catch (err) {
      alert("Error creating item: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleCreateSupplier = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API_BASE}suppliers/`, newSupplier, { headers: getHeaders() });
      setIsSupplierModalOpen(false);
      setNewSupplier({ name: '', contact_person: '', phone: '', email: '', address: '', tin_number: '', supplied_categories: [], supply_items: '' });
      fetchData();
    } catch (err) {
      alert("Error creating supplier: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleCreateCategory = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API_BASE}inventory-categories/`, newCategory, { headers: getHeaders() });
      setIsCategoryModalOpen(false);
      setNewCategory({ name: '', description: '', category_type: 'f_and_b' });
      fetchData();
    } catch (err) {
      alert("Error creating category: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  // --- Edit handlers ---
  const handleEditItem = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...editItem,
        last_supplier: editItem.last_supplier || null
      };
      await axios.patch(`${API_BASE}inventory-items/${editItem.id}/`, payload, { headers: getHeaders() });
      setEditItem(null);
      fetchData();
    } catch (err) {
      alert("Error updating item: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleEditCategory = async (e) => {
    e.preventDefault();
    try {
      await axios.put(`${API_BASE}inventory-categories/${editCategory.id}/`, editCategory, { headers: getHeaders() });
      setEditCategory(null);
      fetchData();
    } catch (err) {
      alert("Error updating category: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleEditSupplier = async (e) => {
    e.preventDefault();
    try {
      await axios.put(`${API_BASE}suppliers/${editSupplier.id}/`, editSupplier, { headers: getHeaders() });
      setEditSupplier(null);
      fetchData();
    } catch (err) {
      alert("Error updating supplier: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleDeleteItem = async (item) => {
    if (window.confirm(`Are you sure you want to delete "${item.name}"?`)) {
      try {
        await axios.delete(`${API_BASE}inventory-items/${item.id}/`, { headers: getHeaders() });
        fetchData();
      } catch (err) {
        alert('Error deleting item. It may be used in recipes or transactions.');
      }
    }
  };

  const handleReceiveGRN = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        item: newGRN.item,
        transaction_type: 'purchase',
        quantity: parseFloat(newGRN.quantity),
        unit_cost: parseFloat(newGRN.unit_cost),
        supplier: newGRN.supplier || null,
        reference_number: newGRN.reference_number,
        notes: newGRN.notes
      };
      await axios.post(`${API_BASE}stock-transactions/`, payload, { headers: getHeaders() });
      alert("Stock Received Successfully!");
      setNewGRN({ item: '', quantity: '', unit_cost: '', supplier: '', reference_number: '', notes: '' });
      fetchData();
    } catch (err) {
      alert("Error recording GRN: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const handleDispatchStock = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        item: newDispatch.item,
        transaction_type: 'issuance',
        quantity: parseFloat(newDispatch.quantity),
        unit_cost: items.find(i => i.id === parseInt(newDispatch.item))?.unit_cost || 0,
        destination_dept: dispatchTargetType === 'department' ? newDispatch.department : '',
        destination_room: dispatchTargetType === 'room' ? newDispatch.room : '',
        notes: dispatchTargetType === 'room'
          ? `Dispatched to Room ${newDispatch.room}. ${newDispatch.notes}`
          : `Dispatched to ${newDispatch.department}. ${newDispatch.notes}`
      };
      await axios.post(`${API_BASE}stock-transactions/`, payload, { headers: getHeaders() });
      alert("Stock Dispatched Successfully!");
      setNewDispatch({ item: '', quantity: '', department: 'Kitchen', room: '', notes: '' });
      setDispatchTargetType('department');
      fetchData();
    } catch (err) {
      alert("Error dispatching stock: " + JSON.stringify(err.response?.data || err.message));
    }
  };

  const addRecipeRow = () => {
    setRecipeRows([...recipeRows, { ingredient: '', quantity_required: '' }]);
  };

  const removeRecipeRow = (index) => {
    const updated = [...recipeRows];
    updated.splice(index, 1);
    setRecipeRows(updated);
  };

  const handleRowChange = (index, field, value) => {
    const updated = [...recipeRows];
    updated[index][field] = value;
    setRecipeRows(updated);
  };

  const handleSaveRecipeBOM = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        menu_item: parseInt(selectedRecipeMenu),
        ingredients: recipeRows
          .filter(row => row.ingredient && row.quantity_required)
          .map(row => ({
            ingredient: parseInt(row.ingredient),
            quantity_required: parseFloat(row.quantity_required)
          }))
      };
      
      await axios.post(`${API_BASE}recipes/bulk-save/`, payload, { headers: getHeaders() });
      setIsRecipeModalOpen(false);
      setSelectedRecipeMenu('');
      setRecipeRows([{ ingredient: '', quantity_required: '' }]);
      alert("Recipe Saved successfully!");
      fetchData();
    } catch (err) {
      alert("Error saving recipe: " + JSON.stringify(err.response?.data || err.message));
    }
  };


  const printReport = () => {
    window.print();
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div style={loadingStyle}>
          <Package size={48} color="#0f766e" className="animate-spin" style={{ marginBottom: '15px' }} />
          <p style={{ color: '#94a3b8', fontFamily: "'Plus Jakarta Sans', sans-serif" }}>Loading inventory data…</p>
        </div>
      );
    }

    switch (activeTab) {
      case 'overview':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            {/* Stats row */}
            <div style={statsGrid} className="inventory-stats-grid">
              <StatCard
                icon={<DollarSign size={22} color="#0f766e" />}
                title="Total Stock Value"
                value={`${parseFloat(stats?.total_valuation || 0).toLocaleString()} ETB`}
                color="#0f766e"
              />
              <StatCard
                icon={<Package size={22} color="#0284c7" />}
                title="Total Stock Items"
                value={stats?.total_items || 0}
                color="#0284c7"
              />
              <StatCard
                icon={<AlertTriangle size={22} color="#d97706" />}
                title="Low Stock Warnings"
                value={stats?.low_stock_count || 0}
                color="#d97706"
              />
              <StatCard
                icon={<Users size={22} color="#0d9488" />}
                title="Active Suppliers"
                value={stats?.suppliers_count || 0}
                color="#0d9488"
              />
            </div>

            {/* Main panels */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '25px' }}>
              {/* Low Stock Alert Table */}
              <div style={cardStyle}>
                <div style={cardHeaderStyle}>
                  <h3 style={cardTitleStyle}>⚠️ Low Stock Warnings</h3>
                  <span style={badgeWarningStyle}>{stats?.low_stock_count || 0} Items</span>
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={tableStyle}>
                    <thead>
                      <tr style={theadStyle}>
                        <th style={thStyle}>Code</th>
                        <th style={thStyle}>Item Name</th>
                        <th style={thStyle}>Category</th>
                        <th style={thStyle}>Current Stock</th>
                        <th style={thStyle}>Min Required</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats?.low_stock_items?.length === 0 ? (
                        <tr>
                          <td colSpan="5" style={{ ...tdStyle, textAlign: 'center', color: '#64748b', padding: '30px' }}>
                            🎉 Great! All inventory items are well-stocked.
                          </td>
                        </tr>
                      ) : (
                        stats?.low_stock_items?.map(item => (
                          <tr key={item.id} style={trStyle}>
                            <td style={{ ...tdStyle, fontWeight: '700', color: '#0f766e' }}>{item.item_code}</td>
                            <td style={tdStyle}>{item.name}</td>
                            <td style={tdStyle}>
                              <span style={badgeCategoryStyle}>{item.category_name}</span>
                            </td>
                            <td style={{ ...tdStyle, color: '#ef4444', fontWeight: '700' }}>
                              {parseFloat(item.current_stock).toFixed(2)} {item.unit}
                            </td>
                            <td style={tdStyle}>{parseFloat(item.min_reorder_level).toFixed(2)} {item.unit}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Department Stock Quick Guide */}
              <div style={cardStyle}>
                <h3 style={{ ...cardTitleStyle, marginBottom: '15px' }}>🏢 Department Dispatches</h3>
                <p style={{ color: '#64748b', fontSize: '13px', lineHeight: '1.5', marginBottom: '20px' }}>
                  Distribute goods from the central warehouse to kitchen, bar, or housekeeping stations. Use the <strong>Stock Actions</strong> tab to dispatch items.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={deptProgressStyle}>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#334155' }}>Kitchen Pantry</span>
                    <div style={progressBarContainer}><div style={{ ...progressBar, width: '70%', backgroundColor: '#0f766e' }} /></div>
                  </div>
                  <div style={deptProgressStyle}>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#334155' }}>Bar Stock</span>
                    <div style={progressBarContainer}><div style={{ ...progressBar, width: '45%', backgroundColor: '#7c3aed' }} /></div>
                  </div>
                  <div style={deptProgressStyle}>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#334155' }}>Housekeeping (Toiletries)</span>
                    <div style={progressBarContainer}><div style={{ ...progressBar, width: '85%', backgroundColor: '#0284c7' }} /></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case 'items':
        const filteredItems = items.filter(item => {
          if (itemsTypeFilter === 'all') return true;
          return item.category_type === itemsTypeFilter;
        });

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>Ingredients & Stock List</h2>
                <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Monitor, add, and inspect all raw ingredients and stock items in your warehouse.</p>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => setIsSupplierModalOpen(true)} style={btnSecondaryStyle}>
                  <Users size={16} style={{ marginRight: '6px' }} /> Add Supplier
                </button>
                <button onClick={() => setIsItemModalOpen(true)} style={btnPrimaryStyle}>
                  <Plus size={16} style={{ marginRight: '6px' }} /> Add Ingredient / Item
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', backgroundColor: 'rgba(241,245,249,0.7)', padding: '5px', borderRadius: '12px', width: 'fit-content', border: '1px solid rgba(148,163,184,0.1)' }}>
              <button 
                onClick={() => setItemsTypeFilter('all')} 
                style={{
                  padding: '6px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  backgroundColor: itemsTypeFilter === 'all' ? '#0f766e' : 'transparent',
                  color: itemsTypeFilter === 'all' ? '#ffffff' : '#64748b',
                  transition: 'all 0.2s'
                }}
              >
                Show All
              </button>
              <button 
                onClick={() => setItemsTypeFilter('f_and_b')} 
                style={{
                  padding: '6px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  backgroundColor: itemsTypeFilter === 'f_and_b' ? '#0f766e' : 'transparent',
                  color: itemsTypeFilter === 'f_and_b' ? '#ffffff' : '#64748b',
                  transition: 'all 0.2s'
                }}
              >
                Food & Beverage (F&B)
              </button>
              <button 
                onClick={() => setItemsTypeFilter('housekeeping')} 
                style={{
                  padding: '6px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  backgroundColor: itemsTypeFilter === 'housekeeping' ? '#0f766e' : 'transparent',
                  color: itemsTypeFilter === 'housekeeping' ? '#ffffff' : '#64748b',
                  transition: 'all 0.2s'
                }}
              >
                Housekeeping & Rooms
              </button>
            </div>

            <div style={cardStyle}>
              <div style={{ overflowX: 'auto' }}>
                <table style={tableStyle}>
                  <thead>
                    <tr style={theadStyle}>
                      <th style={thStyle}>Code</th>
                      <th style={thStyle}>Item Name</th>
                      <th style={thStyle}>Category</th>
                      <th style={thStyle}>Current Stock</th>
                      <th style={thStyle}>Min Level</th>
                      <th style={thStyle}>Unit Cost</th>
                      <th style={thStyle}>Total Value</th>
                      <th style={thStyle}>Supplier</th>
                      <th style={thStyle}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map(item => {
                      const isLow = parseFloat(item.current_stock) < parseFloat(item.min_reorder_level);
                      return (
                        <tr key={item.id} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#0f766e' }}>{item.item_code}</td>
                          <td style={tdStyle}>{item.name}</td>
                          <td style={tdStyle}>
                            <span style={badgeCategoryStyle}>
                              {item.category_name} ({item.category_type === 'f_and_b' ? 'F&B' : 'Room'})
                            </span>
                          </td>
                          <td style={{ ...tdStyle, fontWeight: '700', color: isLow ? '#ef4444' : '#10b981' }}>
                            {parseFloat(item.current_stock).toFixed(2)} {item.unit}
                            {isLow && <span style={{ marginLeft: '6px', fontSize: '10px', color: '#ef4444' }}>(Low)</span>}
                          </td>
                          <td style={tdStyle}>{parseFloat(item.min_reorder_level).toFixed(2)} {item.unit}</td>
                          <td style={tdStyle}>{parseFloat(item.unit_cost).toFixed(2)} ETB</td>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#334155' }}>
                            {(parseFloat(item.current_stock) * parseFloat(item.unit_cost)).toFixed(2)} ETB
                          </td>
                          <td style={tdStyle}>{item.supplier_name || '—'}</td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button onClick={() => setEditItem({ ...item, category: item.category?.toString() || '', last_supplier: item.last_supplier?.toString() || '' })} style={editBtnStyle}>Edit</button>
                              <button onClick={() => handleDeleteItem(item)} style={deleteBtnStyle}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 'actions':
        return (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '30px' }}>
            {/* Purchasing Form */}
            <div style={cardStyle}>
              <div style={formHeaderStyle}>
                <Truck size={24} color="#0f766e" />
                <h3 style={{ margin: 0, color: '#0f172a', fontWeight: '800' }}>Purchase Stock (Stock-In / GRN)</h3>
              </div>
              <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '20px' }}>Record incoming inventory goods from purchase orders or suppliers.</p>
              
              <form onSubmit={handleReceiveGRN} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Select Stock Item</label>
                  <select required style={inputStyle} value={newGRN.item} onChange={e => setNewGRN({ ...newGRN, item: e.target.value })}>
                    <option value="">-- Choose Item --</option>
                    {items.map(item => (
                      <option key={item.id} value={item.id}>{item.name} ({item.item_code})</option>
                    ))}
                  </select>
                </div>

                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Quantity Received</label>
                    <input required type="number" step="0.01" style={inputStyle} value={newGRN.quantity} placeholder="e.g. 50" onChange={e => setNewGRN({ ...newGRN, quantity: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Unit Cost (ETB)</label>
                    <input required type="number" step="0.01" style={inputStyle} value={newGRN.unit_cost} placeholder="e.g. 12.50" onChange={e => setNewGRN({ ...newGRN, unit_cost: e.target.value })} />
                  </div>
                </div>

                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Supplier</label>
                    <select style={inputStyle} value={newGRN.supplier} onChange={e => setNewGRN({ ...newGRN, supplier: e.target.value })}>
                      <option value="">-- Choose Supplier --</option>
                      {suppliers.map(sup => (
                        <option key={sup.id} value={sup.id}>{sup.name}</option>
                      ))}
                    </select>
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Reference/Invoice #</label>
                    <input type="text" style={inputStyle} value={newGRN.reference_number} placeholder="e.g. INV-9021" onChange={e => setNewGRN({ ...newGRN, reference_number: e.target.value })} />
                  </div>
                </div>

                <div style={formGroupStyle}>
                  <label style={labelStyle}>Transaction Notes</label>
                  <textarea style={inputStyle} rows="2" value={newGRN.notes} placeholder="Additional notes about delivery..." onChange={e => setNewGRN({ ...newGRN, notes: e.target.value })} />
                </div>

                <button type="submit" style={btnPrimaryStyle}>
                  <CheckCircle size={16} style={{ marginRight: '6px' }} /> Record Stock-In
                </button>
              </form>
            </div>

            {/* Issuance Form */}
            <div style={cardStyle}>
              <div style={formHeaderStyle}>
                <ShoppingCart size={24} color="#0284c7" />
                <h3 style={{ margin: 0, color: '#0f172a', fontWeight: '800' }}>Issue / Consume Stock (Stock-Out)</h3>
              </div>
              <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '20px' }}>Dispatch warehouse stock items for internal department consumption.</p>

              <form onSubmit={handleDispatchStock} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Select Stock Item</label>
                  <select required style={inputStyle} value={newDispatch.item} onChange={e => setNewDispatch({ ...newDispatch, item: e.target.value })}>
                    <option value="">-- Choose Item --</option>
                    {items.map(item => (
                      <option key={item.id} value={item.id}>{item.name} (Current: {parseFloat(item.current_stock).toFixed(2)} {item.unit})</option>
                    ))}
                  </select>
                </div>

                <div style={formGroupStyle}>
                  <label style={labelStyle}>Dispatch Destination Type</label>
                  <div style={{ display: 'flex', gap: '20px', margin: '5px 0' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#334155', fontWeight: '600', cursor: 'pointer' }}>
                      <input type="radio" checked={dispatchTargetType === 'department'} onChange={() => setDispatchTargetType('department')} style={{ accentColor: '#0ea5e9' }} />
                      Department Station
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#334155', fontWeight: '600', cursor: 'pointer' }}>
                      <input type="radio" checked={dispatchTargetType === 'room'} onChange={() => setDispatchTargetType('room')} style={{ accentColor: '#0ea5e9' }} />
                      Specific Room #
                    </label>
                  </div>
                </div>

                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Quantity to Issue</label>
                    <input required type="number" step="0.01" style={inputStyle} value={newDispatch.quantity} placeholder="e.g. 5" onChange={e => setNewDispatch({ ...newDispatch, quantity: e.target.value })} />
                  </div>
                  {dispatchTargetType === 'department' ? (
                    <div style={formGroupStyle}>
                      <label style={labelStyle}>Destination Station</label>
                      <select required style={inputStyle} value={newDispatch.department} onChange={e => setNewDispatch({ ...newDispatch, department: e.target.value })}>
                        <option value="Kitchen">Kitchen Pantry</option>
                        <option value="Bar">Bar Lounge</option>
                        <option value="Housekeeping">Housekeeping Supplies</option>
                        <option value="Maintenance">Maintenance Log Parts</option>
                        <option value="Administration">General Office</option>
                      </select>
                    </div>
                  ) : (
                    <div style={formGroupStyle}>
                      <label style={labelStyle}>Destination Room</label>
                      <select required style={inputStyle} value={newDispatch.room} onChange={e => setNewDispatch({ ...newDispatch, room: e.target.value })}>
                        <option value="">-- Select Room --</option>
                        {rooms.map(rm => (
                          <option key={rm.id} value={rm.room_number}>Room {rm.room_number} ({rm.status})</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                <div style={formGroupStyle}>
                  <label style={labelStyle}>Reason / Notes</label>
                  <textarea style={inputStyle} rows="3" value={newDispatch.notes} placeholder="e.g. Toiletries for Room 204 or oil for bar generator..." onChange={e => setNewDispatch({ ...newDispatch, notes: e.target.value })} />
                </div>

                <button type="submit" style={{ ...btnPrimaryStyle, backgroundColor: '#0284c7' }}>
                  <ArrowRight size={16} style={{ marginRight: '6px' }} /> Record Stock-Out
                </button>
              </form>
            </div>
          </div>
        );

      case 'recipes':
        // Group the flat recipes array by menu_item
        const groupedRecipes = {};
        recipes.forEach(r => {
          if (!groupedRecipes[r.menu_item]) {
            groupedRecipes[r.menu_item] = {
              menu_item_id: r.menu_item,
              menu_item_name: r.menu_item_name,
              selling_price: parseFloat(menuItems.find(mi => mi.id === r.menu_item)?.price || 0),
              ingredients: []
            };
          }
          const itemCost = parseFloat(items.find(i => i.id === r.ingredient)?.unit_cost || 0);
          const quantity = parseFloat(r.quantity_required);
          groupedRecipes[r.menu_item].ingredients.push({
            id: r.id,
            ingredient_id: r.ingredient,
            ingredient_name: r.ingredient_name,
            ingredient_unit: r.ingredient_unit,
            quantity_required: quantity,
            unit_cost: itemCost,
            total_cost: quantity * itemCost
          });
        });

        const groups = Object.values(groupedRecipes);

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>Recipe Builder & Bill of Materials (BOM)</h2>
                <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Define the exact ingredients and portion sizes for menu items to automate stock deduction and calculate exact profit margins.</p>
              </div>
              <button onClick={() => {
                setSelectedRecipeMenu('');
                setRecipeRows([{ ingredient: '', quantity_required: '' }]);
                setIsRecipeModalOpen(true);
              }} style={btnPrimaryStyle}>
                <Plus size={16} style={{ marginRight: '6px' }} /> Map New Recipe
              </button>
            </div>

            {groups.length === 0 ? (
              <div style={cardStyle}>
                <div style={{ textAlign: 'center', color: '#64748b', padding: '50px 30px' }}>
                  <span style={{ fontSize: '48px' }}>🍽️</span>
                  <h3 style={{ margin: '15px 0 5px', color: '#334155' }}>No Recipes Mapped Yet</h3>
                  <p style={{ margin: 0, color: '#94a3b8', fontSize: '14px', maxWidth: '400px', marginLeft: 'auto', marginRight: 'auto' }}>
                    Connect your F&B menu items to raw inventory ingredients to calculate margins and activate automatic stock deduction upon payment.
                  </p>
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '25px' }}>
                {groups.map(group => {
                  const totalRawCost = group.ingredients.reduce((sum, ing) => sum + ing.total_cost, 0);
                  const marginAmount = group.selling_price - totalRawCost;
                  const marginPct = group.selling_price > 0 ? (marginAmount / group.selling_price) * 100 : 0;
                  
                  return (
                    <div key={group.menu_item_id} style={{
                      ...cardStyle,
                      border: '1px solid #e2e8f0',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      minHeight: '220px'
                    }}>
                      <div>
                        {/* Group Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px dashed #e2e8f0', paddingBottom: '12px', marginBottom: '15px' }}>
                          <div>
                            <h3 style={{ margin: 0, color: '#0f172a', fontWeight: '800', fontSize: '16px' }}>{group.menu_item_name}</h3>
                            <span style={{ fontSize: '12px', color: '#64748b', fontWeight: '600' }}>
                              Price: <strong style={{ color: '#0f766e' }}>{group.selling_price.toFixed(2)} ETB</strong>
                            </span>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '14px', fontWeight: '800', color: '#334155' }}>
                              Raw Cost: <span style={{ color: '#0f766e' }}>{totalRawCost.toFixed(2)} ETB</span>
                            </div>
                            <span style={{
                              fontSize: '11px',
                              fontWeight: '700',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              backgroundColor: marginPct > 40 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                              color: marginPct > 40 ? '#10b981' : '#f59e0b'
                            }}>
                              Margin: {marginPct.toFixed(1)}%
                            </span>
                          </div>
                        </div>

                        {/* Ingredients List */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '15px' }}>
                          {group.ingredients.map(ing => (
                            <div key={ing.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px', color: '#475569' }}>
                              <span>• {ing.ingredient_name}</span>
                              <span style={{ color: '#64748b' }}>
                                <strong style={{ color: '#0f172a' }}>{ing.quantity_required} {ing.ingredient_unit}</strong> ({ing.total_cost.toFixed(2)} ETB)
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Card Actions */}
                      <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '12px', display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: 'auto' }}>
                        <button onClick={() => {
                          setSelectedRecipeMenu(group.menu_item_id.toString());
                          setIsRecipeModalOpen(true);
                        }} style={{
                          padding: '6px 12px',
                          backgroundColor: 'rgba(15, 118, 110, 0.1)',
                          border: 'none',
                          color: '#0f766e',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: '700',
                          cursor: 'pointer'
                        }}>
                          Edit Recipe
                        </button>
                        <button onClick={async () => {
                          if (window.confirm(`Delete entire recipe for ${group.menu_item_name}?`)) {
                            try {
                              await axios.post(`${API_BASE}recipes/bulk-save/`, {
                                menu_item: group.menu_item_id,
                                ingredients: []
                              }, { headers: getHeaders() });
                              alert("Recipe deleted.");
                              fetchData();
                            } catch (err) {
                              alert("Error deleting recipe.");
                            }
                          }
                        }} style={{
                          padding: '6px 12px',
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          border: 'none',
                          color: '#ef4444',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: '700',
                          cursor: 'pointer'
                        }}>
                          Delete Recipe
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );

      case 'ledger':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>Stock Ledger & Audit Trail</h2>
                <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Chronological timeline of all purchases, dispatches, adjustments, and auto-deductions.</p>
              </div>
              <button onClick={printReport} style={btnSecondaryStyle}>
                <Printer size={16} style={{ marginRight: '6px' }} /> Print Stock Audit
              </button>
            </div>

            <div style={cardStyle}>
              <div style={{ overflowX: 'auto' }}>
                <table style={tableStyle}>
                  <thead>
                    <tr style={theadStyle}>
                      <th style={thStyle}>Timestamp</th>
                      <th style={thStyle}>Item Name</th>
                      <th style={thStyle}>Type</th>
                      <th style={thStyle}>Quantity</th>
                      <th style={thStyle}>Cost/Val</th>
                      <th style={thStyle}>Ref Invoice #</th>
                      <th style={thStyle}>Logged By</th>
                      <th style={thStyle}>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.map(tx => {
                      const typeLabel = tx.transaction_type === 'purchase' ? 'Stock-In' :
                                        tx.transaction_type === 'issuance' ? 'Dispatch' :
                                        tx.transaction_type === 'sale_deduction' ? 'Auto-Deduct' : 'Adjustment';
                      const isAddition = tx.transaction_type === 'purchase' || (tx.transaction_type === 'adjustment' && parseFloat(tx.quantity) > 0);
                      
                      return (
                        <tr key={tx.id} style={trStyle}>
                          <td style={{ ...tdStyle, color: '#64748b', fontSize: '12px' }}>
                            {new Date(tx.timestamp).toLocaleString()}
                          </td>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#1e293b' }}>{tx.item_name}</td>
                          <td style={tdStyle}>
                            <span style={{
                              ...badgeStyle,
                              backgroundColor: tx.transaction_type === 'purchase' ? 'rgba(16,185,129,0.1)' :
                                               tx.transaction_type === 'issuance' ? 'rgba(14,165,233,0.1)' : 'rgba(245,158,11,0.1)',
                              color: tx.transaction_type === 'purchase' ? '#10b981' :
                                     tx.transaction_type === 'issuance' ? '#0ea5e9' : '#f59e0b',
                              border: `1px solid ${tx.transaction_type === 'purchase' ? '#10b981' :
                                                   tx.transaction_type === 'issuance' ? '#0ea5e9' : '#f59e0b'}`
                            }}>
                              {typeLabel}
                            </span>
                          </td>
                          <td style={{ ...tdStyle, fontWeight: '700', color: isAddition ? '#10b981' : '#ef4444' }}>
                            {isAddition ? '+' : '-'}{parseFloat(tx.quantity).toFixed(2)} {tx.item_unit}
                          </td>
                          <td style={tdStyle}>{(parseFloat(tx.quantity) * parseFloat(tx.unit_cost)).toFixed(2)} ETB</td>
                          <td style={tdStyle}>{tx.reference_number || '—'}</td>
                          <td style={{ ...tdStyle, color: '#64748b' }}>{tx.logged_by_username || 'system'}</td>
                          <td style={{ ...tdStyle, fontSize: '12px', color: '#64748b', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={tx.notes}>
                            {tx.notes || '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 'categories':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>Category List</h2>
                <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Manage groups and classifications for your ingredients and materials.</p>
              </div>
              <button onClick={() => setIsCategoryModalOpen(true)} style={btnPrimaryStyle}>
                <Plus size={16} style={{ marginRight: '6px' }} /> Add Category
              </button>
            </div>

            <div style={cardStyle}>
              <div style={{ overflowX: 'auto' }}>
                <table style={tableStyle}>
                  <thead>
                    <tr style={theadStyle}>
                      <th style={thStyle}>Category Name</th>
                      <th style={thStyle}>Description</th>
                      <th style={thStyle}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.length === 0 ? (
                      <tr>
                        <td colSpan="3" style={{ ...tdStyle, textAlign: 'center', color: '#64748b', padding: '30px' }}>
                          🗂️ No categories created yet. Click 'Add Category' to begin.
                        </td>
                      </tr>
                    ) : (
                      categories.map(cat => (
                        <tr key={cat.id} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#0f172a' }}>{cat.name}</td>
                          <td style={tdStyle}>{cat.description || '—'}</td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button onClick={() => setEditCategory({ ...cat })} style={editBtnStyle}>Edit</button>
                              <button onClick={async () => {
                                if (window.confirm(`Are you sure you want to delete the category "${cat.name}"?`)) {
                                  try {
                                    await axios.delete(`${API_BASE}inventory-categories/${cat.id}/`, { headers: getHeaders() });
                                    fetchData();
                                  } catch (err) {
                                    alert("Error deleting category. It might be in use by stock items.");
                                  }
                                }
                              }} style={deleteBtnStyle}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 'suppliers':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>Supplier List</h2>
                <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Manage your vendors and supply partners.</p>
              </div>
              <button onClick={() => setIsSupplierModalOpen(true)} style={btnPrimaryStyle}>
                <Plus size={16} style={{ marginRight: '6px' }} /> Add Supplier
              </button>
            </div>

            <div style={cardStyle}>
              <div style={{ overflowX: 'auto' }}>
                <table style={tableStyle}>
                  <thead>
                    <tr style={theadStyle}>
                      <th style={thStyle}>Company Name</th>
                      <th style={thStyle}>Contact Person</th>
                      <th style={thStyle}>Phone</th>
                      <th style={thStyle}>Email</th>
                      <th style={thStyle}>TIN Number</th>
                      <th style={thStyle}>Supplied Categories</th>
                      <th style={thStyle}>Specific Items</th>
                      <th style={thStyle}>Address</th>
                      <th style={thStyle}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.length === 0 ? (
                      <tr>
                        <td colSpan="9" style={{ ...tdStyle, textAlign: 'center', color: '#64748b', padding: '30px' }}>
                          🚚 No suppliers added yet. Click 'Add Supplier' to begin.
                        </td>
                      </tr>
                    ) : (
                      suppliers.map(sup => (
                        <tr key={sup.id} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#0f172a' }}>{sup.name}</td>
                          <td style={tdStyle}>{sup.contact_person || '—'}</td>
                          <td style={tdStyle}>{sup.phone || '—'}</td>
                          <td style={tdStyle}>{sup.email || '—'}</td>
                          <td style={tdStyle}>{sup.tin_number || '—'}</td>
                          <td style={tdStyle}>
                            {sup.supplied_category_names && sup.supplied_category_names.length > 0 ? (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {sup.supplied_category_names.map((cn, i) => (
                                  <span key={i} style={{
                                    padding: '2px 8px', borderRadius: '12px',
                                    backgroundColor: 'rgba(15,118,110,0.1)',
                                    color: '#0f766e', fontSize: '11px', fontWeight: '700',
                                    border: '1px solid rgba(15,118,110,0.25)'
                                  }}>{cn}</span>
                                ))}
                              </div>
                            ) : <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>}
                          </td>
                          <td style={{ ...tdStyle, maxWidth: '180px' }}>
                            {sup.supply_items ? (
                              <span style={{ fontSize: '12px', color: '#334155', lineHeight: '1.5' }}>{sup.supply_items}</span>
                            ) : <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>}
                          </td>
                          <td style={{ ...tdStyle, maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={sup.address}>{sup.address || '—'}</td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button onClick={() => setEditSupplier({ ...sup, supplied_categories: sup.supplied_categories || [] })} style={editBtnStyle}>Edit</button>
                              <button onClick={async () => {
                                if (window.confirm(`Are you sure you want to delete supplier "${sup.name}"?`)) {
                                  try {
                                    await axios.delete(`${API_BASE}suppliers/${sup.id}/`, { headers: getHeaders() });
                                    fetchData();
                                  } catch (err) {
                                    alert('Error deleting supplier. It may be linked to stock transactions.');
                                  }
                                }
                              }} style={deleteBtnStyle}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 'reports':
        // Compute report card summary stats
        const totalValuationVal = items.reduce((sum, item) => sum + (parseFloat(item.current_stock) * parseFloat(item.unit_cost)), 0);
        const lowStockCountVal = items.filter(item => parseFloat(item.current_stock) < parseFloat(item.min_reorder_level)).length;
        
        // Dispatches in last 30 days
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        const recentDispatches = ledger.filter(tx => {
          const txDate = new Date(tx.timestamp);
          return tx.transaction_type === 'issuance' && txDate >= thirtyDaysAgo;
        });
        const totalDispatchValue = recentDispatches.reduce((sum, tx) => sum + (parseFloat(tx.quantity) * parseFloat(tx.unit_cost)), 0);

        // Group recipes to compute average margin
        const recipeGroups = {};
        recipes.forEach(r => {
          if (!recipeGroups[r.menu_item]) {
            recipeGroups[r.menu_item] = {
              price: parseFloat(menuItems.find(mi => mi.id === r.menu_item)?.price || 0),
              cost: 0
            };
          }
          const itemCost = parseFloat(items.find(i => i.id === r.ingredient)?.unit_cost || 0);
          recipeGroups[r.menu_item].cost += parseFloat(r.quantity_required) * itemCost;
        });
        const recipeGroupList = Object.values(recipeGroups);
        const totalRecipeMargins = recipeGroupList.reduce((sum, rg) => {
          const marginPct = rg.price > 0 ? ((rg.price - rg.cost) / rg.price) * 100 : 0;
          return sum + marginPct;
        }, 0);
        const avgRecipeMargin = recipeGroupList.length > 0 ? (totalRecipeMargins / recipeGroupList.length) : 0;

        if (selectedReport === null) {
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '20px', fontWeight: '800' }}>📊 Inventory Reports Section</h2>
                <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: '13px' }}>This section provides reports to track inventory valuation, low stock, department consumption, and recipe profit margins.</p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '25px' }}>
                {/* Card 1: Valuation */}
                <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ backgroundColor: 'rgba(15, 118, 110, 0.1)', padding: '10px', borderRadius: '12px' }}>
                      <DollarSign size={24} color="#0f766e" />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Valuation</span>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 5px', color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>1. Stock Valuation Report</h3>
                    <p style={{ margin: 0, color: '#64748b', fontSize: '12px', lineHeight: '1.5' }}>Shows the current stock of all items in the warehouse grouped by their categories and calculates their total monetary value.</p>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
                    <span style={{ fontSize: '18px', fontWeight: '900', color: '#0f766e' }}>{totalValuationVal.toLocaleString()} ETB</span>
                    <button onClick={() => setSelectedReport('valuation')} style={{ ...btnPrimaryStyle, padding: '8px 14px', fontSize: '12px' }}>View Report</button>
                  </div>
                </div>

                {/* Card 2: Low Stock */}
                <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ backgroundColor: 'rgba(217, 119, 6, 0.1)', padding: '10px', borderRadius: '12px' }}>
                      <AlertTriangle size={24} color="#d97706" />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Low Stock</span>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 5px', color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>2. Low Stock & Reorder Report</h3>
                    <p style={{ margin: 0, color: '#64748b', fontSize: '12px', lineHeight: '1.5' }}>Lists items that urgently need to be reordered, complete with preferred supplier contact information and TIN numbers.</p>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
                    <span style={{ fontSize: '18px', fontWeight: '900', color: '#d97706' }}>{lowStockCountVal} items</span>
                    <button onClick={() => setSelectedReport('low_stock')} style={{ ...btnPrimaryStyle, padding: '8px 14px', fontSize: '12px', backgroundColor: '#d97706' }}>View Report</button>
                  </div>
                </div>

                {/* Card 3: Department Consumption */}
                <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.1)', padding: '10px', borderRadius: '12px' }}>
                      <ShoppingCart size={24} color="#0284c7" />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Department Consumption</span>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 5px', color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>3. Department Consumption Report</h3>
                    <p style={{ margin: 0, color: '#64748b', fontSize: '12px', lineHeight: '1.5' }}>Tracks the quantity and total value of items dispatched to the kitchen, bar, housekeeping, and other departments over the last 30 days.</p>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
                    <span style={{ fontSize: '18px', fontWeight: '900', color: '#0284c7' }}>{totalDispatchValue.toLocaleString()} ETB</span>
                    <button onClick={() => setSelectedReport('consumption')} style={{ ...btnPrimaryStyle, padding: '8px 14px', fontSize: '12px', backgroundColor: '#0284c7' }}>View Report</button>
                  </div>
                </div>

                {/* Card 4: Recipe Margins */}
                <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ backgroundColor: 'rgba(124, 58, 237, 0.1)', padding: '10px', borderRadius: '12px' }}>
                      <Package size={24} color="#7c3aed" />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Profit Margins</span>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 5px', color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>4. Recipe Profit Margins Report</h3>
                    <p style={{ margin: 0, color: '#64748b', fontSize: '12px', lineHeight: '1.5' }}>Shows the total production food cost, selling price, and profit margin percentage for registered recipes.</p>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
                    <span style={{ fontSize: '18px', fontWeight: '900', color: '#7c3aed' }}>{avgRecipeMargin.toFixed(1)}% Average</span>
                    <button onClick={() => setSelectedReport('recipe_margins')} style={{ ...btnPrimaryStyle, padding: '8px 14px', fontSize: '12px', backgroundColor: '#7c3aed' }}>View Report</button>
                  </div>
                </div>
              </div>
            </div>
          );
        }

        // Inside Report Detail View
        const renderReportView = () => {
          if (selectedReport === 'valuation') {
            // Valuation filtering logic
            const filtered = items.filter(item => {
              const matchesCategory = !reportValCategory || item.category?.toString() === reportValCategory;
              const matchesSearch = !reportValSearch || item.name.toLowerCase().includes(reportValSearch.toLowerCase()) || item.item_code.toLowerCase().includes(reportValSearch.toLowerCase());
              return matchesCategory && matchesSearch;
            });
            const totalVal = filtered.reduce((sum, item) => sum + (parseFloat(item.current_stock) * parseFloat(item.unit_cost)), 0);

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} className="no-print">
                  <button onClick={() => setSelectedReport(null)} style={btnBackStyle}>← Back to Reports</button>
                  <button onClick={printReport} style={btnPrintStyle}>Print Valuation Report</button>
                </div>

                <div className="print-header" style={printHeaderStyle}>
                  <h2 style={{ margin: '0 0 5px', color: '#0f172a', fontWeight: '900' }}>SMART HOTEL ERP - INVENTORY SYSTEM</h2>
                  <h3 style={{ margin: 0, color: '#0f766e', fontWeight: '800' }}>Stock Valuation Report</h3>
                  <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: '12px' }}>
                    Date Generated: {new Date().toLocaleString()} | Generated By: {userData?.username || 'system'}
                  </p>
                </div>

                {/* Filters */}
                <div style={filterBarStyle} className="no-print">
                  <div style={{ display: 'flex', gap: '15px', flex: 1 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '200px' }}>
                      <label style={filterLabelStyle}>Filter by Category</label>
                      <select style={filterInputStyle} value={reportValCategory} onChange={e => setReportValCategory(e.target.value)}>
                        <option value="">All Categories</option>
                        {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', flex: 1 }}>
                      <label style={filterLabelStyle}>Search Item Name/Code</label>
                      <input type="text" style={filterInputStyle} placeholder="Type item name or code..." value={reportValSearch} onChange={e => setReportValSearch(e.target.value)} />
                    </div>
                  </div>
                </div>

                {/* Summary Metrics */}
                <div style={{ display: 'flex', gap: '20px', backgroundColor: '#f8fafc', padding: '15px 25px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>TOTAL VALUATION</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#0f766e' }}>{totalVal.toLocaleString()} ETB</div>
                  </div>
                  <div style={{ borderLeft: '1px solid #cbd5e1', paddingLeft: '20px' }}>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>TOTAL ITEMS COUNT</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#334155' }}>{filtered.length} Items</div>
                  </div>
                </div>

                {/* Table */}
                <div style={cardStyle}>
                  <table style={reportTableStyle}>
                    <thead>
                      <tr style={theadStyle}>
                        <th style={thStyle}>Item Code</th>
                        <th style={thStyle}>Item Name</th>
                        <th style={thStyle}>Category</th>
                        <th style={thStyle}>Current Stock</th>
                        <th style={thStyle}>Unit Cost</th>
                        <th style={thStyle}>Total Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0 ? (
                        <tr><td colSpan="6" style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>No items match the filters.</td></tr>
                      ) : (
                        filtered.map(item => (
                          <tr key={item.id} style={trStyle}>
                            <td style={{ ...tdStyle, fontWeight: '700' }}>{item.item_code}</td>
                            <td style={tdStyle}>{item.name}</td>
                            <td style={tdStyle}><span style={badgeCategoryStyle}>{item.category_name}</span></td>
                            <td style={tdStyle}>{parseFloat(item.current_stock).toFixed(2)} {item.unit}</td>
                            <td style={tdStyle}>{parseFloat(item.unit_cost).toFixed(2)} ETB</td>
                            <td style={{ ...tdStyle, fontWeight: '700' }}>{(parseFloat(item.current_stock) * parseFloat(item.unit_cost)).toFixed(2)} ETB</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }

          if (selectedReport === 'low_stock') {
            const filtered = items.filter(item => {
              const isLow = parseFloat(item.current_stock) < parseFloat(item.min_reorder_level);
              if (!isLow) return false;
              const matchesCategory = !reportLowCategory || item.category?.toString() === reportLowCategory;
              const matchesSupplier = !reportLowSupplier || item.last_supplier?.toString() === reportLowSupplier;
              return matchesCategory && matchesSupplier;
            });

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} className="no-print">
                  <button onClick={() => setSelectedReport(null)} style={btnBackStyle}>← Back to Reports</button>
                  <button onClick={printReport} style={btnPrintStyle}>Print Reorder List</button>
                </div>

                <div className="print-header" style={printHeaderStyle}>
                  <h2 style={{ margin: '0 0 5px', color: '#0f172a', fontWeight: '900' }}>SMART HOTEL ERP - INVENTORY SYSTEM</h2>
                  <h3 style={{ margin: 0, color: '#d97706', fontWeight: '800' }}>Low Stock & Reorder Report</h3>
                  <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: '12px' }}>
                    Date Generated: {new Date().toLocaleString()} | Generated By: {userData?.username || 'system'}
                  </p>
                </div>

                {/* Filters */}
                <div style={filterBarStyle} className="no-print">
                  <div style={{ display: 'flex', gap: '15px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '200px' }}>
                      <label style={filterLabelStyle}>Category</label>
                      <select style={filterInputStyle} value={reportLowCategory} onChange={e => setReportLowCategory(e.target.value)}>
                        <option value="">All Categories</option>
                        {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '200px' }}>
                      <label style={filterLabelStyle}>Preferred Supplier</label>
                      <select style={filterInputStyle} value={reportLowSupplier} onChange={e => setReportLowSupplier(e.target.value)}>
                        <option value="">All Suppliers</option>
                        {suppliers.map(sup => <option key={sup.id} value={sup.id}>{sup.name}</option>)}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Summary */}
                <div style={{ display: 'flex', gap: '20px', backgroundColor: '#f8fafc', padding: '15px 25px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>ITEMS TO REORDER</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#d97706' }}>{filtered.length} Items</div>
                  </div>
                </div>

                {/* Table */}
                <div style={cardStyle}>
                  <table style={reportTableStyle}>
                    <thead>
                      <tr style={theadStyle}>
                        <th style={thStyle}>Item Code</th>
                        <th style={thStyle}>Item Name</th>
                        <th style={thStyle}>Current Stock</th>
                        <th style={thStyle}>Min level</th>
                        <th style={thStyle}>Deficit / Reorder Qty</th>
                        <th style={thStyle}>Preferred Supplier</th>
                        <th style={thStyle}>Supplier Contact / TIN</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0 ? (
                        <tr><td colSpan="7" style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>🎉 All items are fully stocked. No reorders needed!</td></tr>
                      ) : (
                        filtered.map(item => {
                          const deficit = parseFloat(item.min_reorder_level) * 2 - parseFloat(item.current_stock);
                          const matchedSupplierObj = suppliers.find(s => s.id === item.last_supplier);
                          return (
                            <tr key={item.id} style={trStyle}>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>{item.item_code}</td>
                              <td style={tdStyle}>{item.name}</td>
                              <td style={{ ...tdStyle, color: '#ef4444', fontWeight: '700' }}>{parseFloat(item.current_stock).toFixed(2)} {item.unit}</td>
                              <td style={tdStyle}>{parseFloat(item.min_reorder_level).toFixed(2)} {item.unit}</td>
                              <td style={{ ...tdStyle, fontWeight: '700', color: '#d97706' }}>{deficit > 0 ? deficit.toFixed(2) : 0} {item.unit}</td>
                              <td style={tdStyle}>{item.supplier_name || '—'}</td>
                              <td style={tdStyle}>
                                {matchedSupplierObj ? (
                                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                                    📞 {matchedSupplierObj.phone} {matchedSupplierObj.tin_number && ` | TIN: ${matchedSupplierObj.tin_number}`}
                                  </div>
                                ) : '—'}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }

          if (selectedReport === 'consumption') {
            // Dispatches filter
            const filtered = ledger.filter(tx => {
              if (tx.transaction_type !== 'issuance') return false;
              
              // Date filter
              const txDateStr = tx.timestamp.split('T')[0];
              const matchesStartDate = !reportConsumptionStart || txDateStr >= reportConsumptionStart;
              const matchesEndDate = !reportConsumptionEnd || txDateStr <= reportConsumptionEnd;
              
              // Department filter
              let matchesDept = true;
              if (reportConsumptionDept) {
                // notes contains e.g. "Dispatched to Kitchen"
                matchesDept = tx.notes?.toLowerCase().includes(`dispatched to ${reportConsumptionDept.toLowerCase()}`);
              }
              
              return matchesStartDate && matchesEndDate && matchesDept;
            });

            const totalCost = filtered.reduce((sum, tx) => sum + (parseFloat(tx.quantity) * parseFloat(tx.unit_cost)), 0);

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} className="no-print">
                  <button onClick={() => setSelectedReport(null)} style={btnBackStyle}>← Back to Reports</button>
                  <button onClick={printReport} style={btnPrintStyle}>Print Consumption Report</button>
                </div>

                <div className="print-header" style={printHeaderStyle}>
                  <h2 style={{ margin: '0 0 5px', color: '#0f172a', fontWeight: '900' }}>SMART HOTEL ERP - INVENTORY SYSTEM</h2>
                  <h3 style={{ margin: 0, color: '#0284c7', fontWeight: '800' }}>Department Consumption Report</h3>
                  <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: '12px' }}>
                    Period: {reportConsumptionStart || 'Beginning'} to {reportConsumptionEnd || 'Today'} | Generated By: {userData?.username || 'system'}
                  </p>
                </div>

                {/* Filters */}
                <div style={filterBarStyle} className="no-print">
                  <div style={{ display: 'flex', gap: '15px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '180px' }}>
                      <label style={filterLabelStyle}>Department / Station</label>
                      <select style={filterInputStyle} value={reportConsumptionDept} onChange={e => setReportConsumptionDept(e.target.value)}>
                        <option value="">All Departments</option>
                        <option value="Kitchen">Kitchen Pantry</option>
                        <option value="Bar">Bar Lounge</option>
                        <option value="Housekeeping">Housekeeping Supplies</option>
                        <option value="Maintenance">Maintenance Log</option>
                        <option value="Administration">General Office</option>
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '150px' }}>
                      <label style={filterLabelStyle}>Start Date</label>
                      <input type="date" style={filterInputStyle} value={reportConsumptionStart} onChange={e => setReportConsumptionStart(e.target.value)} />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '150px' }}>
                      <label style={filterLabelStyle}>End Date</label>
                      <input type="date" style={filterInputStyle} value={reportConsumptionEnd} onChange={e => setReportConsumptionEnd(e.target.value)} />
                    </div>
                  </div>
                </div>

                {/* Summary */}
                <div style={{ display: 'flex', gap: '20px', backgroundColor: '#f8fafc', padding: '15px 25px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>TOTAL CONSUMED VALUE</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#0284c7' }}>{totalCost.toLocaleString()} ETB</div>
                  </div>
                  <div style={{ borderLeft: '1px solid #cbd5e1', paddingLeft: '20px' }}>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>TRANSACTIONS COUNT</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#334155' }}>{filtered.length} Dispatches</div>
                  </div>
                </div>

                {/* Table */}
                <div style={cardStyle}>
                  <table style={reportTableStyle}>
                    <thead>
                      <tr style={theadStyle}>
                        <th style={thStyle}>Date & Time</th>
                        <th style={thStyle}>Item Name</th>
                        <th style={thStyle}>Quantity</th>
                        <th style={thStyle}>Unit Cost</th>
                        <th style={thStyle}>Total Cost</th>
                        <th style={thStyle}>Logged By</th>
                        <th style={thStyle}>Dispatch Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0 ? (
                        <tr><td colSpan="7" style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>No consumption logs found in this period.</td></tr>
                      ) : (
                        filtered.map(tx => (
                          <tr key={tx.id} style={trStyle}>
                            <td style={{ ...tdStyle, fontSize: '11px', color: '#64748b' }}>{new Date(tx.timestamp).toLocaleString()}</td>
                            <td style={{ ...tdStyle, fontWeight: '700' }}>{tx.item_name}</td>
                            <td style={tdStyle}>{parseFloat(tx.quantity).toFixed(2)} {tx.item_unit}</td>
                            <td style={tdStyle}>{parseFloat(tx.unit_cost).toFixed(2)} ETB</td>
                            <td style={{ ...tdStyle, fontWeight: '700' }}>{(parseFloat(tx.quantity) * parseFloat(tx.unit_cost)).toFixed(2)} ETB</td>
                            <td style={tdStyle}>{tx.logged_by_username || 'system'}</td>
                            <td style={{ ...tdStyle, fontSize: '11px' }}>{tx.notes}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }

          if (selectedReport === 'recipe_margins') {
            // Group flat recipes array by menu item
            const grouped = {};
            recipes.forEach(r => {
              if (!grouped[r.menu_item]) {
                const menuItem = menuItems.find(mi => mi.id === r.menu_item);
                grouped[r.menu_item] = {
                  id: r.menu_item,
                  name: r.menu_item_name,
                  category: menuItem?.category || '',
                  category_name: menuItem?.category_name || '—',
                  price: parseFloat(menuItem?.price || 0),
                  cost: 0,
                  ingredientsCount: 0
                };
              }
              const itemCost = parseFloat(items.find(i => i.id === r.ingredient)?.unit_cost || 0);
              grouped[r.menu_item].cost += parseFloat(r.quantity_required) * itemCost;
              grouped[r.menu_item].ingredientsCount += 1;
            });

            // Convert to list & filter
            const list = Object.values(grouped).filter(item => {
              const marginAmount = item.price - item.cost;
              const marginPct = item.price > 0 ? (marginAmount / item.price) * 100 : 0;
              
              // Category filter
              const matchesCategory = !reportRecipeCategory || item.category?.toString() === reportRecipeCategory;
              
              // Margin filter
              let matchesMargin = true;
              if (reportRecipeMarginFilter === 'low') {
                matchesMargin = marginPct < 40;
              } else if (reportRecipeMarginFilter === 'good') {
                matchesMargin = marginPct >= 40;
              }

              return matchesCategory && matchesMargin;
            });

            const avgMargin = list.reduce((sum, item) => {
              const marginPct = item.price > 0 ? ((item.price - item.cost) / item.price) * 100 : 0;
              return sum + marginPct;
            }, 0) / (list.length || 1);

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} className="no-print">
                  <button onClick={() => setSelectedReport(null)} style={btnBackStyle}>← Back to Reports</button>
                  <button onClick={printReport} style={btnPrintStyle}>Print Recipe Margin Analysis</button>
                </div>

                <div className="print-header" style={printHeaderStyle}>
                  <h2 style={{ margin: '0 0 5px', color: '#0f172a', fontWeight: '900' }}>SMART HOTEL ERP - F&B COSTING</h2>
                  <h3 style={{ margin: 0, color: '#7c3aed', fontWeight: '800' }}>Menu Recipe Costing & Profit Margin Report</h3>
                  <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: '12px' }}>
                    Date Generated: {new Date().toLocaleString()} | Generated By: {userData?.username || 'system'}
                  </p>
                </div>

                {/* Filters */}
                <div style={filterBarStyle} className="no-print">
                  <div style={{ display: 'flex', gap: '15px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '200px' }}>
                      <label style={filterLabelStyle}>Menu Category</label>
                      <select style={filterInputStyle} value={reportRecipeCategory} onChange={e => setReportRecipeCategory(e.target.value)}>
                        <option value="">All Categories</option>
                        {Array.from(new Set(menuItems.map(m => m.category).filter(Boolean))).map(catId => {
                          const name = menuItems.find(m => m.category === catId)?.category_name || `Category ${catId}`;
                          return <option key={catId} value={catId}>{name}</option>;
                        })}
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '200px' }}>
                      <label style={filterLabelStyle}>Profit Margin Rating</label>
                      <select style={filterInputStyle} value={reportRecipeMarginFilter} onChange={e => setReportRecipeMarginFilter(e.target.value)}>
                        <option value="all">All Recipes</option>
                        <option value="low">Low Margin (&lt; 40%)</option>
                        <option value="good">Healthy Margin (≥ 40%)</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Summary */}
                <div style={{ display: 'flex', gap: '20px', backgroundColor: '#f8fafc', padding: '15px 25px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>AVERAGE MARGIN PERCENTAGE</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#7c3aed' }}>{avgMargin.toFixed(1)} %</div>
                  </div>
                  <div style={{ borderLeft: '1px solid #cbd5e1', paddingLeft: '20px' }}>
                    <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>RECIPES ANALYZED</div>
                    <div style={{ fontSize: '20px', fontWeight: '900', color: '#334155' }}>{list.length} Items</div>
                  </div>
                </div>

                {/* Table */}
                <div style={cardStyle}>
                  <table style={reportTableStyle}>
                    <thead>
                      <tr style={theadStyle}>
                        <th style={thStyle}>Menu Item</th>
                        <th style={thStyle}>Menu Category</th>
                        <th style={thStyle}>Ingredients Count</th>
                        <th style={thStyle}>Selling Price</th>
                        <th style={thStyle}>BOM Raw Cost</th>
                        <th style={thStyle}>Profit Margin (ETB)</th>
                        <th style={thStyle}>Margin (%)</th>
                        <th style={thStyle}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.length === 0 ? (
                        <tr><td colSpan="8" style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>No recipes match the filters.</td></tr>
                      ) : (
                        list.map(item => {
                          const margin = item.price - item.cost;
                          const marginPct = item.price > 0 ? (margin / item.price) * 100 : 0;
                          const isLow = marginPct < 40;

                          return (
                            <tr key={item.id} style={trStyle}>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>{item.name}</td>
                              <td style={tdStyle}>{item.category_name}</td>
                              <td style={tdStyle}>{item.ingredientsCount} items</td>
                              <td style={tdStyle}>{item.price.toFixed(2)} ETB</td>
                              <td style={tdStyle}>{item.cost.toFixed(2)} ETB</td>
                              <td style={{ ...tdStyle, fontWeight: '700', color: margin >= 0 ? '#0f766e' : '#ef4444' }}>{margin.toFixed(2)} ETB</td>
                              <td style={{ ...tdStyle, fontWeight: '700', color: isLow ? '#f59e0b' : '#10b981' }}>{marginPct.toFixed(1)}%</td>
                              <td style={tdStyle}>
                                <span style={{
                                  padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700',
                                  backgroundColor: isLow ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                                  color: isLow ? '#f59e0b' : '#10b981',
                                  border: `1px solid ${isLow ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
                                }}>{isLow ? 'Low Margin' : 'Healthy'}</span>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }
          return null;
        };

        return renderReportView();

      default:
        return null;
    }
  };

  return (
    <div style={containerStyle} className="inventory-container">
      {/* Dynamic Font Styling */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        
        .inventory-container {
          font-family: 'Plus Jakarta Sans', sans-serif !important;
        }
        
        .tab-btn-active {
          border-bottom: 3px solid #0f766e !important;
          color: #0f766e !important;
          font-weight: 800 !important;
        }

        @media print {
          @page {
            size: A4;
            margin: 15mm 15mm 15mm 15mm !important;
          }
          body, html {
            background-color: #ffffff !important;
            background: #ffffff !important;
            color: #000000 !important;
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            height: auto !important;
          }
          .no-print, header, nav, aside, button, .tab-bar, footer {
            display: none !important;
          }
          .print-header {
            display: block !important;
          }
          /* Reset parent dashboard layout and sidebar alignment */
          .app-layout,
          .main-content-wrapper,
          .sidebar-container,
          main,
          #root,
          .App {
            margin: 0 !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            display: block !important;
            float: none !important;
            position: static !important;
            box-shadow: none !important;
            border: none !important;
            background: transparent !important;
            background-color: transparent !important;
          }
          table {
            border: 1px solid #cbd5e1 !important;
            border-collapse: collapse !important;
            width: 100% !important;
            margin-top: 15px !important;
          }
          th, td {
            border: 1px solid #cbd5e1 !important;
            padding: 8px 12px !important;
            font-size: 11px !important;
            color: #000000 !important;
          }
          th {
            background-color: #f1f5f9 !important;
            font-weight: 700 !important;
          }
        }
        @media screen {
          .print-header {
            display: none !important;
          }
        }
      `}</style>

      <header style={headerStyle} className="no-print inventory-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={logoIconBg}>
            <Package size={22} color="#ffffff" />
          </div>
          <div>
            <h1 style={titleStyle}>INVENTORY CONTROL CENTER</h1>
            <p style={subtitleStyle}>
              Logged: {userData?.username || 'Staff'} — {userData?.role?.toUpperCase()}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={fetchData} style={btnSecondaryStyle}>
            <RefreshCw size={14} style={{ marginRight: '6px' }} /> Refresh Stock
          </button>
          {handleLogout && (
            <button onClick={handleLogout} style={logoutBtn} title="Logout">
              <LogOut size={16} color="#ef4444" style={{ marginRight: '6px' }} /> <span className="inventory-logout-label">Logout</span>
            </button>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div style={tabBar} className="no-print inventory-tab-bar">
        <button onClick={() => { setActiveTab('overview'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'overview' ? 'tab-btn-active' : ''}>Overview</button>
        <button onClick={() => { setActiveTab('actions'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'actions' ? 'tab-btn-active' : ''}>Stock Actions</button>
        <button onClick={() => { setActiveTab('recipes'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'recipes' ? 'tab-btn-active' : ''}>Recipes BOM</button>
        <button onClick={() => { setActiveTab('ledger'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'ledger' ? 'tab-btn-active' : ''}>Stock Ledger</button>
        <button onClick={() => { setActiveTab('items'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'items' ? 'tab-btn-active' : ''}>Ingredients & Stock List</button>
        <button onClick={() => { setActiveTab('categories'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'categories' ? 'tab-btn-active' : ''}>Category List</button>
        <button onClick={() => { setActiveTab('suppliers'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'suppliers' ? 'tab-btn-active' : ''}>Supplier List</button>
        <button onClick={() => { setActiveTab('reports'); setSelectedReport(null); }} style={tabBtn} className={activeTab === 'reports' ? 'tab-btn-active' : ''}>Reports</button>
      </div>

      <main style={mainBody} className="inventory-main">
        {renderContent()}
      </main>

      {/* MODALS */}

      {/* Item Modal */}
      <AnimatePresence>
        {isItemModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={modalContentStyle}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>Add New Ingredient / Stock Item</h3>
              <form onSubmit={handleCreateItem} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Item Code (Unique)</label>
                  <input required type="text" style={inputStyle} value={newItem.item_code} placeholder="e.g. INGR-092" onChange={e => setNewItem({ ...newItem, item_code: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Item Name</label>
                  <input required type="text" style={inputStyle} value={newItem.name} placeholder="e.g. Fresh Tomatoes" onChange={e => setNewItem({ ...newItem, name: e.target.value })} />
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Category</label>
                    <select required style={inputStyle} value={newItem.category} onChange={e => setNewItem({ ...newItem, category: e.target.value })}>
                      <option value="">-- Select Category --</option>
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name} ({cat.category_type === 'f_and_b' ? 'F&B' : 'Room'})</option>
                      ))}
                    </select>
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Unit of Measure</label>
                    <select required style={inputStyle} value={newItem.unit} onChange={e => setNewItem({ ...newItem, unit: e.target.value })}>
                      <option value="kg">Kilogram (kg)</option>
                      <option value="g">Gram (g)</option>
                      <option value="l">Liter (L)</option>
                      <option value="ml">Milliliter (ml)</option>
                      <option value="pcs">Pieces (pcs)</option>
                      <option value="pack">Packs (pack)</option>
                      <option value="bottle">Bottles (bottle)</option>
                    </select>
                  </div>
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Min Reorder Warning Level</label>
                    <input required type="number" step="0.01" style={inputStyle} value={newItem.min_reorder_level} onChange={e => setNewItem({ ...newItem, min_reorder_level: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Purchase Unit Cost (ETB)</label>
                    <input required type="number" step="0.01" style={inputStyle} value={newItem.unit_cost} onChange={e => setNewItem({ ...newItem, unit_cost: e.target.value })} />
                  </div>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Guest Selling Price (ETB) <span style={{ color: '#94a3b8', fontWeight: 400 }}>— for minibar / room charges</span></label>
                  <input type="number" step="0.01" style={inputStyle} value={newItem.selling_price} placeholder="0.00" onChange={e => setNewItem({ ...newItem, selling_price: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Preferred Supplier</label>
                  <select style={inputStyle} value={newItem.last_supplier} onChange={e => setNewItem({ ...newItem, last_supplier: e.target.value })}>
                    <option value="">-- Select Supplier --</option>
                    {suppliers.map(sup => (
                      <option key={sup.id} value={sup.id}>{sup.name}</option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsItemModalOpen(false)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Item</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Supplier Modal */}
      <AnimatePresence>
        {isSupplierModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={modalContentStyle}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>Add New Supplier</h3>
              <form onSubmit={handleCreateSupplier} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Supplier / Company Name</label>
                  <input required type="text" style={inputStyle} value={newSupplier.name} placeholder="e.g. Horizon Farms Plc" onChange={e => setNewSupplier({ ...newSupplier, name: e.target.value })} />
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Contact Person</label>
                    <input type="text" style={inputStyle} value={newSupplier.contact_person} placeholder="John Doe" onChange={e => setNewSupplier({ ...newSupplier, contact_person: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Phone Number</label>
                    <input required type="text" style={inputStyle} value={newSupplier.phone} placeholder="0911..." onChange={e => setNewSupplier({ ...newSupplier, phone: e.target.value })} />
                  </div>
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Email</label>
                    <input type="email" style={inputStyle} value={newSupplier.email} placeholder="supplier@mail.com" onChange={e => setNewSupplier({ ...newSupplier, email: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>TIN Number</label>
                    <input type="text" style={inputStyle} value={newSupplier.tin_number} placeholder="TIN..." onChange={e => setNewSupplier({ ...newSupplier, tin_number: e.target.value })} />
                  </div>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Supplied Ingredient Categories</label>
                  <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#64748b' }}>ይህ አቅራቢ የሚያቀርበውን የግብአት አይነቶች ምረጥ:</p>
                  {categories.length === 0 ? (
                    <p style={{ fontSize: '13px', color: '#f59e0b', fontWeight: '600' }}>⚠️ No categories yet. Go to "Category List" tab to add some first.</p>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      {categories.map(cat => {
                        const isChecked = newSupplier.supplied_categories.includes(cat.id);
                        return (
                          <label key={cat.id} style={{
                            display: 'flex', alignItems: 'center', gap: '7px',
                            padding: '6px 12px',
                            borderRadius: '20px',
                            border: `1.5px solid ${isChecked ? '#0f766e' : '#cbd5e1'}`,
                            backgroundColor: isChecked ? 'rgba(15,118,110,0.08)' : '#ffffff',
                            cursor: 'pointer',
                            fontSize: '13px',
                            fontWeight: isChecked ? '700' : '500',
                            color: isChecked ? '#0f766e' : '#475569',
                            transition: 'all 0.15s ease',
                            userSelect: 'none'
                          }}>
                            <input
                              type="checkbox"
                              style={{ accentColor: '#0f766e', width: '14px', height: '14px' }}
                              checked={isChecked}
                              onChange={e => {
                                const updated = e.target.checked
                                  ? [...newSupplier.supplied_categories, cat.id]
                                  : newSupplier.supplied_categories.filter(id => id !== cat.id);
                                setNewSupplier({ ...newSupplier, supplied_categories: updated });
                              }}
                            />
                            {cat.name}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Specific Items Supplied</label>
                  <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#64748b' }}>ይህ አቅራቢ የሚያቀርባቸውን ልዩ ምርቶች ዘርዝር (ለምሳሌ: ቲማቲም፣ ነጭ ሽንኩርት፣ ዘይት)</p>
                  <textarea
                    style={{ ...inputStyle, resize: 'vertical', minHeight: '70px' }}
                    rows="3"
                    placeholder="e.g. Fresh Tomatoes, Onions, Sunflower Oil, Garlic..."
                    value={newSupplier.supply_items}
                    onChange={e => setNewSupplier({ ...newSupplier, supply_items: e.target.value })}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Company Address</label>
                  <textarea style={inputStyle} rows="2" value={newSupplier.address} placeholder="Office location..." onChange={e => setNewSupplier({ ...newSupplier, address: e.target.value })} />
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsSupplierModalOpen(false)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Supplier</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Recipe BOM Modal */}
      <AnimatePresence>
        {isRecipeModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ ...modalContentStyle, width: '650px', maxWidth: '95%' }}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>Define Recipe / Bill of Materials</h3>
              <form onSubmit={handleSaveRecipeBOM} style={formStyle}>
                
                {/* Menu Item Selection */}
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Select F&B Menu Item</label>
                  <select required style={inputStyle} value={selectedRecipeMenu} onChange={e => setSelectedRecipeMenu(e.target.value)}>
                    <option value="">-- Choose Menu Item --</option>
                    {menuItems.map(mi => (
                      <option key={mi.id} value={mi.id}>{mi.name} ({parseFloat(mi.price).toFixed(2)} ETB)</option>
                    ))}
                  </select>
                </div>

                {/* Recipe Rows */}
                {selectedRecipeMenu && (
                  <div style={{ marginTop: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <h4 style={{ margin: 0, color: '#334155', fontWeight: '700', fontSize: '14px' }}>Ingredients List</h4>
                      <button type="button" onClick={addRecipeRow} style={{
                        padding: '4px 10px',
                        backgroundColor: '#0f766e',
                        border: 'none',
                        color: '#ffffff',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '700',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        <Plus size={14} /> Add Ingredient
                      </button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '250px', overflowY: 'auto', paddingRight: '5px' }}>
                      {recipeRows.map((row, index) => {
                        const selectedIng = items.find(i => i.id === parseInt(row.ingredient));
                        const unit = selectedIng ? selectedIng.unit : '';
                        const cost = selectedIng ? parseFloat(selectedIng.unit_cost) : 0;
                        const rowCost = row.quantity_required ? parseFloat(row.quantity_required) * cost : 0;

                        return (
                          <div key={index} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                            <div style={{ flex: 2 }}>
                              <select required style={inputStyle} value={row.ingredient} onChange={e => handleRowChange(index, 'ingredient', e.target.value)}>
                                <option value="">-- Select Ingredient --</option>
                                {items.map(item => (
                                  <option key={item.id} value={item.id}>{item.name} ({item.item_code})</option>
                                ))}
                              </select>
                            </div>
                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '5px' }}>
                              <input required type="number" step="0.001" style={{ ...inputStyle, width: '100%' }} value={row.quantity_required} placeholder="Qty" onChange={e => handleRowChange(index, 'quantity_required', e.target.value)} />
                              <span style={{ fontSize: '12px', color: '#64748b', minWidth: '35px' }}>{unit}</span>
                            </div>
                            <div style={{ minWidth: '80px', textAlign: 'right', fontSize: '13px', fontWeight: '700', color: '#0f766e' }}>
                              {rowCost.toFixed(2)} ETB
                            </div>
                            <button type="button" onClick={() => removeRecipeRow(index)} style={{
                              padding: '6px',
                              backgroundColor: 'rgba(239, 68, 68, 0.1)',
                              border: 'none',
                              color: '#ef4444',
                              borderRadius: '4px',
                              cursor: 'pointer'
                            }}>
                              <Trash2 size={14} />
                            </button>
                          </div>
                        );
                      })}
                    </div>

                    {/* Cost Summary Box */}
                    {(() => {
                      const selectedMenu = menuItems.find(mi => mi.id === parseInt(selectedRecipeMenu));
                      const sellingPrice = selectedMenu ? parseFloat(selectedMenu.price) : 0;
                      const totalCost = recipeRows.reduce((sum, row) => {
                        const ing = items.find(i => i.id === parseInt(row.ingredient));
                        const cost = ing ? parseFloat(ing.unit_cost) : 0;
                        const qty = row.quantity_required ? parseFloat(row.quantity_required) : 0;
                        return sum + (qty * cost);
                      }, 0);
                      const margin = sellingPrice - totalCost;
                      const marginPct = sellingPrice > 0 ? (margin / sellingPrice) * 100 : 0;

                      return (
                        <div style={{
                          marginTop: '20px',
                          padding: '12px',
                          backgroundColor: '#f8fafc',
                          borderRadius: '8px',
                          border: '1px solid #e2e8f0',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>Selling Price: <strong>{sellingPrice.toFixed(2)} ETB</strong></div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>BOM Raw Cost: <strong>{totalCost.toFixed(2)} ETB</strong></div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '13px', fontWeight: '800', color: margin >= 0 ? '#0f766e' : '#ef4444' }}>
                              Margin: {margin.toFixed(2)} ETB
                            </div>
                            <div style={{ fontSize: '11px', fontWeight: '700', color: marginPct > 40 ? '#10b981' : '#f59e0b' }}>
                              Percentage: {marginPct.toFixed(1)}%
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Footer Buttons */}
                <div style={{ display: 'flex', gap: '10px', marginTop: '20px', justifyContent: 'flex-end' }}>
                  <button type="button" onClick={() => setIsRecipeModalOpen(false)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" disabled={!selectedRecipeMenu || recipeRows.length === 0} style={{
                    ...btnPrimaryStyle,
                    opacity: (!selectedRecipeMenu || recipeRows.length === 0) ? 0.6 : 1,
                    cursor: (!selectedRecipeMenu || recipeRows.length === 0) ? 'not-allowed' : 'pointer'
                  }}>
                    Save Recipe
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Category Modal */}
      <AnimatePresence>
        {isCategoryModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={modalContentStyle}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>Add New Inventory Category</h3>
              <form onSubmit={handleCreateCategory} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Category Name</label>
                  <input required type="text" style={inputStyle} value={newCategory.name} placeholder="e.g. Food, Beverages, Housekeeping" onChange={e => setNewCategory({ ...newCategory, name: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Category Type</label>
                  <select style={inputStyle} value={newCategory.category_type} onChange={e => setNewCategory({ ...newCategory, category_type: e.target.value })}>
                    <option value="f_and_b">Food & Beverage (F&B)</option>
                    <option value="housekeeping">Housekeeping & Rooms</option>
                  </select>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Description (Optional)</label>
                  <textarea style={inputStyle} rows="3" value={newCategory.description} placeholder="Describe what items belong to this category..." onChange={e => setNewCategory({ ...newCategory, description: e.target.value })} />
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsCategoryModalOpen(false)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Category</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── EDIT ITEM MODAL ─────────────────────────────────────── */}
      <AnimatePresence>
        {editItem && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={modalContentStyle}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>✏️ Edit Ingredient / Stock Item</h3>
              <form onSubmit={handleEditItem} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Item Code</label>
                  <input required type="text" style={inputStyle} value={editItem.item_code} onChange={e => setEditItem({ ...editItem, item_code: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Item Name</label>
                  <input required type="text" style={inputStyle} value={editItem.name} onChange={e => setEditItem({ ...editItem, name: e.target.value })} />
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Category</label>
                    <select required style={inputStyle} value={editItem.category} onChange={e => setEditItem({ ...editItem, category: e.target.value })}>
                      <option value="">-- Select --</option>
                      {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name} ({cat.category_type === 'f_and_b' ? 'F&B' : 'Room'})</option>)}
                    </select>
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Unit</label>
                    <select required style={inputStyle} value={editItem.unit} onChange={e => setEditItem({ ...editItem, unit: e.target.value })}>
                      <option value="kg">Kilogram (kg)</option>
                      <option value="g">Gram (g)</option>
                      <option value="l">Liter (L)</option>
                      <option value="ml">Milliliter (ml)</option>
                      <option value="pcs">Pieces (pcs)</option>
                      <option value="pack">Packs (pack)</option>
                      <option value="bottle">Bottles (bottle)</option>
                    </select>
                  </div>
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Min Reorder Level</label>
                    <input required type="number" step="0.01" style={inputStyle} value={editItem.min_reorder_level} onChange={e => setEditItem({ ...editItem, min_reorder_level: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Purchase Unit Cost (ETB)</label>
                    <input required type="number" step="0.01" style={inputStyle} value={editItem.unit_cost} onChange={e => setEditItem({ ...editItem, unit_cost: e.target.value })} />
                  </div>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Guest Selling Price (ETB) <span style={{ color: '#94a3b8', fontWeight: 400 }}>— for minibar / room charges</span></label>
                  <input type="number" step="0.01" style={inputStyle} value={editItem.selling_price ?? ''} placeholder="0.00" onChange={e => setEditItem({ ...editItem, selling_price: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Preferred Supplier</label>
                  <select style={inputStyle} value={editItem.last_supplier} onChange={e => setEditItem({ ...editItem, last_supplier: e.target.value })}>
                    <option value="">-- Select Supplier --</option>
                    {suppliers.map(sup => <option key={sup.id} value={sup.id}>{sup.name}</option>)}
                  </select>
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setEditItem(null)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Changes</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── EDIT CATEGORY MODAL ──────────────────────────────────── */}
      <AnimatePresence>
        {editCategory && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={modalContentStyle}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>✏️ Edit Category</h3>
              <form onSubmit={handleEditCategory} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Category Name</label>
                  <input required type="text" style={inputStyle} value={editCategory.name} onChange={e => setEditCategory({ ...editCategory, name: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Description (Optional)</label>
                  <textarea style={inputStyle} rows="3" value={editCategory.description || ''} onChange={e => setEditCategory({ ...editCategory, description: e.target.value })} />
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setEditCategory(null)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Changes</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── EDIT SUPPLIER MODAL ──────────────────────────────────── */}
      <AnimatePresence>
        {editSupplier && (
          <div style={modalOverlayStyle}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ ...modalContentStyle, width: '560px', maxWidth: '95%', maxHeight: '90vh', overflowY: 'auto' }}>
              <h3 style={{ margin: '0 0 20px', color: '#0f172a', fontWeight: '800' }}>✏️ Edit Supplier</h3>
              <form onSubmit={handleEditSupplier} style={formStyle}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Company Name</label>
                  <input required type="text" style={inputStyle} value={editSupplier.name} onChange={e => setEditSupplier({ ...editSupplier, name: e.target.value })} />
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Contact Person</label>
                    <input type="text" style={inputStyle} value={editSupplier.contact_person || ''} onChange={e => setEditSupplier({ ...editSupplier, contact_person: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Phone Number</label>
                    <input required type="text" style={inputStyle} value={editSupplier.phone} onChange={e => setEditSupplier({ ...editSupplier, phone: e.target.value })} />
                  </div>
                </div>
                <div style={formRowStyle}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Email</label>
                    <input type="email" style={inputStyle} value={editSupplier.email || ''} onChange={e => setEditSupplier({ ...editSupplier, email: e.target.value })} />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>TIN Number</label>
                    <input type="text" style={inputStyle} value={editSupplier.tin_number || ''} onChange={e => setEditSupplier({ ...editSupplier, tin_number: e.target.value })} />
                  </div>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Supplied Ingredient Categories</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    {categories.map(cat => {
                      const isChecked = (editSupplier.supplied_categories || []).includes(cat.id);
                      return (
                        <label key={cat.id} style={{ display: 'flex', alignItems: 'center', gap: '7px', padding: '6px 12px', borderRadius: '20px', border: `1.5px solid ${isChecked ? '#0f766e' : '#cbd5e1'}`, backgroundColor: isChecked ? 'rgba(15,118,110,0.08)' : '#ffffff', cursor: 'pointer', fontSize: '13px', fontWeight: isChecked ? '700' : '500', color: isChecked ? '#0f766e' : '#475569' }}>
                          <input type="checkbox" style={{ accentColor: '#0f766e' }} checked={isChecked} onChange={e => {
                            const updated = e.target.checked
                              ? [...(editSupplier.supplied_categories || []), cat.id]
                              : (editSupplier.supplied_categories || []).filter(id => id !== cat.id);
                            setEditSupplier({ ...editSupplier, supplied_categories: updated });
                          }} />
                          {cat.name}
                        </label>
                      );
                    })}
                  </div>
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Specific Items Supplied</label>
                  <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: '70px' }} rows="3" value={editSupplier.supply_items || ''} onChange={e => setEditSupplier({ ...editSupplier, supply_items: e.target.value })} />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Company Address</label>
                  <textarea style={inputStyle} rows="2" value={editSupplier.address || ''} onChange={e => setEditSupplier({ ...editSupplier, address: e.target.value })} />
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setEditSupplier(null)} style={btnSecondaryStyle}>Cancel</button>
                  <button type="submit" style={btnPrimaryStyle}>Save Changes</button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};

// -- Stat Card Component --
const StatCard = ({ icon, title, value, color }) => (
  <motion.div whileHover={{ y: -4 }} style={statCardStyle}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div>
        <p style={{ margin: 0, fontSize: '11px', color: '#64748b', fontWeight: '800', letterSpacing: '0.5px', textTransform: 'uppercase' }}>{title}</p>
        <h2 style={{ margin: '8px 0 0', fontSize: '22px', fontWeight: '900', color: '#0f172a' }}>{value}</h2>
      </div>
      <div style={{ ...cardIconBg, backgroundColor: `${color}15` }}>
        {icon}
      </div>
    </div>
  </motion.div>
);

// -- Styling definitions --
const containerStyle = { minHeight: '100vh', backgroundColor: '#f8fafc', paddingBottom: '60px', fontFamily: "'Plus Jakarta Sans', sans-serif" };
const headerStyle = {
  background: 'linear-gradient(135deg, #072f2d 0%, #0c4a45 100%)',
  padding: '25px 40px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  boxShadow: '0 4px 20px rgba(0,0,0,0.06)'
};
const logoIconBg = { backgroundColor: '#0f766e', padding: '10px', borderRadius: '12px', display: 'flex', alignItems: 'center' };
const titleStyle = { color: '#ffffff', margin: 0, fontSize: '18px', fontWeight: '900', letterSpacing: '0.5px' };
const subtitleStyle = { color: '#99f6e4', margin: '4px 0 0', fontSize: '12px', fontWeight: '600' };

const btnPrimaryStyle = { backgroundColor: '#0f766e', color: '#ffffff', border: 'none', borderRadius: '10px', padding: '10px 18px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', transition: 'all 0.2s' };
const btnSecondaryStyle = { backgroundColor: 'rgba(255,255,255,0.08)', color: '#ffffff', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '10px', padding: '10px 18px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', transition: 'all 0.2s' };
const logoutBtn = { backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.15)', color: '#ef4444', borderRadius: '10px', padding: '10px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center' };

const tabBar = { display: 'flex', gap: '20px', padding: '0 40px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.02)' };
const tabBtn = { padding: '18px 10px', background: 'transparent', border: 'none', cursor: 'pointer', fontWeight: '600', fontSize: '13px', color: '#64748b', transition: 'all 0.2s' };

const mainBody = { padding: '30px 40px' };
const loadingStyle = { textAlign: 'center', paddingTop: '100px' };

const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' };
const statCardStyle = { backgroundColor: '#ffffff', padding: '22px', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.12)', boxShadow: '0 4px 16px rgba(15,23,42,0.03)' };
const cardIconBg = { padding: '10px', borderRadius: '12px', display: 'flex', alignItems: 'center' };

const cardStyle = { backgroundColor: '#ffffff', padding: '25px', borderRadius: '20px', border: '1px solid rgba(148,163,184,0.12)', boxShadow: '0 6px 20px rgba(15,23,42,0.03)', overflow: 'hidden' };
const cardHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' };
const cardTitleStyle = { margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' };

const tableStyle = { width: '100%', borderCollapse: 'collapse' };
const theadStyle = { backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' };
const thStyle = { padding: '12px 18px', textAlign: 'left', fontSize: '11px', fontWeight: '800', color: '#475569', letterSpacing: '0.5px', textTransform: 'uppercase' };
const trStyle = { borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' };
const tdStyle = { padding: '14px 18px', fontSize: '13px', color: '#334155' };

const badgeStyle = { padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: '800' };
const badgeWarningStyle = { backgroundColor: 'rgba(217,119,6,0.1)', color: '#d97706', border: '1px solid #d97706', padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: '800' };
const badgeCategoryStyle = { backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #ccfbf1', padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: '800' };

const deptProgressStyle = { display: 'flex', flexDirection: 'column', gap: '6px' };
const progressBarContainer = { height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' };
const progressBar = { height: '100%', borderRadius: '3px' };

// Modal styles
const modalOverlayStyle = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(15,23,42,0.6)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 };
const modalContentStyle = { backgroundColor: '#ffffff', padding: '30px', borderRadius: '24px', width: '480px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)', border: '1px solid rgba(148,163,184,0.15)' };

// Form styles
const formStyle = { display: 'flex', flexDirection: 'column', gap: '15px' };
const formHeaderStyle = { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' };
const formGroupStyle = { display: 'flex', flexDirection: 'column', gap: '6px' };
const formRowStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' };
const labelStyle = { fontSize: '11px', fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.5px' };
const inputStyle = { padding: '12px 14px', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '13px', outline: 'none', transition: 'border 0.2s', fontFamily: "'Plus Jakarta Sans', sans-serif" };

const editBtnStyle = { padding: '5px 12px', backgroundColor: 'rgba(15,118,110,0.1)', border: '1px solid rgba(15,118,110,0.25)', color: '#0f766e', borderRadius: '6px', fontSize: '12px', fontWeight: '700', cursor: 'pointer' };
const deleteBtnStyle = { padding: '5px 12px', backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', borderRadius: '6px', fontSize: '12px', fontWeight: '700', cursor: 'pointer' };

// Report Specific Styles
const btnBackStyle = { padding: '8px 16px', backgroundColor: 'transparent', border: '1px solid #cbd5e1', borderRadius: '10px', color: '#475569', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center' };
const btnPrintStyle = { padding: '8px 16px', backgroundColor: '#0f766e', border: 'none', borderRadius: '10px', color: '#ffffff', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center' };
const printHeaderStyle = { textAlign: 'center', borderBottom: '2px solid #0f766e', paddingBottom: '15px', marginBottom: '20px' };
const filterBarStyle = { backgroundColor: '#ffffff', padding: '20px', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.12)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '15px' };
const filterLabelStyle = { fontSize: '10px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' };
const filterInputStyle = { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '12px', outline: 'none', width: '100%', fontFamily: "'Plus Jakarta Sans', sans-serif" };
const reportTableStyle = { width: '100%', borderCollapse: 'collapse' };

export default InventoryDashboard;
