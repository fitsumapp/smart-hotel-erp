import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  FileText, Plus, CheckCircle2, AlertTriangle,
  Search, Eye, Trash2, X, ShieldAlert
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

const DEPARTMENTS = [
  'Kitchen',
  'Bar',
  'Housekeeping',
  'Front Office',
  'Maintenance',
  'Food & Beverage',
  'Administrative'
];

export default function RequisitionDesk({ userData, onNavigateToRfq }) {
  const [requisitions, setRequisitions] = useState([]);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [departmentFilter, setDepartmentFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal states
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [selectedReq, setSelectedReq] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // New Requisition Form State
  const [newDepartment, setNewDepartment] = useState('Kitchen');
  const [newNotes, setNewNotes] = useState('');
  const [lineItems, setLineItems] = useState([
    { item_id: '', quantity_requested: '', estimated_unit_cost: '', notes: '' }
  ]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [reqsRes, itemsRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/requisitions/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/inventory-items/`, { headers }).catch(err => ({ data: [] }))
      ]);

      setRequisitions(Array.isArray(reqsRes.data) ? reqsRes.data : (reqsRes.data?.results || []));
      setInventoryItems(Array.isArray(itemsRes.data) ? itemsRes.data : (itemsRes.data?.results || []));
    } catch (err) {
      console.error('Failed to load requisitions data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load procurement requisitions.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Form Calculations
  const calculatedTotal = useMemo(() => {
    return lineItems.reduce((acc, row) => {
      const q = parseFloat(row.quantity_requested) || 0;
      const c = parseFloat(row.estimated_unit_cost) || 0;
      return acc + (q * c);
    }, 0);
  }, [lineItems]);

  // Tier estimation preview based on amount
  const estimatedTier = useMemo(() => {
    if (calculatedTotal <= 10000) {
      return { tier: 1, name: 'Tier 1 — Department Head', color: '#0f766e', bg: '#f0fdfa' };
    } else if (calculatedTotal <= 50000) {
      return { tier: 2, name: 'Tier 2 — General Manager', color: '#b45309', bg: '#fffbeb' };
    }
    return { tier: 3, name: 'Tier 3 — Finance Director / Board', color: '#b91c1c', bg: '#fef2f2' };
  }, [calculatedTotal]);

  const handleItemSelect = (index, itemId) => {
    const selectedItem = inventoryItems.find(i => String(i.id) === String(itemId));
    const updated = [...lineItems];
    updated[index].item_id = itemId;
    if (selectedItem) {
      updated[index].estimated_unit_cost = selectedItem.unit_cost || '0.00';
    }
    setLineItems(updated);
  };

  const handleLineChange = (index, field, value) => {
    const updated = [...lineItems];
    updated[index][field] = value;
    setLineItems(updated);
  };

  const handleAddLine = () => {
    setLineItems([...lineItems, { item_id: '', quantity_requested: '', estimated_unit_cost: '', notes: '' }]);
  };

  const handleRemoveLine = (index) => {
    if (lineItems.length === 1) return;
    setLineItems(lineItems.filter((_, idx) => idx !== index));
  };

  const handleCreateRequisition = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      if (!newDepartment) {
        throw new Error('Please select a department.');
      }
      const validItems = lineItems.filter(l => l.item_id && parseFloat(l.quantity_requested) > 0);
      if (validItems.length === 0) {
        throw new Error('Please add at least one line item with a valid quantity.');
      }

      const payload = {
        department: newDepartment,
        notes: newNotes,
        total_estimated_amount: calculatedTotal.toFixed(2),
        items: validItems.map(l => ({
          item_id: parseInt(l.item_id, 10),
          quantity_requested: parseFloat(l.quantity_requested).toFixed(4),
          estimated_unit_cost: parseFloat(l.estimated_unit_cost || 0).toFixed(2),
          notes: l.notes || ''
        }))
      };

      await axios.post(`${API_V1}/procurement/requisitions/`, payload, { headers: getHeaders() });
      setSuccessBanner('Purchase requisition created successfully!');
      setIsNewModalOpen(false);
      setNewNotes('');
      setLineItems([{ item_id: '', quantity_requested: '', estimated_unit_cost: '', notes: '' }]);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to create requisition.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleApproveRequisition = async (reqId) => {
    if (!window.confirm('Are you sure you want to approve this purchase requisition?')) return;
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(`${API_V1}/procurement/requisitions/${reqId}/approve/`, {}, { headers: getHeaders() });
      setSuccessBanner(`Requisition approved successfully.`);
      setIsDetailModalOpen(false);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to approve requisition.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleRejectRequisition = async (e) => {
    e.preventDefault();
    if (!rejectionReason.trim()) {
      alert('Please provide a mandatory rejection reason.');
      return;
    }
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(
        `${API_V1}/procurement/requisitions/${selectedReq.id}/reject/`,
        { rejection_reason: rejectionReason.trim() },
        { headers: getHeaders() }
      );
      setSuccessBanner(`Requisition #${selectedReq.requisition_number} rejected.`);
      setIsRejectModalOpen(false);
      setIsDetailModalOpen(false);
      setRejectionReason('');
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to reject requisition.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  // Filtered requisitions list
  const filteredRequisitions = requisitions.filter(r => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (departmentFilter !== 'all' && r.department !== departmentFilter) return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const numMatch = (r.requisition_number || '').toLowerCase().includes(q);
      const deptMatch = (r.department || '').toLowerCase().includes(q);
      const userMatch = (r.requested_by_name || r.requested_by?.username || '').toLowerCase().includes(q);
      if (!numMatch && !deptMatch && !userMatch) return false;
    }
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'approved':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4' }}>Approved</span>;
      case 'pending_approval':
      case 'draft':
        return <span style={{ ...badgeStyle, backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' }}>Pending Review</span>;
      case 'rejected':
        return <span style={{ ...badgeStyle, backgroundColor: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>Rejected</span>;
      case 'ordered':
      case 'partially_ordered':
        return <span style={{ ...badgeStyle, backgroundColor: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>Sourced (PO)</span>;
      default:
        return <span style={{ ...badgeStyle, backgroundColor: '#f1f5f9', color: '#475569' }}>{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Notifications */}
      {errorBanner && (
        <div style={bannerErrorStyle}>
          <AlertTriangle size={18} color="#dc2626" />
          <span style={{ flex: 1 }}>{errorBanner}</span>
          <button onClick={() => setErrorBanner('')} style={closeBannerBtn}><X size={14} /></button>
        </div>
      )}
      {successBanner && (
        <div style={bannerSuccessStyle}>
          <CheckCircle2 size={18} color="#059669" />
          <span style={{ flex: 1 }}>{successBanner}</span>
          <button onClick={() => setSuccessBanner('')} style={closeBannerBtn}><X size={14} /></button>
        </div>
      )}

      {/* Control & Filter Header */}
      <div style={filterHeaderStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={searchBoxStyle}>
            <Search size={16} color="#64748b" />
            <input
              type="text"
              placeholder="Search by PR #, dept, or staff..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={searchInputStyle}
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={selectStyle}
          >
            <option value="all">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="approved">Approved</option>
            <option value="ordered">Ordered</option>
            <option value="rejected">Rejected</option>
          </select>

          <select
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
            style={selectStyle}
          >
            <option value="all">All Departments</option>
            {DEPARTMENTS.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <button
          id="btn-new-requisition"
          onClick={() => setIsNewModalOpen(true)}
          style={btnPrimaryStyle}
        >
          <Plus size={16} /> New Requisition
        </button>
      </div>

      {/* Requisitions Table */}
      <div style={cardStyle}>
        <div style={cardHeaderStyle}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
            Purchase Requisitions ({filteredRequisitions.length})
          </h3>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
            Loading requisitions...
          </div>
        ) : filteredRequisitions.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
            <FileText size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No requisitions found</p>
            <p style={{ margin: '4px 0 0', fontSize: '13px' }}>Click "New Requisition" to create one.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr style={theadRowStyle}>
                  <th style={thStyle}>PR Number</th>
                  <th style={thStyle}>Department</th>
                  <th style={thStyle}>Requested By</th>
                  <th style={thStyle}>Date</th>
                  <th style={thStyle}>Est. Total</th>
                  <th style={thStyle}>Approval Status</th>
                  <th style={thStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRequisitions.map(req => (
                  <tr key={req.id} style={trStyle}>
                    <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                      {req.requisition_number}
                    </td>
                    <td style={tdStyle}>{req.department}</td>
                    <td style={tdStyle}>{req.requested_by_name || req.requested_by?.username || 'Staff'}</td>
                    <td style={tdStyle}>
                      {req.requested_at ? new Date(req.requested_at).toLocaleDateString() : '-'}
                    </td>
                    <td style={{ ...tdStyle, fontWeight: '700' }}>
                      ETB {parseFloat(req.total_estimated_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td style={tdStyle}>
                      {getStatusBadge(req.status)}
                    </td>
                    <td style={tdStyle}>
                      <button
                        onClick={() => { setSelectedReq(req); setIsDetailModalOpen(true); }}
                        style={btnIconStyle}
                        title="View Requisition Details"
                      >
                        <Eye size={15} /> Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Create Requisition */}
      <AnimatePresence>
        {isNewModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '750px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f172a' }}>New Purchase Requisition</h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Specify required inventory items and department sourcing details.
                  </p>
                </div>
                <button onClick={() => setIsNewModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleCreateRequisition} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Requesting Department *</label>
                    <select
                      value={newDepartment}
                      onChange={(e) => setNewDepartment(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      {DEPARTMENTS.map(d => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Approval Tier Preview</label>
                    <div style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      backgroundColor: estimatedTier.bg,
                      color: estimatedTier.color,
                      fontSize: '12px',
                      fontWeight: '800',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      border: `1px solid ${estimatedTier.color}33`
                    }}>
                      <ShieldAlert size={16} />
                      {estimatedTier.name}
                    </div>
                  </div>
                </div>

                <div style={formGroupStyle}>
                  <label style={labelStyle}>Justification / Notes</label>
                  <input
                    type="text"
                    placeholder="e.g. Weekly kitchen replenish or banquet event prep"
                    value={newNotes}
                    onChange={(e) => setNewNotes(e.target.value)}
                    style={inputStyle}
                  />
                </div>

                {/* Line Items Table */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <label style={{ ...labelStyle, fontSize: '12px' }}>Requested Line Items *</label>
                    <button
                      type="button"
                      onClick={handleAddLine}
                      style={{ ...btnPrimaryStyle, padding: '5px 12px', fontSize: '11px' }}
                    >
                      <Plus size={13} /> Add Row
                    </button>
                  </div>

                  <div style={{ maxHeight: '240px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
                    <table style={tableStyle}>
                      <thead style={{ backgroundColor: '#f8fafc', position: 'sticky', top: 0, zIndex: 1 }}>
                        <tr>
                          <th style={{ ...thStyle, width: '35%' }}>Catalog Item</th>
                          <th style={{ ...thStyle, width: '18%' }}>Quantity</th>
                          <th style={{ ...thStyle, width: '22%' }}>Est. Unit Cost (ETB)</th>
                          <th style={{ ...thStyle, width: '20%' }}>Subtotal</th>
                          <th style={{ ...thStyle, width: '5%' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineItems.map((row, idx) => {
                          const subtotal = (parseFloat(row.quantity_requested) || 0) * (parseFloat(row.estimated_unit_cost) || 0);
                          return (
                            <tr key={idx} style={trStyle}>
                              <td style={tdStyle}>
                                <select
                                  value={row.item_id}
                                  onChange={(e) => handleItemSelect(idx, e.target.value)}
                                  style={{ ...inputStyle, padding: '8px' }}
                                  required
                                >
                                  <option value="">Select SKU...</option>
                                  {inventoryItems.map(item => (
                                    <option key={item.id} value={item.id}>
                                      {item.item_code} — {item.name} ({item.unit})
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td style={tdStyle}>
                                <input
                                  type="number"
                                  step="0.0001"
                                  min="0.0001"
                                  placeholder="0.00"
                                  value={row.quantity_requested}
                                  onChange={(e) => handleLineChange(idx, 'quantity_requested', e.target.value)}
                                  style={{ ...inputStyle, padding: '8px' }}
                                  required
                                />
                              </td>
                              <td style={tdStyle}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  placeholder="0.00"
                                  value={row.estimated_unit_cost}
                                  onChange={(e) => handleLineChange(idx, 'estimated_unit_cost', e.target.value)}
                                  style={{ ...inputStyle, padding: '8px' }}
                                />
                              </td>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>
                                ETB {subtotal.toFixed(2)}
                              </td>
                              <td style={tdStyle}>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveLine(idx)}
                                  style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}
                                  disabled={lineItems.length === 1}
                                  title="Remove line"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px', paddingRight: '10px' }}>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '800', textTransform: 'uppercase' }}>
                        Total Estimated Amount:
                      </span>
                      <h3 style={{ margin: '2px 0 0', color: '#0f766e', fontWeight: '900', fontSize: '18px' }}>
                        ETB {calculatedTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </h3>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '15px' }}>
                  <button
                    type="button"
                    onClick={() => setIsNewModalOpen(false)}
                    style={btnSecondaryStyle}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting}
                    style={btnPrimaryStyle}
                  >
                    {actionSubmitting ? 'Creating Requisition...' : 'Submit Requisition'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Requisition Details & Approval */}
      <AnimatePresence>
        {isDetailModalOpen && selectedReq && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '700px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>
                      Requisition #{selectedReq.requisition_number}
                    </h3>
                    {getStatusBadge(selectedReq.status)}
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Department: <strong>{selectedReq.department}</strong> | Requested: {new Date(selectedReq.requested_at).toLocaleString()}
                  </p>
                </div>
                <button onClick={() => setIsDetailModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {selectedReq.notes && (
                  <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '10px', fontSize: '13px', color: '#334155' }}>
                    <strong>Notes:</strong> {selectedReq.notes}
                  </div>
                )}

                {selectedReq.status === 'rejected' && selectedReq.rejection_reason && (
                  <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', padding: '12px', borderRadius: '10px', fontSize: '13px', color: '#991b1b' }}>
                    <strong>Rejection Reason:</strong> {selectedReq.rejection_reason}
                  </div>
                )}

                <h4 style={{ margin: '8px 0 0', color: '#0f172a', fontSize: '14px', fontWeight: '800' }}>
                  Requested Line Items ({selectedReq.items?.length || 0})
                </h4>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>SKU / Item</th>
                        <th style={thStyle}>Quantity</th>
                        <th style={thStyle}>Est. Unit Cost</th>
                        <th style={thStyle}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedReq.items || []).map((line, idx) => (
                        <tr key={idx} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            {line.item_code} — {line.item_name}
                          </td>
                          <td style={tdStyle}>{parseFloat(line.quantity_requested).toFixed(4)} {line.item_unit}</td>
                          <td style={tdStyle}>ETB {parseFloat(line.estimated_unit_cost || 0).toFixed(2)}</td>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            ETB {(parseFloat(line.quantity_requested) * parseFloat(line.estimated_unit_cost || 0)).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f0fdfa', padding: '12px 18px', borderRadius: '10px', border: '1px solid #ccfbf1' }}>
                  <span style={{ fontWeight: '700', color: '#0f766e', fontSize: '13px' }}>Total Estimated Amount:</span>
                  <span style={{ fontWeight: '900', color: '#0f766e', fontSize: '16px' }}>
                    ETB {parseFloat(selectedReq.total_estimated_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>

                {/* Managerial Actions */}
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', marginTop: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '15px' }}>
                  <button
                    type="button"
                    onClick={() => setIsDetailModalOpen(false)}
                    style={btnSecondaryStyle}
                  >
                    Close
                  </button>

                  <div style={{ display: 'flex', gap: '10px' }}>
                    {selectedReq.status === 'approved' && onNavigateToRfq && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsDetailModalOpen(false);
                          onNavigateToRfq(selectedReq);
                        }}
                        style={{ ...btnPrimaryStyle, backgroundColor: '#0284c7' }}
                      >
                        Create RFQ from this PR
                      </button>
                    )}

                    {(selectedReq.status === 'draft' || selectedReq.status === 'pending_approval') && (
                      <>
                        <button
                          type="button"
                          onClick={() => setIsRejectModalOpen(true)}
                          style={{ ...btnSecondaryStyle, color: '#dc2626', borderColor: '#fca5a5' }}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          disabled={actionSubmitting}
                          onClick={() => handleApproveRequisition(selectedReq.id)}
                          style={btnPrimaryStyle}
                        >
                          {actionSubmitting ? 'Approving...' : 'Approve Requisition'}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Rejection Justification */}
      <AnimatePresence>
        {isRejectModalOpen && (
          <div style={{ ...modalOverlayStyle, zIndex: 1100 }}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '450px' }}
            >
              <div style={modalHeaderStyle}>
                <h3 style={{ margin: 0, fontWeight: '800', color: '#dc2626' }}>Reject Purchase Requisition</h3>
                <button onClick={() => setIsRejectModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleRejectRequisition} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#475569' }}>
                  Please enter a mandatory justification for rejecting Requisition #{selectedReq?.requisition_number}:
                </p>

                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Current stock sufficient or budget allocation exceeded."
                  rows={4}
                  style={{ ...inputStyle, resize: 'vertical' }}
                  required
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button type="button" onClick={() => setIsRejectModalOpen(false)} style={btnSecondaryStyle}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting}
                    style={{ ...btnPrimaryStyle, backgroundColor: '#dc2626' }}
                  >
                    {actionSubmitting ? 'Rejecting...' : 'Confirm Rejection'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Styles
const cardStyle = { backgroundColor: '#ffffff', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.15)', boxShadow: '0 4px 16px rgba(15,23,42,0.03)', overflow: 'hidden' };
const cardHeaderStyle = { padding: '18px 22px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const filterHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' };
const searchBoxStyle = { display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '8px 12px', width: '280px' };
const searchInputStyle = { border: 'none', outline: 'none', fontSize: '13px', width: '100%', background: 'transparent' };
const selectStyle = { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '13px', backgroundColor: '#ffffff', outline: 'none', cursor: 'pointer' };
const btnPrimaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#0f766e', color: '#ffffff', border: 'none', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' };
const btnSecondaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer' };
const btnIconStyle = { display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4', borderRadius: '8px', padding: '5px 10px', fontSize: '12px', fontWeight: '700', cursor: 'pointer' };
const tableStyle = { width: '100%', borderCollapse: 'collapse', textAlign: 'left' };
const theadRowStyle = { backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' };
const thStyle = { padding: '12px 16px', fontSize: '11px', fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.4px' };
const trStyle = { borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' };
const tdStyle = { padding: '12px 16px', fontSize: '13px', color: '#334155' };
const badgeStyle = { display: 'inline-block', padding: '3px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: '700' };

const bannerErrorStyle = { display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '12px 16px', borderRadius: '10px', fontSize: '13px' };
const bannerSuccessStyle = { display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '12px 16px', borderRadius: '10px', fontSize: '13px' };
const closeBannerBtn = { background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: '2px' };

const modalOverlayStyle = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(15,23,42,0.6)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '16px' };
const modalContentStyle = { backgroundColor: '#ffffff', borderRadius: '20px', padding: '26px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15)', border: '1px solid rgba(148,163,184,0.15)' };
const modalHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px', borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' };
const modalCloseBtn = { backgroundColor: '#f1f5f9', border: 'none', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#64748b' };
const formGroupStyle = { display: 'flex', flexDirection: 'column', gap: '6px' };
const labelStyle = { fontSize: '11px', fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.5px' };
const inputStyle = { padding: '10px 14px', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '13px', outline: 'none', width: '100%', boxSizing: 'border-box' };
