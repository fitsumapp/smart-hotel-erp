import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Award, CheckCircle2, AlertTriangle,
  ShoppingBag, Truck, FileText, X,
  RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

export default function AwardMatrixDesk({ userData, initialRfq, onNavigateToGrn }) {
  const [rfqs, setRfqs] = useState([]);
  const [selectedRfqId, setSelectedRfqId] = useState(initialRfq ? String(initialRfq.id) : '');
  const [rfqDetails, setRfqDetails] = useState(null);
  const [quotations, setQuotations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Award Selections: Map of rfq_item_id -> { quotation_id, quote_item_id, supplier_name }
  const [selections, setSelections] = useState({});
  const [justification, setJustification] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // PO Conversion Modal
  const [isPoModalOpen, setIsPoModalOpen] = useState(false);
  const [createdOrders, setCreatedOrders] = useState([]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  // Fetch RFQs for dropdown
  useEffect(() => {
    const fetchRfqs = async () => {
      try {
        const res = await axios.get(`${API_V1}/procurement/rfqs/`, { headers: getHeaders() });
        const list = Array.isArray(res.data) ? res.data : (res.data?.results || []);
        setRfqs(list);
        if (!selectedRfqId && list.length > 0) {
          const activeRfq = list.find(r => r.status === 'published' || r.status === 'closed' || r.status === 'awarded') || list[0];
          setSelectedRfqId(String(activeRfq.id));
        }
      } catch (err) {
        console.error('Failed to load RFQs:', err);
      }
    };
    fetchRfqs();
  }, [getHeaders, selectedRfqId]);

  // Load RFQ details and associated quotations
  const loadMatrixData = useCallback(async (rfqId) => {
    if (!rfqId) return;
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [rfqRes, quotesRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/rfqs/${rfqId}/`, { headers }),
        axios.get(`${API_V1}/procurement/quotations/?rfq_id=${rfqId}`, { headers })
      ]);

      setRfqDetails(rfqRes.data);
      const quotesList = Array.isArray(quotesRes.data) ? quotesRes.data : (quotesRes.data?.results || []);
      setQuotations(quotesList);

      // Pre-populate selections if already awarded
      const initialMap = {};
      quotesList.forEach(q => {
        (q.items || []).forEach(it => {
          if (it.award_status === 'awarded' && it.rfq_item) {
            initialMap[it.rfq_item] = {
              quotation_id: q.id,
              quote_item_id: it.id,
              supplier_name: q.supplier_name
            };
          }
        });
      });
      setSelections(initialMap);
    } catch (err) {
      console.error('Failed to load matrix data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load evaluation matrix.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    if (selectedRfqId) {
      loadMatrixData(selectedRfqId);
    }
  }, [selectedRfqId, loadMatrixData]);

  const handleSelectVendorLine = (rfqItemId, quotationId, quoteItemId, supplierName) => {
    setSelections(prev => ({
      ...prev,
      [rfqItemId]: { quotation_id: quotationId, quote_item_id: quoteItemId, supplier_name: supplierName }
    }));
  };

  const handleAwardQuotations = async (e) => {
    e.preventDefault();
    if (Object.keys(selections).length === 0) {
      alert('Please select at least one vendor to award.');
      return;
    }
    if (!justification.trim()) {
      alert('Mandatory managerial justification is required for awarding bids.');
      return;
    }

    setActionSubmitting(true);
    setErrorBanner('');
    try {
      // Build quotation evaluation payload
      const quotePayloadMap = {};
      quotations.forEach(q => {
        quotePayloadMap[q.id] = {
          quotation_id: q.id,
          items: []
        };
      });

      // Assign awarded status
      quotations.forEach(q => {
        (q.items || []).forEach(it => {
          const selected = selections[it.rfq_item];
          const isAwarded = selected && selected.quotation_id === q.id;
          quotePayloadMap[q.id].items.push({
            item_id: it.item || it.item_id,
            award_status: isAwarded ? 'awarded' : 'rejected'
          });
        });
      });

      const payload = {
        quotations: Object.values(quotePayloadMap),
        justification: justification.trim()
      };

      await axios.post(`${API_V1}/procurement/quotations/award/`, payload, { headers: getHeaders() });
      setSuccessBanner('Bid evaluation and split awards submitted successfully!');
      loadMatrixData(selectedRfqId);
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to award quotations.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleConvertToPo = async () => {
    const awardedQuotes = quotations.filter(q => q.status === 'accepted' || q.status === 'partially_awarded');
    if (awardedQuotes.length === 0) {
      alert('No awarded quotations found to convert. Please submit awards first.');
      return;
    }

    setActionSubmitting(true);
    setErrorBanner('');
    try {
      const payload = {
        quotation_ids: awardedQuotes.map(q => q.id)
      };

      const res = await axios.post(`${API_V1}/procurement/quotations/convert-to-po/`, payload, { headers: getHeaders() });
      const orders = Array.isArray(res.data) ? res.data : (res.data?.orders || []);
      setCreatedOrders(orders);
      setSuccessBanner(`Successfully generated ${orders.length} Purchase Order(s)!`);
      loadMatrixData(selectedRfqId);
      setIsPoModalOpen(true);
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to convert quotations to Purchase Orders.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const hasAwardedQuotes = quotations.some(q => q.status === 'accepted' || q.status === 'partially_awarded');
  const allConverted = quotations.length > 0 && quotations.every(q => q.status === 'converted_to_po');

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

      {/* Selector & Actions Bar */}
      <div style={cardStyle}>
        <div style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Award size={22} color="#7c3aed" />
            <div>
              <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
                Split-Award Evaluation Matrix
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#64748b' }}>
                Evaluate competing supplier bids side-by-side, split-award line items, and convert to Purchase Orders.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label style={{ fontSize: '12px', fontWeight: '800', color: '#475569' }}>RFQ:</label>
            <select
              value={selectedRfqId}
              onChange={(e) => setSelectedRfqId(e.target.value)}
              style={{ ...selectStyle, minWidth: '240px', fontWeight: '700' }}
            >
              {rfqs.map(r => (
                <option key={r.id} value={r.id}>
                  {r.rfq_number} — {r.title} ({r.status})
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => loadMatrixData(selectedRfqId)}
              style={btnSecondaryStyle}
              title="Refresh Matrix"
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Main Comparison Matrix */}
      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
          Loading evaluation matrix...
        </div>
      ) : !rfqDetails || quotations.length === 0 ? (
        <div style={{ ...cardStyle, padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
          <FileText size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
          <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No supplier quotes recorded for this RFQ</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px' }}>
            At least one vendor quote must be recorded in the Quotations desk before evaluating awards.
          </p>
        </div>
      ) : (
        <form onSubmit={handleAwardQuotations} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={cardStyle}>
            <div style={{ padding: '16px 22px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '11px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase' }}>
                  Target Sourcing Lines: {rfqDetails.items?.length || 0} | Competing Suppliers: {quotations.length}
                </span>
                <h4 style={{ margin: '2px 0 0', color: '#0f172a', fontWeight: '800' }}>
                  Line-by-Line Supplier Bid Comparison
                </h4>
              </div>

              {hasAwardedQuotes && !allConverted && (
                <button
                  type="button"
                  onClick={handleConvertToPo}
                  disabled={actionSubmitting}
                  style={{ ...btnPrimaryStyle, backgroundColor: '#059669' }}
                >
                  <ShoppingBag size={15} /> Convert Awarded Bids to PO
                </button>
              )}
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr style={theadRowStyle}>
                    <th style={{ ...thStyle, width: '22%' }}>RFQ Item Specification</th>
                    <th style={{ ...thStyle, width: '12%' }}>Target Qty</th>
                    {quotations.map(q => (
                      <th key={q.id} style={{ ...thStyle, textAlign: 'center', borderLeft: '1px solid #e2e8f0', minWidth: '180px' }}>
                        <div style={{ fontWeight: '800', color: '#0f172a' }}>{q.supplier_name}</div>
                        <div style={{ fontSize: '10px', color: '#64748b', fontWeight: '600' }}>
                          Quote #{q.quotation_number} ({q.currency})
                        </div>
                        <div style={{ fontSize: '10px', color: '#0f766e', fontWeight: '700' }}>
                          Lead: {q.delivery_lead_time_days || 7}d | Status: {q.status}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(rfqDetails.items || []).map(rfqLine => {
                    // Find lowest price quote for this line
                    let minUnitPrice = Infinity;
                    quotations.forEach(q => {
                      const qLine = (q.items || []).find(it => it.rfq_item === rfqLine.id || it.item_id === rfqLine.item);
                      if (qLine && parseFloat(qLine.quoted_unit_price) > 0) {
                        const price = parseFloat(qLine.quoted_unit_price);
                        if (price < minUnitPrice) minUnitPrice = price;
                      }
                    });

                    return (
                      <tr key={rfqLine.id} style={trStyle}>
                        <td style={tdStyle}>
                          <div style={{ fontWeight: '800', color: '#0f766e' }}>
                            {rfqLine.item_code} — {rfqLine.item_name}
                          </div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>
                            {rfqLine.specifications || 'Standard specifications'}
                          </div>
                        </td>
                        <td style={{ ...tdStyle, fontWeight: '700' }}>
                          {parseFloat(rfqLine.target_quantity).toFixed(4)} {rfqLine.item_unit}
                        </td>

                        {quotations.map(q => {
                          const quoteItem = (q.items || []).find(it => it.rfq_item === rfqLine.id || it.item_id === rfqLine.item);
                          if (!quoteItem) {
                            return (
                              <td key={q.id} style={{ ...tdStyle, textAlign: 'center', color: '#cbd5e1', borderLeft: '1px solid #f1f5f9' }}>
                                No Bid
                              </td>
                            );
                          }

                          const unitPrice = parseFloat(quoteItem.quoted_unit_price || 0);
                          const isLowest = unitPrice === minUnitPrice && minUnitPrice !== Infinity;
                          const isSelected = selections[rfqLine.id]?.quotation_id === q.id;

                          return (
                            <td
                              key={q.id}
                              style={{
                                ...tdStyle,
                                textAlign: 'center',
                                borderLeft: '1px solid #f1f5f9',
                                backgroundColor: isSelected ? '#f0fdf4' : 'transparent',
                                transition: 'background 0.2s'
                              }}
                            >
                              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                                <div style={{ fontWeight: '800', fontSize: '14px', color: isLowest ? '#166534' : '#0f172a' }}>
                                  {q.currency} {unitPrice.toFixed(2)}
                                  {isLowest && (
                                    <span style={{ marginLeft: '4px', fontSize: '10px', backgroundColor: '#bbf7d0', color: '#166534', padding: '1px 5px', borderRadius: '8px' }}>
                                      Best
                                    </span>
                                  )}
                                </div>

                                <div style={{ fontSize: '11px', color: '#64748b' }}>
                                  Net: {q.currency} {parseFloat(quoteItem.line_total || 0).toFixed(2)}
                                  {parseFloat(quoteItem.discount_percentage || 0) > 0 && ` (${quoteItem.discount_percentage}% off)`}
                                </div>

                                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer', marginTop: '4px' }}>
                                  <input
                                    type="radio"
                                    name={`award_selection_${rfqLine.id}`}
                                    checked={isSelected}
                                    onChange={() => handleSelectVendorLine(rfqLine.id, q.id, quoteItem.id, q.supplier_name)}
                                  />
                                  <span style={{ fontSize: '11px', fontWeight: '800', color: isSelected ? '#166534' : '#475569' }}>
                                    {isSelected ? 'Awarded' : 'Award to this vendor'}
                                  </span>
                                </label>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Managerial Justification & Award Submission */}
          <div style={{ ...cardStyle, padding: '20px 24px' }}>
            <h4 style={{ margin: '0 0 10px', color: '#0f172a', fontWeight: '800' }}>
              Managerial Award Justification & Sign-off
            </h4>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Award Decision Rationale *</label>
              <textarea
                rows={3}
                placeholder="State the justification for this award (e.g. lowest compliant landed cost, fastest delivery time, or dual-sourcing risk mitigation)..."
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                style={{ ...inputStyle, resize: 'vertical' }}
                required
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
              <div style={{ fontSize: '13px', color: '#64748b' }}>
                Selected Awards: <strong>{Object.keys(selections).length}</strong> of {rfqDetails.items?.length || 0} lines
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={actionSubmitting || Object.keys(selections).length === 0}
                  style={btnPrimaryStyle}
                >
                  {actionSubmitting ? 'Submitting Awards...' : 'Save & Confirm Split Awards'}
                </button>
              </div>
            </div>
          </div>
        </form>
      )}

      {/* Modal: Purchase Orders Created Confirmation */}
      <AnimatePresence>
        {isPoModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '560px' }}
            >
              <div style={modalHeaderStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <CheckCircle2 size={24} color="#059669" />
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>Purchase Orders Issued</h3>
                </div>
                <button onClick={() => setIsPoModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#475569' }}>
                  Distinct Purchase Orders have been generated atomically with prorated freight and customs:
                </p>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>PO Number</th>
                        <th style={thStyle}>Supplier</th>
                        <th style={thStyle}>Total Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {createdOrders.map(po => (
                        <tr key={po.id} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                            {po.po_number}
                          </td>
                          <td style={tdStyle}>{po.supplier_name || 'Vendor'}</td>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            ETB {parseFloat(po.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setIsPoModalOpen(false)}
                    style={btnSecondaryStyle}
                  >
                    Dismiss
                  </button>
                  {onNavigateToGrn && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsPoModalOpen(false);
                        onNavigateToGrn();
                      }}
                      style={{ ...btnPrimaryStyle, backgroundColor: '#0284c7' }}
                    >
                      <Truck size={14} /> Open Goods Receiving Desk
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
const selectStyle = { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '13px', backgroundColor: '#ffffff', outline: 'none', cursor: 'pointer' };
const btnPrimaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#7c3aed', color: '#ffffff', border: 'none', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' };
const btnSecondaryStyle = { display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '9px 16px', fontSize: '13px', fontWeight: '700', cursor: 'pointer' };
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
