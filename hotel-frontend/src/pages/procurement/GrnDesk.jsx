import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Truck, CheckCircle2, AlertTriangle, Package,
  Search, Eye, X, FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

export default function GrnDesk({ userData, onNavigateToInvoice }) {
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [grns, setGrns] = useState([]);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Sub-view tab: 'orders' (POs to receive) vs 'grn_history' (Received GRNs)
  const [activeTab, setActiveTab] = useState('orders');
  const [searchTerm, setSearchTerm] = useState('');

  // Receiving Modal state
  const [selectedPo, setSelectedPo] = useState(null);
  const [isReceiveModalOpen, setIsReceiveModalOpen] = useState(false);
  const [selectedGrnDetail, setSelectedGrnDetail] = useState(null);
  const [isGrnDetailModalOpen, setIsGrnDetailModalOpen] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // Form State for Receiving
  const [locationId, setLocationId] = useState('');
  const [receivingNotes, setReceivingNotes] = useState('');
  const [receivedLines, setReceivedLines] = useState([]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [posRes, grnsRes, locsRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/orders/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_V1}/procurement/grns/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/locations/`, { headers }).catch(err => ({ data: [] }))
      ]);

      setPurchaseOrders(Array.isArray(posRes.data) ? posRes.data : (posRes.data?.results || []));
      setGrns(Array.isArray(grnsRes.data) ? grnsRes.data : (grnsRes.data?.results || []));
      const locList = Array.isArray(locsRes.data) ? locsRes.data : (locsRes.data?.results || []);
      setLocations(locList);
      if (locList.length > 0 && !locationId) {
        setLocationId(locList[0].id);
      }
    } catch (err) {
      console.error('Failed to load receiving data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load Goods Receipt data.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders, locationId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenReceiveModal = (po) => {
    setSelectedPo(po);
    const initialLines = (po.items || []).map(line => {
      const remaining = Math.max(0, parseFloat(line.quantity_ordered) - parseFloat(line.quantity_received || 0));
      return {
        po_item_id: line.id,
        item_id: line.item || line.item_id,
        item_code: line.item_code,
        item_name: line.item_name,
        item_unit: line.item_unit || 'KG',
        unit_price: parseFloat(line.unit_price || 0),
        quantity_ordered: parseFloat(line.quantity_ordered || 0),
        quantity_previously_received: parseFloat(line.quantity_received || 0),
        remaining_quantity: remaining,
        received_quantity: remaining.toFixed(4),
        batch_number: `BATCH-${new Date().toISOString().slice(2, 7).replace('-', '')}-${Math.floor(100 + Math.random() * 900)}`,
        expiry_date: ''
      };
    });
    setReceivedLines(initialLines);
    setReceivingNotes('Received in good condition and verified against delivery note.');
    setIsReceiveModalOpen(true);
  };

  const handleLineQtyChange = (idx, value) => {
    const updated = [...receivedLines];
    updated[idx].received_quantity = value;
    setReceivedLines(updated);
  };

  const handleLineBatchChange = (idx, field, value) => {
    const updated = [...receivedLines];
    updated[idx][field] = value;
    setReceivedLines(updated);
  };

  const calculatedTotalReceivedCost = receivedLines.reduce((acc, row) => {
    const q = parseFloat(row.received_quantity) || 0;
    return acc + (q * row.unit_price);
  }, 0);

  const handleConfirmReceipt = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      const validItems = receivedLines.filter(l => parseFloat(l.received_quantity) > 0);
      if (validItems.length === 0) {
        throw new Error('Please enter a positive received quantity for at least one item.');
      }

      for (const line of validItems) {
        if (parseFloat(line.received_quantity) > line.remaining_quantity + 0.0001) {
          throw new Error(`Received quantity ${line.received_quantity} exceeds remaining balance of ${line.remaining_quantity} for ${line.item_name}.`);
        }
      }

      const payload = {
        location_id: parseInt(locationId, 10),
        notes: receivingNotes.trim(),
        items: validItems.map(l => ({
          po_item_id: l.po_item_id,
          received_quantity: parseFloat(l.received_quantity).toFixed(4),
          batch_number: l.batch_number.trim(),
          expiry_date: l.expiry_date || null
        }))
      };

      const res = await axios.post(`${API_V1}/procurement/orders/${selectedPo.id}/receive-grn/`, payload, { headers: getHeaders() });
      setSuccessBanner(`Goods Receipt Note #${res.data?.grn_number || 'GRN'} generated! Interim GRNI accrual posted.`);
      setIsReceiveModalOpen(false);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to complete goods receipt.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const filteredOrders = purchaseOrders.filter(po => {
    if (po.status === 'cancelled') return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const numMatch = (po.po_number || '').toLowerCase().includes(q);
      const supMatch = (po.supplier_name || '').toLowerCase().includes(q);
      if (!numMatch && !supMatch) return false;
    }
    return true;
  });

  const filteredGrns = grns.filter(g => {
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const numMatch = (g.grn_number || '').toLowerCase().includes(q);
      const poMatch = (g.po_number || '').toLowerCase().includes(q);
      const supMatch = (g.supplier_name || '').toLowerCase().includes(q);
      if (!numMatch && !poMatch && !supMatch) return false;
    }
    return true;
  });

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

      {/* Desk Switcher & Search */}
      <div style={filterHeaderStyle}>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('orders')}
            style={{
              padding: '8px 16px',
              borderRadius: '10px',
              border: 'none',
              backgroundColor: activeTab === 'orders' ? '#0f766e' : '#ffffff',
              color: activeTab === 'orders' ? '#ffffff' : '#475569',
              fontWeight: '800',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(0,0,0,0.04)'
            }}
          >
            Pending Receiving ({purchaseOrders.filter(po => po.status === 'issued' || po.status === 'partially_received').length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('grn_history')}
            style={{
              padding: '8px 16px',
              borderRadius: '10px',
              border: 'none',
              backgroundColor: activeTab === 'grn_history' ? '#0f766e' : '#ffffff',
              color: activeTab === 'grn_history' ? '#ffffff' : '#475569',
              fontWeight: '800',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(0,0,0,0.04)'
            }}
          >
            Goods Receipt Notes Log ({grns.length})
          </button>
        </div>

        <div style={searchBoxStyle}>
          <Search size={16} color="#64748b" />
          <input
            type="text"
            placeholder="Search PO #, GRN #, or supplier..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={searchInputStyle}
          />
        </div>
      </div>

      {/* Tab 1: Orders Pending Physical Receiving */}
      {activeTab === 'orders' && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
              Purchase Orders for Delivery Receiving
            </h3>
          </div>

          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading purchase orders...</div>
          ) : filteredOrders.length === 0 ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
              <Truck size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
              <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No purchase orders awaiting receiving</p>
              <p style={{ margin: '4px 0 0', fontSize: '13px' }}>Convert awarded quotations into POs to receive deliveries.</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadRowStyle}>
                    <th style={thStyle}>PO Number</th>
                    <th style={thStyle}>Supplier</th>
                    <th style={thStyle}>Issued Date</th>
                    <th style={thStyle}>Total Amount</th>
                    <th style={thStyle}>Receiving Status</th>
                    <th style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map(po => {
                    const isFullyReceived = po.status === 'received';
                    return (
                      <tr key={po.id} style={trStyle}>
                        <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                          {po.po_number}
                        </td>
                        <td style={{ ...tdStyle, fontWeight: '600' }}>{po.supplier_name}</td>
                        <td style={tdStyle}>{po.issue_date ? new Date(po.issue_date).toLocaleDateString() : '-'}</td>
                        <td style={{ ...tdStyle, fontWeight: '700' }}>
                          ETB {parseFloat(po.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td style={tdStyle}>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: '700',
                            backgroundColor: isFullyReceived ? '#f0fdf4' : po.status === 'partially_received' ? '#fffbeb' : '#eff6ff',
                            color: isFullyReceived ? '#166534' : po.status === 'partially_received' ? '#b45309' : '#1e40af'
                          }}>
                            {po.status === 'issued' ? 'Awaiting Delivery' : po.status === 'partially_received' ? 'Partially Received' : 'Fully Received'}
                          </span>
                        </td>
                        <td style={tdStyle}>
                          {!isFullyReceived && (
                            <button
                              onClick={() => handleOpenReceiveModal(po)}
                              style={btnPrimaryStyle}
                            >
                              <Truck size={14} /> Receive Goods (GRN)
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: GRN Log History */}
      {activeTab === 'grn_history' && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
              Historical Goods Receipt Notes (GRN)
            </h3>
          </div>

          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading GRN records...</div>
          ) : filteredGrns.length === 0 ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
              <Package size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
              <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No GRNs posted yet</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadRowStyle}>
                    <th style={thStyle}>GRN Number</th>
                    <th style={thStyle}>PO Reference</th>
                    <th style={thStyle}>Supplier</th>
                    <th style={thStyle}>Received Date</th>
                    <th style={thStyle}>Received By</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredGrns.map(grn => (
                    <tr key={grn.id} style={trStyle}>
                      <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                        {grn.grn_number}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: '700' }}>#{grn.po_number}</td>
                      <td style={tdStyle}>{grn.supplier_name}</td>
                      <td style={tdStyle}>{new Date(grn.received_at).toLocaleString()}</td>
                      <td style={tdStyle}>{grn.received_by_name || 'Storekeeper'}</td>
                      <td style={tdStyle}>
                        <span style={{ padding: '3px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: '700', backgroundColor: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' }}>
                          Verified & Posted
                        </span>
                      </td>
                      <td style={tdStyle}>
                        <button
                          onClick={() => { setSelectedGrnDetail(grn); setIsGrnDetailModalOpen(true); }}
                          style={btnIconStyle}
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
      )}

      {/* Modal: Physical Receiving Form */}
      <AnimatePresence>
        {isReceiveModalOpen && selectedPo && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '840px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>
                    Goods Receipt Desk: PO #{selectedPo.po_number}
                  </h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Vendor: <strong>{selectedPo.supplier_name}</strong> | Record warehouse physical intake and assign inventory batches.
                  </p>
                </div>
                <button onClick={() => setIsReceiveModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleConfirmReceipt} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Receiving Storage Location *</label>
                    <select
                      value={locationId}
                      onChange={(e) => setLocationId(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      {locations.map(loc => (
                        <option key={loc.id} value={loc.id}>{loc.name} ({loc.code})</option>
                      ))}
                    </select>
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Delivery Note / Waybill Ref</label>
                    <input
                      type="text"
                      placeholder="e.g. DN-2026-9021"
                      value={receivingNotes}
                      onChange={(e) => setReceivingNotes(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* Receiving Lines */}
                <div>
                  <label style={labelStyle}>Received Line Items & Batch Assignment *</label>
                  <div style={{ maxHeight: '220px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                    <table style={tableStyle}>
                      <thead style={{ backgroundColor: '#f8fafc' }}>
                        <tr>
                          <th style={{ ...thStyle, width: '25%' }}>SKU / Description</th>
                          <th style={{ ...thStyle, width: '12%' }}>Ordered</th>
                          <th style={{ ...thStyle, width: '12%' }}>Remaining</th>
                          <th style={{ ...thStyle, width: '15%' }}>Received Qty *</th>
                          <th style={{ ...thStyle, width: '20%' }}>Batch Number *</th>
                          <th style={{ ...thStyle, width: '16%' }}>Expiry Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {receivedLines.map((line, idx) => (
                          <tr key={idx} style={trStyle}>
                            <td style={tdStyle}>
                              <div style={{ fontWeight: '700', color: '#0f766e' }}>{line.item_code}</div>
                              <div style={{ fontSize: '11px', color: '#64748b' }}>{line.item_name}</div>
                            </td>
                            <td style={tdStyle}>{line.quantity_ordered} {line.item_unit}</td>
                            <td style={{ ...tdStyle, fontWeight: '700' }}>{line.remaining_quantity.toFixed(2)}</td>
                            <td style={tdStyle}>
                              <input
                                type="number"
                                step="0.0001"
                                min="0"
                                max={line.remaining_quantity}
                                value={line.received_quantity}
                                onChange={(e) => handleLineQtyChange(idx, e.target.value)}
                                style={{ ...inputStyle, padding: '6px' }}
                                required
                              />
                            </td>
                            <td style={tdStyle}>
                              <input
                                type="text"
                                value={line.batch_number}
                                onChange={(e) => handleLineBatchChange(idx, 'batch_number', e.target.value)}
                                style={{ ...inputStyle, padding: '6px' }}
                                required
                              />
                            </td>
                            <td style={tdStyle}>
                              <input
                                type="date"
                                value={line.expiry_date}
                                onChange={(e) => handleLineBatchChange(idx, 'expiry_date', e.target.value)}
                                style={{ ...inputStyle, padding: '6px' }}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Accounting Preview (GRNI Accrual) */}
                <div style={{ backgroundColor: '#f0fdfa', border: '1px solid #ccfbf1', padding: '14px 18px', borderRadius: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '11px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase' }}>
                      Interim General Ledger Posting Preview:
                    </span>
                    <span style={{ fontWeight: '900', color: '#0f766e', fontSize: '15px' }}>
                      ETB {calculatedTotalReceivedCost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#334155', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div>• <strong>Debit Account 1300 (Inventory Asset):</strong> ETB {calculatedTotalReceivedCost.toFixed(2)}</div>
                    <div>• <strong>Credit Account 2010 (Goods Received Not Invoiced - GRNI):</strong> ETB {calculatedTotalReceivedCost.toFixed(2)}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsReceiveModalOpen(false)} style={btnSecondaryStyle}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting || calculatedTotalReceivedCost <= 0}
                    style={btnPrimaryStyle}
                  >
                    {actionSubmitting ? 'Posting Receipt...' : 'Confirm Delivery & Post GRNI'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: GRN Detail Inspection */}
      <AnimatePresence>
        {isGrnDetailModalOpen && selectedGrnDetail && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '680px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>
                    Goods Receipt Note: {selectedGrnDetail.grn_number}
                  </h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    PO: #{selectedGrnDetail.po_number} | Received: {new Date(selectedGrnDetail.received_at).toLocaleString()}
                  </p>
                </div>
                <button onClick={() => setIsGrnDetailModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <h4 style={{ margin: '4px 0 0', color: '#0f172a', fontSize: '13px', fontWeight: '800' }}>
                  Intake Inventory Batches
                </h4>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>SKU / Item</th>
                        <th style={thStyle}>Quantity</th>
                        <th style={thStyle}>Batch Number</th>
                        <th style={thStyle}>Expiry Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedGrnDetail.items || []).map((line, idx) => (
                        <tr key={idx} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>{line.item_code} — {line.item_name}</td>
                          <td style={tdStyle}>{parseFloat(line.quantity_received).toFixed(4)} {line.item_unit}</td>
                          <td style={{ ...tdStyle, fontWeight: '700', color: '#0f766e' }}>{line.batch_number}</td>
                          <td style={tdStyle}>{line.expiry_date || 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsGrnDetailModalOpen(false)} style={btnSecondaryStyle}>
                    Close
                  </button>
                  {onNavigateToInvoice && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsGrnDetailModalOpen(false);
                        onNavigateToInvoice();
                      }}
                      style={{ ...btnPrimaryStyle, backgroundColor: '#0284c7' }}
                    >
                      <FileText size={14} /> Open 3-Way Match & Invoicing Desk
                    </button>
                  )}
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
const btnPrimaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#0f766e', color: '#ffffff', border: 'none', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' };
const btnSecondaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer' };
const btnIconStyle = { display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4', borderRadius: '8px', padding: '5px 10px', fontSize: '12px', fontWeight: '700', cursor: 'pointer' };
const tableStyle = { width: '100%', borderCollapse: 'collapse', textAlign: 'left' };
const theadRowStyle = { backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' };
const thStyle = { padding: '12px 16px', fontSize: '11px', fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.4px' };
const trStyle = { borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' };
const tdStyle = { padding: '12px 16px', fontSize: '13px', color: '#334155' };

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
