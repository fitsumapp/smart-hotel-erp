import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  FileText, Plus, CheckCircle2, Clock, AlertTriangle,
  Search, Eye, X, Send, Lock,
  Globe, Award, Check
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

export default function RfqDesk({ userData, onNavigateToQuotations, onNavigateToAward }) {
  const [rfqs, setRfqs] = useState([]);
  const [approvedRequisitions, setApprovedRequisitions] = useState([]);
  const [locations, setLocations] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal states
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [selectedRfq, setSelectedRfq] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // New RFQ Form State
  const [title, setTitle] = useState('');
  const [deliveryLocationId, setDeliveryLocationId] = useState('');
  const [submissionDeadline, setSubmissionDeadline] = useState('');
  const [isPublicBidding, setIsPublicBidding] = useState(true);
  const [invitedSupplierIds, setInvitedSupplierIds] = useState([]);
  const [selectedReqIds, setSelectedReqIds] = useState([]);
  const [termsAndConditions, setTermsAndConditions] = useState('Payment: Net 30 days upon delivery and 3-way match.');
  const [itemsData, setItemsData] = useState([]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [rfqRes, reqRes, locRes, supRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/rfqs/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_V1}/procurement/requisitions/?status=approved`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/locations/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/suppliers/`, { headers }).catch(err => ({ data: [] }))
      ]);

      setRfqs(Array.isArray(rfqRes.data) ? rfqRes.data : (rfqRes.data?.results || []));
      setApprovedRequisitions(Array.isArray(reqRes.data) ? reqRes.data : (reqRes.data?.results || []));
      const locList = Array.isArray(locRes.data) ? locRes.data : (locRes.data?.results || []);
      setLocations(locList);
      if (locList.length > 0 && !deliveryLocationId) {
        setDeliveryLocationId(locList[0].id);
      }
      setSuppliers(Array.isArray(supRes.data) ? supRes.data : (supRes.data?.results || []));
    } catch (err) {
      console.error('Failed to load RFQ data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load RFQ records.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders, deliveryLocationId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // When selected approved requisitions change, populate available line items
  useEffect(() => {
    if (selectedReqIds.length === 0) {
      setItemsData([]);
      return;
    }
    const lines = [];
    selectedReqIds.forEach(reqId => {
      const found = approvedRequisitions.find(r => String(r.id) === String(reqId));
      if (found && found.items) {
        found.items.forEach(it => {
          lines.push({
            item_id: it.item || it.item_id,
            item_code: it.item_code,
            item_name: it.item_name,
            item_unit: it.item_unit || 'KG',
            requisition_item_id: it.id,
            requisition_number: found.requisition_number,
            target_quantity: parseFloat(it.quantity_requested || 0).toFixed(4),
            specifications: it.notes || ''
          });
        });
      }
    });
    setItemsData(lines);
  }, [selectedReqIds, approvedRequisitions]);

  const handleCreateRfq = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      if (!title.trim()) throw new Error('Please enter an RFQ title.');
      if (!deliveryLocationId) throw new Error('Please select a delivery location.');
      if (!submissionDeadline) throw new Error('Please specify a submission deadline in the future.');
      if (new Date(submissionDeadline) <= new Date()) {
        throw new Error('Submission deadline must be set to a future date and time.');
      }
      if (!isPublicBidding && invitedSupplierIds.length === 0) {
        throw new Error('Restricted bidding requires selecting at least one invited supplier.');
      }
      if (itemsData.length === 0) {
        throw new Error('Please select at least one approved requisition with items to source.');
      }

      const payload = {
        title: title.trim(),
        delivery_location_id: parseInt(deliveryLocationId, 10),
        submission_deadline: new Date(submissionDeadline).toISOString(),
        is_public_bidding: isPublicBidding,
        invited_supplier_ids: isPublicBidding ? [] : invitedSupplierIds.map(id => parseInt(id, 10)),
        requisition_ids: selectedReqIds.map(id => parseInt(id, 10)),
        items_data: itemsData.map(l => ({
          item_id: parseInt(l.item_id, 10),
          requisition_item_id: parseInt(l.requisition_item_id, 10),
          target_quantity: parseFloat(l.target_quantity).toFixed(4),
          specifications: l.specifications || ''
        })),
        terms_and_conditions: termsAndConditions.trim()
      };

      await axios.post(`${API_V1}/procurement/rfqs/`, payload, { headers: getHeaders() });
      setSuccessBanner('Request for Quotation created successfully in Draft!');
      setIsNewModalOpen(false);
      setTitle('');
      setSelectedReqIds([]);
      setInvitedSupplierIds([]);
      setItemsData([]);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to create RFQ.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handlePublishRfq = async (rfqId) => {
    if (!window.confirm('Publish this RFQ? This will lock line items and open it for supplier bids.')) return;
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(`${API_V1}/procurement/rfqs/${rfqId}/publish/`, {}, { headers: getHeaders() });
      setSuccessBanner('RFQ published successfully! Suppliers may now submit bids.');
      setIsDetailModalOpen(false);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to publish RFQ.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleCloseRfq = async (rfqId) => {
    if (!window.confirm('Close bidding on this RFQ? No further quotations will be accepted.')) return;
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(`${API_V1}/procurement/rfqs/${rfqId}/close/`, {}, { headers: getHeaders() });
      setSuccessBanner('RFQ bidding closed. Proceed to Quotation Evaluation.');
      setIsDetailModalOpen(false);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to close RFQ.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const toggleSupplierInvite = (supId) => {
    if (invitedSupplierIds.includes(supId)) {
      setInvitedSupplierIds(invitedSupplierIds.filter(id => id !== supId));
    } else {
      setInvitedSupplierIds([...invitedSupplierIds, supId]);
    }
  };

  const toggleReqSelect = (reqId) => {
    if (selectedReqIds.includes(reqId)) {
      setSelectedReqIds(selectedReqIds.filter(id => id !== reqId));
    } else {
      setSelectedReqIds([...selectedReqIds, reqId]);
    }
  };

  const filteredRfqs = rfqs.filter(r => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const numMatch = (r.rfq_number || '').toLowerCase().includes(q);
      const titleMatch = (r.title || '').toLowerCase().includes(q);
      if (!numMatch && !titleMatch) return false;
    }
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'published':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' }}>Open for Bids</span>;
      case 'draft':
        return <span style={{ ...badgeStyle, backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' }}>Draft</span>;
      case 'closed':
        return <span style={{ ...badgeStyle, backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>Bidding Closed</span>;
      case 'awarded':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4' }}>Awarded</span>;
      case 'cancelled':
        return <span style={{ ...badgeStyle, backgroundColor: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>Cancelled</span>;
      default:
        return <span style={{ ...badgeStyle, backgroundColor: '#f1f5f9', color: '#475569' }}>{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Alerts */}
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

      {/* Controls */}
      <div style={filterHeaderStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={searchBoxStyle}>
            <Search size={16} color="#64748b" />
            <input
              type="text"
              placeholder="Search RFQ # or title..."
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
            <option value="published">Published (Open)</option>
            <option value="closed">Closed</option>
            <option value="awarded">Awarded</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <button
          id="btn-new-rfq"
          onClick={() => setIsNewModalOpen(true)}
          style={btnPrimaryStyle}
        >
          <Plus size={16} /> Create RFQ
        </button>
      </div>

      {/* RFQ List Table */}
      <div style={cardStyle}>
        <div style={cardHeaderStyle}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
            Requests for Quotation ({filteredRfqs.length})
          </h3>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading RFQs...</div>
        ) : filteredRfqs.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
            <FileText size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No RFQs found</p>
            <p style={{ margin: '4px 0 0', fontSize: '13px' }}>Create an RFQ from approved requisitions to invite vendor quotes.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr style={theadRowStyle}>
                  <th style={thStyle}>RFQ Number</th>
                  <th style={thStyle}>Title</th>
                  <th style={thStyle}>Mode</th>
                  <th style={thStyle}>Submission Deadline</th>
                  <th style={thStyle}>Items</th>
                  <th style={thStyle}>Quotes</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRfqs.map(rfq => {
                  const isExpired = new Date(rfq.submission_deadline) < new Date();
                  return (
                    <tr key={rfq.id} style={trStyle}>
                      <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                        {rfq.rfq_number}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: '600' }}>{rfq.title}</td>
                      <td style={tdStyle}>
                        {rfq.is_public_bidding ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#0369a1' }}>
                            <Globe size={13} /> Public
                          </span>
                        ) : (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#475569' }}>
                            <Lock size={13} /> Invited ({rfq.invited_suppliers?.length || 0})
                          </span>
                        )}
                      </td>
                      <td style={tdStyle}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isExpired ? '#dc2626' : '#334155' }}>
                          <Clock size={13} />
                          {new Date(rfq.submission_deadline).toLocaleString()}
                        </div>
                      </td>
                      <td style={tdStyle}>{rfq.items?.length || 0} lines</td>
                      <td style={tdStyle}>
                        <span style={{ fontWeight: '700', color: '#0f766e' }}>
                          {rfq.quotations_count !== undefined ? rfq.quotations_count : (rfq.quotations?.length || 0)} bids
                        </span>
                      </td>
                      <td style={tdStyle}>{getStatusBadge(rfq.status)}</td>
                      <td style={tdStyle}>
                        <button
                          onClick={() => { setSelectedRfq(rfq); setIsDetailModalOpen(true); }}
                          style={btnIconStyle}
                        >
                          <Eye size={15} /> Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Create RFQ */}
      <AnimatePresence>
        {isNewModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '780px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f172a' }}>Create Request for Quotation (RFQ)</h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Select approved requisitions and invite vendor quotations.
                  </p>
                </div>
                <button onClick={() => setIsNewModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleCreateRfq} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>RFQ Title *</label>
                  <input
                    type="text"
                    placeholder="e.g. November Bulk Produce & Meat Sourcing"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    style={inputStyle}
                    required
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Delivery Destination *</label>
                    <select
                      value={deliveryLocationId}
                      onChange={(e) => setDeliveryLocationId(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      {locations.map(loc => (
                        <option key={loc.id} value={loc.id}>{loc.name} ({loc.code})</option>
                      ))}
                    </select>
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Submission Deadline *</label>
                    <input
                      type="datetime-local"
                      value={submissionDeadline}
                      onChange={(e) => setSubmissionDeadline(e.target.value)}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                {/* Sourcing Requisitions */}
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Select Approved Requisitions to Source *</label>
                  {approvedRequisitions.length === 0 ? (
                    <div style={{ padding: '12px', backgroundColor: '#fffbeb', borderRadius: '10px', fontSize: '12px', color: '#b45309' }}>
                      No approved requisitions available. Please approve pending requisitions first.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', maxHeight: '100px', overflowY: 'auto', border: '1px solid #e2e8f0', padding: '8px', borderRadius: '10px' }}>
                      {approvedRequisitions.map(req => {
                        const isSelected = selectedReqIds.includes(req.id);
                        return (
                          <button
                            type="button"
                            key={req.id}
                            onClick={() => toggleReqSelect(req.id)}
                            style={{
                              padding: '6px 12px',
                              borderRadius: '20px',
                              border: isSelected ? '1.5px solid #0f766e' : '1px solid #cbd5e1',
                              backgroundColor: isSelected ? '#f0fdfa' : '#ffffff',
                              color: isSelected ? '#0f766e' : '#475569',
                              fontSize: '12px',
                              fontWeight: '700',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}
                          >
                            {isSelected && <Check size={13} />}
                            #{req.requisition_number} ({req.department})
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Bidding Mode & Invited Suppliers */}
                <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <label style={{ ...labelStyle, margin: 0 }}>Bidding Access Mode</label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: '700', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={isPublicBidding}
                        onChange={(e) => setIsPublicBidding(e.target.checked)}
                      />
                      <span>Open Public Bidding (Any verified vendor)</span>
                    </label>
                  </div>

                  {!isPublicBidding && (
                    <div style={{ marginTop: '10px' }}>
                      <label style={{ ...labelStyle, fontSize: '10px' }}>Select Authorized Invited Vendors *</label>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', maxHeight: '100px', overflowY: 'auto', border: '1px solid #cbd5e1', padding: '8px', borderRadius: '8px', backgroundColor: '#ffffff' }}>
                        {suppliers.map(sup => {
                          const isInvited = invitedSupplierIds.includes(sup.id);
                          return (
                            <button
                              type="button"
                              key={sup.id}
                              onClick={() => toggleSupplierInvite(sup.id)}
                              style={{
                                padding: '4px 10px',
                                borderRadius: '16px',
                                border: isInvited ? '1px solid #0f766e' : '1px solid #cbd5e1',
                                backgroundColor: isInvited ? '#f0fdfa' : '#ffffff',
                                color: isInvited ? '#0f766e' : '#475569',
                                fontSize: '11px',
                                fontWeight: '700',
                                cursor: 'pointer'
                              }}
                            >
                              {isInvited ? '✓ ' : '+ '} {sup.name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Selected Sourcing Lines Preview */}
                {itemsData.length > 0 && (
                  <div>
                    <label style={labelStyle}>Target Sourcing Items ({itemsData.length})</label>
                    <div style={{ maxHeight: '160px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                      <table style={tableStyle}>
                        <thead style={{ backgroundColor: '#f8fafc' }}>
                          <tr>
                            <th style={thStyle}>Item</th>
                            <th style={thStyle}>Source PR</th>
                            <th style={thStyle}>Target Quantity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {itemsData.map((line, idx) => (
                            <tr key={idx} style={trStyle}>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>{line.item_code} — {line.item_name}</td>
                              <td style={tdStyle}>#{line.requisition_number}</td>
                              <td style={tdStyle}>{line.target_quantity} {line.item_unit}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div style={formGroupStyle}>
                  <label style={labelStyle}>Terms & Conditions</label>
                  <textarea
                    rows={2}
                    value={termsAndConditions}
                    onChange={(e) => setTermsAndConditions(e.target.value)}
                    style={{ ...inputStyle, resize: 'vertical' }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsNewModalOpen(false)} style={btnSecondaryStyle}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting}
                    style={btnPrimaryStyle}
                  >
                    {actionSubmitting ? 'Creating RFQ...' : 'Save Draft RFQ'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: RFQ Details & Actions */}
      <AnimatePresence>
        {isDetailModalOpen && selectedRfq && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '740px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>
                      {selectedRfq.rfq_number}: {selectedRfq.title}
                    </h3>
                    {getStatusBadge(selectedRfq.status)}
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Deadline: {new Date(selectedRfq.submission_deadline).toLocaleString()} | Destination: {selectedRfq.delivery_location_name || 'STORE-MAIN'}
                  </p>
                </div>
                <button onClick={() => setIsDetailModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h4 style={{ margin: '4px 0 0', color: '#0f172a', fontSize: '14px', fontWeight: '800' }}>
                  Line Items ({selectedRfq.items?.length || 0})
                </h4>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>SKU / Description</th>
                        <th style={thStyle}>Target Quantity</th>
                        <th style={thStyle}>Specifications</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedRfq.items || []).map((line, idx) => (
                        <tr key={idx} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            {line.item_code} — {line.item_name}
                          </td>
                          <td style={tdStyle}>{parseFloat(line.target_quantity).toFixed(4)} {line.item_unit}</td>
                          <td style={tdStyle}>{line.specifications || 'Standard specifications'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {selectedRfq.terms_and_conditions && (
                  <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '10px', fontSize: '12px', color: '#475569' }}>
                    <strong>Terms:</strong> {selectedRfq.terms_and_conditions}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsDetailModalOpen(false)} style={btnSecondaryStyle}>
                    Close
                  </button>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    {selectedRfq.status === 'draft' && (
                      <button
                        type="button"
                        disabled={actionSubmitting}
                        onClick={() => handlePublishRfq(selectedRfq.id)}
                        style={{ ...btnPrimaryStyle, backgroundColor: '#059669' }}
                      >
                        <Send size={14} /> Publish RFQ for Bidding
                      </button>
                    )}

                    {selectedRfq.status === 'published' && (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setIsDetailModalOpen(false);
                            if (onNavigateToQuotations) onNavigateToQuotations(selectedRfq);
                          }}
                          style={{ ...btnPrimaryStyle, backgroundColor: '#0284c7' }}
                        >
                          <Plus size={14} /> Record Supplier Bid
                        </button>
                        <button
                          type="button"
                          disabled={actionSubmitting}
                          onClick={() => handleCloseRfq(selectedRfq.id)}
                          style={{ ...btnSecondaryStyle, color: '#dc2626', borderColor: '#fca5a5' }}
                        >
                          <Lock size={14} /> Close Bidding
                        </button>
                      </>
                    )}

                    {(selectedRfq.status === 'closed' || selectedRfq.status === 'awarded') && onNavigateToAward && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsDetailModalOpen(false);
                          onNavigateToAward(selectedRfq);
                        }}
                        style={{ ...btnPrimaryStyle, backgroundColor: '#7c3aed' }}
                      >
                        <Award size={14} /> View Split-Award Matrix
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Styling definitions
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
