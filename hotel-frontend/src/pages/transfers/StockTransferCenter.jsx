import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Truck, ArrowRight, CheckCircle, AlertTriangle, Plus,
  Search, Filter, Clock, X, Package, Layers, ShieldCheck,
  RefreshCw, Check, ArrowRightLeft, Building2, User, Eye,
  AlertCircle, ShieldAlert
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_BASE = `${API_BASE_URL}/users/`;

const StockTransferCenter = ({ userData }) => {
  // Navigation tabs: 'transfers', 'new_request', 'locations', 'dashboard'
  const [activeTab, setActiveTab] = useState('transfers');

  // Core Data States
  const [transfers, setTransfers] = useState([]);
  const [locations, setLocations] = useState([]);
  const [items, setItems] = useState([]);
  const [staffUsers, setStaffUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Transfers Filter States
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterSource, setFilterSource] = useState('');
  const [filterDest, setFilterDest] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Location Dashboard States
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [locationInventory, setLocationInventory] = useState(null);
  const [locInventoryLoading, setLocInventoryLoading] = useState(false);

  // New Transfer Request Form State
  const [newRequisition, setNewRequisition] = useState({
    source_location: '',
    destination_location: '',
    notes: '',
    items: [{ item_id: '', quantity_requested: '', notes: '' }]
  });
  const [submittingRequisition, setSubmittingRequisition] = useState(false);

  // Dispatch Modal State
  const [dispatchTarget, setDispatchTarget] = useState(null);
  const [dispatchItems, setDispatchItems] = useState([]);
  const [dispatchNotes, setDispatchNotes] = useState('');
  const [submittingDispatch, setSubmittingDispatch] = useState(false);

  // Receiving Modal State
  const [receiveTarget, setReceiveTarget] = useState(null);
  const [receiveItems, setReceiveItems] = useState([]);
  const [receiveNotes, setReceiveNotes] = useState('');
  const [submittingReceive, setSubmittingReceive] = useState(false);

  // Cancel / Reject Modal State
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [submittingCancel, setSubmittingCancel] = useState(false);

  // Location Management Modal States
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);
  const [locationForm, setLocationForm] = useState({
    id: null,
    code: '',
    name: '',
    location_type: 'warehouse',
    custodian: '',
    is_active: true
  });
  const [submittingLocation, setSubmittingLocation] = useState(false);

  const getHeaders = () => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // Fetch initial data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const headers = getHeaders();
      const [transfersRes, locationsRes, itemsRes, usersRes] = await Promise.all([
        axios.get(`${API_BASE}transfers/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}locations/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}inventory-items/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}users/`, { headers }).catch(() => ({ data: [] }))
      ]);

      const trfList = Array.isArray(transfersRes.data)
        ? transfersRes.data
        : (transfersRes.data?.results || []);
      setTransfers(trfList);

      const locList = Array.isArray(locationsRes.data)
        ? locationsRes.data
        : (locationsRes.data?.results || []);
      setLocations(locList);
      if (locList.length > 0 && !selectedLocationId) {
        setSelectedLocationId(locList[0].id);
      }

      const itList = Array.isArray(itemsRes.data)
        ? itemsRes.data
        : (itemsRes.data?.results || []);
      setItems(itList);

      const usrList = Array.isArray(usersRes.data)
        ? usersRes.data
        : (usersRes.data?.results || []);
      setStaffUsers(usrList);
    } catch (err) {
      console.error('Failed to load stock transfer data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedLocationId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch location inventory when selected
  const fetchLocationInventory = useCallback(async (locId) => {
    if (!locId) return;
    setLocInventoryLoading(true);
    try {
      const headers = getHeaders();
      const res = await axios.get(`${API_BASE}locations/${locId}/inventory/`, { headers });
      setLocationInventory(res.data);
    } catch (err) {
      console.error('Failed to fetch location inventory:', err);
      setLocationInventory(null);
    } finally {
      setLocInventoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'dashboard' && selectedLocationId) {
      fetchLocationInventory(selectedLocationId);
    }
  }, [activeTab, selectedLocationId, fetchLocationInventory]);

  // ── Requisition Line Items Management ──
  const handleAddLineItem = () => {
    setNewRequisition(prev => ({
      ...prev,
      items: [...prev.items, { item_id: '', quantity_requested: '', notes: '' }]
    }));
  };

  const handleRemoveLineItem = (index) => {
    if (newRequisition.items.length <= 1) return;
    setNewRequisition(prev => ({
      ...prev,
      items: prev.items.filter((_, idx) => idx !== index)
    }));
  };

  const handleLineItemChange = (index, field, value) => {
    setNewRequisition(prev => {
      const updated = [...prev.items];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, items: updated };
    });
  };

  const handleSubmitRequisition = async (e) => {
    e.preventDefault();
    if (!newRequisition.source_location || !newRequisition.destination_location) {
      alert('Please specify both source and destination locations.');
      return;
    }
    if (newRequisition.source_location === newRequisition.destination_location) {
      alert('Source and destination locations cannot be identical.');
      return;
    }
    const validItems = newRequisition.items.filter(it => it.item_id && parseFloat(it.quantity_requested) > 0);
    if (validItems.length === 0) {
      alert('Please add at least one line item with a positive quantity.');
      return;
    }

    setSubmittingRequisition(true);
    try {
      const payload = {
        source_location: newRequisition.source_location,
        destination_location: newRequisition.destination_location,
        notes: newRequisition.notes,
        items: validItems.map(it => ({
          item_id: it.item_id,
          quantity_requested: parseFloat(it.quantity_requested),
          notes: it.notes
        }))
      };
      await axios.post(`${API_BASE}transfers/`, payload, { headers: getHeaders() });
      alert('Stock Transfer Requisition submitted successfully!');
      setNewRequisition({
        source_location: '',
        destination_location: '',
        notes: '',
        items: [{ item_id: '', quantity_requested: '', notes: '' }]
      });
      setActiveTab('transfers');
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to submit stock transfer requisition.'));
    } finally {
      setSubmittingRequisition(false);
    }
  };

  // ── Dispatch Handler ──
  const openDispatchModal = (transfer) => {
    setDispatchTarget(transfer);
    setDispatchNotes('');
    setDispatchItems(
      transfer.items.map(it => ({
        id: it.id,
        item_id: it.item,
        item_name: it.item_name,
        unit: it.item_unit,
        quantity_requested: it.quantity_requested,
        quantity_dispatched: it.quantity_requested,
        batch_id: ''
      }))
    );
  };

  const handleSubmitDispatch = async (e) => {
    e.preventDefault();
    if (!dispatchTarget) return;

    setSubmittingDispatch(true);
    try {
      const payload = {
        notes: dispatchNotes,
        items: dispatchItems.map(it => ({
          id: it.id,
          item_id: it.item_id,
          quantity_dispatched: parseFloat(it.quantity_dispatched),
          batch_id: it.batch_id || undefined
        }))
      };
      await axios.post(`${API_BASE}transfers/${dispatchTarget.id}/dispatch/`, payload, {
        headers: getHeaders()
      });
      alert(`Transfer #${dispatchTarget.transfer_number} dispatched into in-transit custody!`);
      setDispatchTarget(null);
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to dispatch stock transfer.'));
    } finally {
      setSubmittingDispatch(false);
    }
  };

  // ── Receiving Handler ──
  const openReceiveModal = (transfer) => {
    setReceiveTarget(transfer);
    setReceiveNotes('');
    setReceiveItems(
      transfer.items.map(it => ({
        id: it.id,
        item_id: it.item,
        item_name: it.item_name,
        unit: it.item_unit,
        quantity_dispatched: it.quantity_dispatched,
        quantity_received: it.quantity_dispatched,
        quantity_damaged: '0.00'
      }))
    );
  };

  const handleSubmitReceive = async (e) => {
    e.preventDefault();
    if (!receiveTarget) return;

    // Validate quantities
    for (const it of receiveItems) {
      const recv = parseFloat(it.quantity_received || 0);
      const dam = parseFloat(it.quantity_damaged || 0);
      const disp = parseFloat(it.quantity_dispatched || 0);
      if (recv < 0 || dam < 0) {
        alert(`Quantities for '${it.item_name}' cannot be negative.`);
        return;
      }
      if (Math.abs((recv + dam) - disp) > 0.001) {
        alert(`Reconciliation error for '${it.item_name}': Received (${recv}) + Damaged (${dam}) must equal Dispatched (${disp}).`);
        return;
      }
    }

    setSubmittingReceive(true);
    try {
      const payload = {
        notes: receiveNotes,
        items: receiveItems.map(it => ({
          id: it.id,
          item_id: it.item_id,
          quantity_received: parseFloat(it.quantity_received),
          quantity_damaged: parseFloat(it.quantity_damaged || 0)
        }))
      };
      await axios.post(`${API_BASE}transfers/${receiveTarget.id}/receive/`, payload, {
        headers: getHeaders()
      });
      alert(`Transfer #${receiveTarget.transfer_number} confirmed and inventory updated!`);
      setReceiveTarget(null);
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to confirm receipt of transfer.'));
    } finally {
      setSubmittingReceive(false);
    }
  };

  // ── Cancel / Return Handler ──
  const handleCancelTransfer = async (e) => {
    e.preventDefault();
    if (!cancelTarget) return;
    setSubmittingCancel(true);
    try {
      await axios.post(`${API_BASE}transfers/${cancelTarget.id}/cancel/`, {
        reason: cancelReason || 'Cancelled by staff'
      }, { headers: getHeaders() });
      alert(`Transfer #${cancelTarget.transfer_number} has been cancelled/rejected.`);
      setCancelTarget(null);
      setCancelReason('');
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to cancel transfer.'));
    } finally {
      setSubmittingCancel(false);
    }
  };

  // ── Location CRUD ──
  const openCreateLocationModal = () => {
    setLocationForm({
      id: null,
      code: '',
      name: '',
      location_type: 'warehouse',
      custodian: '',
      is_active: true
    });
    setIsLocationModalOpen(true);
  };

  const openEditLocationModal = (loc) => {
    setLocationForm({
      id: loc.id,
      code: loc.code,
      name: loc.name,
      location_type: loc.location_type,
      custodian: loc.custodian || '',
      is_active: loc.is_active
    });
    setIsLocationModalOpen(true);
  };

  const handleSaveLocation = async (e) => {
    e.preventDefault();
    setSubmittingLocation(true);
    try {
      const headers = getHeaders();
      const payload = {
        code: locationForm.code.trim().toUpperCase(),
        name: locationForm.name.trim(),
        location_type: locationForm.location_type,
        custodian: locationForm.custodian || null,
        is_active: locationForm.is_active
      };
      if (locationForm.id) {
        await axios.put(`${API_BASE}locations/${locationForm.id}/`, payload, { headers });
        alert('Stock Location updated successfully!');
      } else {
        await axios.post(`${API_BASE}locations/`, payload, { headers });
        alert('Stock Location created successfully!');
      }
      setIsLocationModalOpen(false);
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to save stock location.'));
    } finally {
      setSubmittingLocation(false);
    }
  };

  const handleDeactivateLocation = async (loc) => {
    if (!window.confirm(`Are you sure you want to deactivate location '${loc.name}'? Existing stock balances will be preserved safely.`)) return;
    try {
      const headers = getHeaders();
      await axios.delete(`${API_BASE}locations/${loc.id}/`, { headers });
      alert(`Location '${loc.name}' updated.`);
      fetchData();
    } catch (err) {
      alert(apiErrorMessage(err, 'Failed to deactivate location.'));
    }
  };

  // Filtered transfers
  const filteredTransfers = transfers.filter(trf => {
    if (filterStatus !== 'all' && trf.status !== filterStatus) return false;
    if (filterSource && String(trf.source_location) !== String(filterSource)) return false;
    if (filterDest && String(trf.destination_location) !== String(filterDest)) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const numMatch = (trf.transfer_number || '').toLowerCase().includes(q);
      const notesMatch = (trf.notes || '').toLowerCase().includes(q);
      const itemMatch = (trf.items || []).some(it => (it.item_name || '').toLowerCase().includes(q));
      if (!numMatch && !notesMatch && !itemMatch) return false;
    }
    return true;
  });

  // Styles
  const cardStyle = {
    backgroundColor: '#ffffff',
    borderRadius: '16px',
    border: '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
    overflow: 'hidden'
  };
  const tableStyle = { width: '100%', borderCollapse: 'collapse', textAlign: 'left' };
  const theadStyle = { backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' };
  const thStyle = { padding: '12px 16px', fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' };
  const tdStyle = { padding: '14px 16px', fontSize: '13px', borderBottom: '1px solid #f1f5f9' };
  const trStyle = { transition: 'background-color 0.15s ease' };
  const inputStyle = {
    padding: '8px 12px',
    borderRadius: '8px',
    border: '1px solid #cbd5e1',
    fontSize: '13px',
    outline: 'none',
    backgroundColor: '#ffffff'
  };
  const btnPrimary = {
    backgroundColor: '#0f766e',
    color: '#ffffff',
    padding: '8px 16px',
    borderRadius: '8px',
    border: 'none',
    fontWeight: '700',
    fontSize: '13px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  };
  const btnSecondary = {
    backgroundColor: '#f1f5f9',
    color: '#334155',
    padding: '8px 14px',
    borderRadius: '8px',
    border: '1px solid #cbd5e1',
    fontWeight: '600',
    fontSize: '13px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  };
  const modalOverlayStyle = {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    padding: '20px'
  };
  const modalContentStyle = {
    backgroundColor: '#ffffff',
    borderRadius: '20px',
    width: '100%',
    maxWidth: '680px',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    display: 'flex',
    flexDirection: 'column'
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'requested':
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fde68a' }}>Requested</span>;
      case 'in_transit':
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#e0e7ff', color: '#4338ca', border: '1px solid #c7d2fe' }}>In Transit</span>;
      case 'completed':
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0' }}>Completed</span>;
      case 'partially_received':
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#ffedd5', color: '#c2410c', border: '1px solid #fed7aa' }}>Partial (Breakage)</span>;
      case 'rejected':
      case 'cancelled':
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#fee2e2', color: '#b91c1c', border: '1px solid #fecaca' }}>{status.toUpperCase()}</span>;
      default:
        return <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#f1f5f9', color: '#475569' }}>{status}</span>;
    }
  };

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ backgroundColor: 'rgba(15,118,110,0.1)', color: '#0f766e', padding: '10px', borderRadius: '12px' }}>
              <ArrowRightLeft size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '22px', fontWeight: '800', color: '#0f172a' }}>
                Stock Transfer & Location Center
              </h1>
              <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
                Two-phase custody transfers, storekeeper dispatches, door receipts, and multi-location balances.
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => { setActiveTab('new_request'); }} style={btnPrimary}>
            <Plus size={16} /> New Stock Requisition
          </button>
          <button onClick={fetchData} style={btnSecondary} disabled={loading}>
            <RefreshCw size={15} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Refresh
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
        {[
          { id: 'transfers', label: 'Stock Transfers', icon: <Truck size={16} /> },
          { id: 'new_request', label: 'New Requisition', icon: <Plus size={16} /> },
          { id: 'dashboard', label: 'Location Dashboard', icon: <Layers size={16} /> },
          { id: 'locations', label: 'Store Locations', icon: <Building2 size={16} /> }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '9px 18px',
              borderRadius: '10px',
              border: 'none',
              backgroundColor: activeTab === t.id ? '#0f766e' : '#f8fafc',
              color: activeTab === t.id ? '#ffffff' : '#64748b',
              fontWeight: '700',
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.15s ease'
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── TAB 1: TRANSFERS LIST & WORKFLOW ── */}
      {activeTab === 'transfers' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Filter Bar */}
          <div style={{ ...cardStyle, padding: '16px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
            <div style={{ flex: '1 1 220px', minWidth: '180px' }}>
              <input
                type="text"
                placeholder="Search transfer #, item, notes..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ ...inputStyle, width: '100%' }}
              />
            </div>

            <div style={{ flex: '0 1 160px' }}>
              <select
                value={filterStatus}
                onChange={e => setFilterStatus(e.target.value)}
                style={{ ...inputStyle, width: '100%' }}
              >
                <option value="all">All Statuses</option>
                <option value="requested">Requested</option>
                <option value="in_transit">In Transit</option>
                <option value="completed">Completed</option>
                <option value="partially_received">Partial (Breakage)</option>
                <option value="rejected">Rejected / Cancelled</option>
              </select>
            </div>

            <div style={{ flex: '0 1 160px' }}>
              <select
                value={filterSource}
                onChange={e => setFilterSource(e.target.value)}
                style={{ ...inputStyle, width: '100%' }}
              >
                <option value="">All Source Locations</option>
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.name}</option>
                ))}
              </select>
            </div>

            <div style={{ flex: '0 1 160px' }}>
              <select
                value={filterDest}
                onChange={e => setFilterDest(e.target.value)}
                style={{ ...inputStyle, width: '100%' }}
              >
                <option value="">All Dest Locations</option>
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.name}</option>
                ))}
              </select>
            </div>

            <button
              onClick={() => { setSearchQuery(''); setFilterStatus('all'); setFilterSource(''); setFilterDest(''); }}
              style={btnSecondary}
            >
              Reset
            </button>
          </div>

          {/* Transfers Table */}
          <div style={cardStyle}>
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadStyle}>
                    <th style={thStyle}>Transfer #</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Route</th>
                    <th style={thStyle}>Items Summary</th>
                    <th style={thStyle}>Requested By</th>
                    <th style={thStyle}>Dispatched By</th>
                    <th style={thStyle}>Received By</th>
                    <th style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransfers.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                        No stock transfers matching the selected filters.
                      </td>
                    </tr>
                  ) : (
                    filteredTransfers.map(trf => {
                      const isRequested = trf.status === 'requested';
                      const isInTransit = trf.status === 'in_transit';

                      return (
                        <tr key={trf.id} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700', fontFamily: 'monospace', color: '#0f766e' }}>
                            {trf.transfer_number}
                          </td>
                          <td style={tdStyle}>{getStatusBadge(trf.status)}</td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '600' }}>
                              <span style={{ color: '#0f172a' }}>{trf.source_location_name}</span>
                              <ArrowRight size={13} color="#94a3b8" />
                              <span style={{ color: '#0f766e' }}>{trf.destination_location_name}</span>
                            </div>
                          </td>
                          <td style={{ ...tdStyle, fontSize: '12px' }}>
                            {(trf.items || []).map((it, idx) => (
                              <div key={idx} style={{ color: '#334155' }}>
                                • <strong>{it.item_name}</strong>: Req {parseFloat(it.quantity_requested).toFixed(2)}
                                {it.quantity_dispatched > 0 && ` | Disp ${parseFloat(it.quantity_dispatched).toFixed(2)}`}
                                {it.quantity_received > 0 && ` | Recv ${parseFloat(it.quantity_received).toFixed(2)}`}
                                {it.quantity_damaged > 0 && <span style={{ color: '#dc2626' }}> (Damaged: {parseFloat(it.quantity_damaged).toFixed(2)})</span>}
                              </div>
                            ))}
                          </td>
                          <td style={{ ...tdStyle, fontSize: '12px', color: '#64748b' }}>
                            {trf.requested_by_username || '—'}
                          </td>
                          <td style={{ ...tdStyle, fontSize: '12px', color: '#64748b' }}>
                            {trf.dispatched_by_username || '—'}
                          </td>
                          <td style={{ ...tdStyle, fontSize: '12px', color: '#64748b' }}>
                            {trf.received_by_username || '—'}
                          </td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              {isRequested && (
                                <>
                                  <button
                                    onClick={() => openDispatchModal(trf)}
                                    style={{ ...btnPrimary, padding: '5px 10px', fontSize: '12px' }}
                                    title="Dispatch into transit custody"
                                  >
                                    <Truck size={13} /> Dispatch
                                  </button>
                                  <button
                                    onClick={() => setCancelTarget(trf)}
                                    style={{ ...btnSecondary, padding: '5px 8px', fontSize: '12px', color: '#b91c1c' }}
                                    title="Cancel transfer request"
                                  >
                                    Cancel
                                  </button>
                                </>
                              )}

                              {isInTransit && (
                                <>
                                  <button
                                    onClick={() => openReceiveModal(trf)}
                                    style={{ ...btnPrimary, backgroundColor: '#2563eb', padding: '5px 10px', fontSize: '12px' }}
                                    title="Confirm receipt at receiving bay"
                                  >
                                    <CheckCircle size={13} /> Receive
                                  </button>
                                  <button
                                    onClick={() => setCancelTarget(trf)}
                                    style={{ ...btnSecondary, padding: '5px 8px', fontSize: '12px', color: '#b91c1c' }}
                                    title="Reject and return delivery to source store"
                                  >
                                    Reject / Return
                                  </button>
                                </>
                              )}

                              {!isRequested && !isInTransit && (
                                <span style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic' }}>Archived</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: NEW REQUISITION FORM ── */}
      {activeTab === 'new_request' && (
        <div style={{ ...cardStyle, padding: '24px', maxWidth: '850px', margin: '0 auto', width: '100%' }}>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
            New Stock Transfer Requisition
          </h2>
          <p style={{ margin: '0 0 20px 0', fontSize: '13px', color: '#64748b' }}>
            Request stock transfer from a central warehouse to a kitchen, bar, or departmental pantry.
          </p>

          <form onSubmit={handleSubmitRequisition} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Source Store (Dispatching From) *
                </label>
                <select
                  required
                  value={newRequisition.source_location}
                  onChange={e => setNewRequisition({ ...newRequisition, source_location: e.target.value })}
                  style={{ ...inputStyle, width: '100%' }}
                >
                  <option value="">Select Source Location...</option>
                  {locations.filter(l => l.is_active).map(loc => (
                    <option key={loc.id} value={loc.id}>{loc.name} ({loc.code})</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Destination Pantry (Receiving Door) *
                </label>
                <select
                  required
                  value={newRequisition.destination_location}
                  onChange={e => setNewRequisition({ ...newRequisition, destination_location: e.target.value })}
                  style={{ ...inputStyle, width: '100%' }}
                >
                  <option value="">Select Destination Location...</option>
                  {locations.filter(l => l.is_active && String(l.id) !== String(newRequisition.source_location)).map(loc => (
                    <option key={loc.id} value={loc.id}>{loc.name} ({loc.code})</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                Requisition Notes / Justification
              </label>
              <textarea
                rows={2}
                value={newRequisition.notes}
                onChange={e => setNewRequisition({ ...newRequisition, notes: e.target.value })}
                placeholder="e.g. Replenishment for banquet service / dinner rush..."
                style={{ ...inputStyle, width: '100%', resize: 'vertical' }}
              />
            </div>

            {/* Line Items */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f172a' }}>
                  Requested Line Items
                </h3>
                <button
                  type="button"
                  onClick={handleAddLineItem}
                  style={{ ...btnSecondary, padding: '4px 10px', fontSize: '12px' }}
                >
                  <Plus size={13} /> Add Item
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {newRequisition.items.map((row, idx) => (
                  <div key={idx} style={{ display: 'grid', gridTemplateColumns: '3fr 1.5fr 3fr auto', gap: '10px', alignItems: 'center' }}>
                    <select
                      required
                      value={row.item_id}
                      onChange={e => handleLineItemChange(idx, 'item_id', e.target.value)}
                      style={{ ...inputStyle, width: '100%' }}
                    >
                      <option value="">Select Ingredient / Material...</option>
                      {items.map(it => (
                        <option key={it.id} value={it.id}>
                          {it.name} ({it.unit}) - On Hand: {it.current_stock}
                        </option>
                      ))}
                    </select>

                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      placeholder="Quantity"
                      value={row.quantity_requested}
                      onChange={e => handleLineItemChange(idx, 'quantity_requested', e.target.value)}
                      style={{ ...inputStyle, width: '100%' }}
                    />

                    <input
                      type="text"
                      placeholder="Item notes (optional)"
                      value={row.notes}
                      onChange={e => handleLineItemChange(idx, 'notes', e.target.value)}
                      style={{ ...inputStyle, width: '100%' }}
                    />

                    <button
                      type="button"
                      onClick={() => handleRemoveLineItem(idx)}
                      disabled={newRequisition.items.length <= 1}
                      style={{ ...btnSecondary, padding: '8px', color: '#b91c1c', opacity: newRequisition.items.length <= 1 ? 0.3 : 1 }}
                      title="Remove row"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
              <button
                type="button"
                onClick={() => setActiveTab('transfers')}
                style={btnSecondary}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingRequisition}
                style={btnPrimary}
              >
                {submittingRequisition ? 'Submitting...' : 'Submit Requisition'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── TAB 3: LOCATION DASHBOARD ── */}
      {activeTab === 'dashboard' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ ...cardStyle, padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#475569' }}>Select Location:</span>
              <select
                value={selectedLocationId}
                onChange={e => {
                  setSelectedLocationId(e.target.value);
                  fetchLocationInventory(e.target.value);
                }}
                style={{ ...inputStyle, minWidth: '220px', fontWeight: '700' }}
              >
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.code}) {!loc.is_active ? '— INACTIVE' : ''}
                  </option>
                ))}
              </select>
            </div>

            {locationInventory && (
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', color: '#64748b' }}>
                  Total Items: <strong>{locationInventory.total_items}</strong>
                </span>
                <span style={{ fontSize: '13px', color: '#0f766e', fontWeight: '800' }}>
                  Total Valuation: {parseFloat(locationInventory.total_valuation || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} ETB
                </span>
                <button onClick={() => fetchLocationInventory(selectedLocationId)} style={btnSecondary} disabled={locInventoryLoading}>
                  <RefreshCw size={14} style={{ animation: locInventoryLoading ? 'spin 1s linear infinite' : 'none' }} />
                </button>
              </div>
            )}
          </div>

          {/* Location Inventory Table */}
          <div style={cardStyle}>
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadStyle}>
                    <th style={thStyle}>Code</th>
                    <th style={thStyle}>Item Name</th>
                    <th style={thStyle}>Category</th>
                    <th style={thStyle}>On Hand</th>
                    <th style={thStyle}>Unit Cost</th>
                    <th style={thStyle}>Valuation</th>
                    <th style={thStyle}>Active Batches</th>
                  </tr>
                </thead>
                <tbody>
                  {locInventoryLoading ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                        Loading location inventory balances...
                      </td>
                    </tr>
                  ) : !locationInventory || locationInventory.items.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                        No inventory stock currently allocated to this location.
                      </td>
                    </tr>
                  ) : (
                    locationInventory.items.map((it, idx) => (
                      <tr key={idx} style={trStyle}>
                        <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#64748b' }}>{it.item_code}</td>
                        <td style={{ ...tdStyle, fontWeight: '700', color: '#0f172a' }}>{it.item_name}</td>
                        <td style={{ ...tdStyle, color: '#475569' }}>{it.category_name}</td>
                        <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                          {parseFloat(it.quantity).toFixed(2)} {it.unit}
                        </td>
                        <td style={tdStyle}>{parseFloat(it.unit_cost).toFixed(2)} ETB</td>
                        <td style={{ ...tdStyle, fontWeight: '700' }}>
                          {parseFloat(it.valuation).toLocaleString(undefined, { minimumFractionDigits: 2 })} ETB
                        </td>
                        <td style={{ ...tdStyle, fontSize: '12px' }}>
                          {(it.batches || []).map((bt, bIdx) => (
                            <span
                              key={bIdx}
                              style={{
                                display: 'inline-block',
                                backgroundColor: '#f1f5f9',
                                padding: '2px 8px',
                                borderRadius: '6px',
                                margin: '2px 4px 2px 0',
                                border: '1px solid #e2e8f0'
                              }}
                            >
                              <strong>{bt.batch_number}</strong>: {parseFloat(bt.quantity).toFixed(2)} {it.unit}
                              {bt.expiry_date && <span style={{ color: '#64748b' }}> (Exp: {bt.expiry_date})</span>}
                            </span>
                          ))}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 4: STORE LOCATIONS MANAGEMENT ── */}
      {activeTab === 'locations' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
                Store & Department Locations
              </h2>
              <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
                Configure central warehouses, kitchen pantries, bars, and housekeeping store rooms.
              </p>
            </div>
            <button onClick={openCreateLocationModal} style={btnPrimary}>
              <Plus size={16} /> Add Location
            </button>
          </div>

          <div style={cardStyle}>
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadStyle}>
                    <th style={thStyle}>Code</th>
                    <th style={thStyle}>Name</th>
                    <th style={thStyle}>Type</th>
                    <th style={thStyle}>Custodian</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {locations.map(loc => (
                    <tr key={loc.id} style={trStyle}>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', fontWeight: '700', color: '#0f766e' }}>
                        {loc.code}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: '700', color: '#0f172a' }}>{loc.name}</td>
                      <td style={{ ...tdStyle, textTransform: 'capitalize', color: '#475569' }}>
                        {loc.location_type}
                      </td>
                      <td style={{ ...tdStyle, color: '#64748b' }}>
                        {loc.custodian_username ? `@${loc.custodian_username}` : '—'}
                      </td>
                      <td style={tdStyle}>
                        {loc.is_active ? (
                          <span style={{ padding: '3px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '700', backgroundColor: '#dcfce7', color: '#15803d' }}>Active</span>
                        ) : (
                          <span style={{ padding: '3px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '700', backgroundColor: '#fee2e2', color: '#b91c1c' }}>Inactive</span>
                        )}
                      </td>
                      <td style={tdStyle}>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => openEditLocationModal(loc)}
                            style={{ ...btnSecondary, padding: '4px 8px', fontSize: '12px' }}
                          >
                            Edit
                          </button>
                          {loc.is_active && (
                            <button
                              onClick={() => handleDeactivateLocation(loc)}
                              style={{ ...btnSecondary, padding: '4px 8px', fontSize: '12px', color: '#b91c1c' }}
                            >
                              Deactivate
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 1: DISPATCH TRANSFER ── */}
      {dispatchTarget && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
                  Dispatch Transfer #{dispatchTarget.transfer_number}
                </h3>
                <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                  From: <strong>{dispatchTarget.source_location_name}</strong> → To: <strong>{dispatchTarget.destination_location_name}</strong>
                </p>
              </div>
              <button onClick={() => setDispatchTarget(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X size={20} color="#64748b" />
              </button>
            </div>

            <form onSubmit={handleSubmitDispatch} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ backgroundColor: '#f0fdfa', borderRadius: '10px', padding: '12px', border: '1px solid #ccfbf1', fontSize: '12px', color: '#0f766e' }}>
                <strong>Storekeeper Notice:</strong> Dispatching locks goods into in-transit custody. Batches are authoritatively allocated via FEFO/FIFO from the source warehouse.
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '8px' }}>
                  Line Items to Dispatch
                </label>
                {dispatchItems.map((it, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: '8px', marginBottom: '8px', border: '1px solid #e2e8f0' }}>
                    <div>
                      <div style={{ fontWeight: '700', fontSize: '13px', color: '#0f172a' }}>{it.item_name}</div>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>
                        Requested: {it.quantity_requested} {it.unit}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: '600' }}>Dispatch Qty:</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={it.quantity_dispatched}
                        onChange={e => {
                          const val = e.target.value;
                          setDispatchItems(prev => {
                            const up = [...prev];
                            up[idx].quantity_dispatched = val;
                            return up;
                          });
                        }}
                        style={{ ...inputStyle, width: '100px', fontWeight: '700' }}
                      />
                      <span style={{ fontSize: '12px', color: '#64748b' }}>{it.unit}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Dispatch Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Dispatched via trolley #2 / Storekeeper sign-off"
                  value={dispatchNotes}
                  onChange={e => setDispatchNotes(e.target.value)}
                  style={{ ...inputStyle, width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setDispatchTarget(null)} style={btnSecondary}>
                  Cancel
                </button>
                <button type="submit" disabled={submittingDispatch} style={btnPrimary}>
                  {submittingDispatch ? 'Dispatching...' : 'Confirm Dispatch (Lock to Transit)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL 2: RECEIVE TRANSFER & DAMAGE RECONCILIATION ── */}
      {receiveTarget && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
                  Confirm Physical Receipt #{receiveTarget.transfer_number}
                </h3>
                <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                  Destination: <strong>{receiveTarget.destination_location_name}</strong> (Dispatched by @{receiveTarget.dispatched_by_username})
                </p>
              </div>
              <button onClick={() => setReceiveTarget(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X size={20} color="#64748b" />
              </button>
            </div>

            <form onSubmit={handleSubmitReceive} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ backgroundColor: '#eff6ff', borderRadius: '10px', padding: '12px', border: '1px solid #dbeafe', fontSize: '12px', color: '#1e40af' }}>
                <strong>Destination Custodian Verification:</strong> Inspect goods upon arrival. Received intact quantities increment destination balances. Transit breakage is auto-posted to Spoilage & Waste (Dr 5010 / Cr 1300).
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '8px' }}>
                  Arrival Reconciliation by Line Item
                </label>
                {receiveItems.map((it, idx) => (
                  <div key={idx} style={{ padding: '12px 14px', backgroundColor: '#f8fafc', borderRadius: '8px', marginBottom: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: '700', fontSize: '13px', color: '#0f172a' }}>{it.item_name}</span>
                      <span style={{ fontSize: '12px', color: '#475569' }}>
                        Dispatched: <strong>{it.quantity_dispatched} {it.unit}</strong>
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#15803d', marginBottom: '4px' }}>
                          Intact Received Qty *
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          required
                          value={it.quantity_received}
                          onChange={e => {
                            const val = e.target.value;
                            setReceiveItems(prev => {
                              const up = [...prev];
                              up[idx].quantity_received = val;
                              return up;
                            });
                          }}
                          style={{ ...inputStyle, width: '100%', borderColor: '#86efac' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#b91c1c', marginBottom: '4px' }}>
                          Damaged / Broken Qty
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={it.quantity_damaged}
                          onChange={e => {
                            const val = e.target.value;
                            setReceiveItems(prev => {
                              const up = [...prev];
                              up[idx].quantity_damaged = val;
                              return up;
                            });
                          }}
                          style={{ ...inputStyle, width: '100%', borderColor: '#fca5a5' }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Receiving Bay Notes / Inspection Sign-off
                </label>
                <input
                  type="text"
                  placeholder="e.g. Inspected at kitchen door. 2 bottles broken in trolley transit."
                  value={receiveNotes}
                  onChange={e => setReceiveNotes(e.target.value)}
                  style={{ ...inputStyle, width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setReceiveTarget(null)} style={btnSecondary}>
                  Cancel
                </button>
                <button type="submit" disabled={submittingReceive} style={{ ...btnPrimary, backgroundColor: '#2563eb' }}>
                  {submittingReceive ? 'Confirming...' : 'Confirm Receipt & Update Balances'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL 3: CANCEL / RETURN TRANSFER ── */}
      {cancelTarget && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalContentStyle, maxWidth: '480px' }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: '800', color: '#b91c1c' }}>
                Cancel Transfer #{cancelTarget.transfer_number}
              </h3>
              <button onClick={() => setCancelTarget(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X size={18} color="#64748b" />
              </button>
            </div>

            <form onSubmit={handleCancelTransfer} style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <p style={{ margin: 0, fontSize: '13px', color: '#475569' }}>
                {cancelTarget.status === 'in_transit'
                  ? 'Rejecting this transfer will return all dispatched goods back to the source location balances with an authoritative return audit transaction.'
                  : 'Are you sure you want to cancel this transfer request?'}
              </p>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Reason for Cancellation / Door Rejection *
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Delivery vehicle issue / Wrong destination requested..."
                  value={cancelReason}
                  onChange={e => setCancelReason(e.target.value)}
                  style={{ ...inputStyle, width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" onClick={() => setCancelTarget(null)} style={btnSecondary}>
                  Close
                </button>
                <button type="submit" disabled={submittingCancel} style={{ ...btnPrimary, backgroundColor: '#dc2626' }}>
                  {submittingCancel ? 'Cancelling...' : 'Confirm Cancellation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL 4: CREATE / EDIT LOCATION ── */}
      {isLocationModalOpen && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalContentStyle, maxWidth: '520px' }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
                {locationForm.id ? 'Edit Stock Location' : 'New Stock Location'}
              </h3>
              <button onClick={() => setIsLocationModalOpen(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X size={18} color="#64748b" />
              </button>
            </div>

            <form onSubmit={handleSaveLocation} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Location Code *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. STORE-MAIN, KITCHEN-PANTRY"
                  value={locationForm.code}
                  onChange={e => setLocationForm({ ...locationForm, code: e.target.value })}
                  style={{ ...inputStyle, width: '100%', textTransform: 'uppercase' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Location Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Main Central Warehouse"
                  value={locationForm.name}
                  onChange={e => setLocationForm({ ...locationForm, name: e.target.value })}
                  style={{ ...inputStyle, width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Location Type *
                </label>
                <select
                  value={locationForm.location_type}
                  onChange={e => setLocationForm({ ...locationForm, location_type: e.target.value })}
                  style={{ ...inputStyle, width: '100%' }}
                >
                  <option value="warehouse">Central Warehouse / Main Store</option>
                  <option value="kitchen">Kitchen Production Pantry</option>
                  <option value="bar">Bar Station</option>
                  <option value="housekeeping">Housekeeping Storage</option>
                  <option value="minibar">Minibar Pantry</option>
                  <option value="scrap">Waste / Scrap Area</option>
                  <option value="other">Other Sub-Store</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Assigned Storekeeper / Custodian
                </label>
                <select
                  value={locationForm.custodian}
                  onChange={e => setLocationForm({ ...locationForm, custodian: e.target.value })}
                  style={{ ...inputStyle, width: '100%' }}
                >
                  <option value="">No Custodian Assigned</option>
                  {staffUsers.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.username} ({u.role})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                <input
                  type="checkbox"
                  id="loc_active"
                  checked={locationForm.is_active}
                  onChange={e => setLocationForm({ ...locationForm, is_active: e.target.checked })}
                />
                <label htmlFor="loc_active" style={{ fontSize: '13px', fontWeight: '600', color: '#334155', cursor: 'pointer' }}>
                  Active Location (Available for Requisitions & Receiving)
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setIsLocationModalOpen(false)} style={btnSecondary}>
                  Cancel
                </button>
                <button type="submit" disabled={submittingLocation} style={btnPrimary}>
                  {submittingLocation ? 'Saving...' : 'Save Location'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default StockTransferCenter;

