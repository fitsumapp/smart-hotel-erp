import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  DollarSign, Plus, CheckCircle2, Clock, AlertTriangle,
  Search, Eye, X, Award
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

export default function QuotationDesk({ userData, initialRfq, onNavigateToAward }) {
  const [quotations, setQuotations] = useState([]);
  const [rfqs, setRfqs] = useState([]);
  const [requisitions, setRequisitions] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal states
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isEvaluateModalOpen, setIsEvaluateModalOpen] = useState(false);
  const [evaluationNotes, setEvaluationNotes] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // New Quotation Form State
  const [procurementMode, setProcurementMode] = useState(initialRfq ? 'rfq' : 'rfq');
  const [selectedRfqId, setSelectedRfqId] = useState(initialRfq ? String(initialRfq.id) : '');
  const [selectedReqId, setSelectedReqId] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [supplierReference, setSupplierReference] = useState('');
  const [soleSourceJustification, setSoleSourceJustification] = useState('');
  const [quotationDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [validUntil, setValidUntil] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split('T')[0];
  });
  const [deliveryLeadTimeDays, setDeliveryLeadTimeDays] = useState(7);
  const [paymentTerms] = useState('30 Days Net');
  const [currency, setCurrency] = useState('ETB');
  const [exchangeRate, setExchangeRate] = useState('1.0000');
  const [taxAmount, setTaxAmount] = useState('0.00');
  const [shippingAndHandling, setShippingAndHandling] = useState('0.00');
  const [customsAndDuties, setCustomsAndDuties] = useState('0.00');
  const [items, setItems] = useState([]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [quoteRes, rfqRes, reqRes, supRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/quotations/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_V1}/procurement/rfqs/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_V1}/procurement/requisitions/?status=approved`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/suppliers/`, { headers }).catch(err => ({ data: [] }))
      ]);

      setQuotations(Array.isArray(quoteRes.data) ? quoteRes.data : (quoteRes.data?.results || []));
      setRfqs(Array.isArray(rfqRes.data) ? rfqRes.data : (rfqRes.data?.results || []));
      setRequisitions(Array.isArray(reqRes.data) ? reqRes.data : (reqRes.data?.results || []));
      setSuppliers(Array.isArray(supRes.data) ? supRes.data : (supRes.data?.results || []));
    } catch (err) {
      console.error('Failed to load quotation data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load quotation records.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // When initialRfq is provided or changed, open modal pre-populated
  useEffect(() => {
    if (initialRfq) {
      setSelectedRfqId(String(initialRfq.id));
      setProcurementMode('rfq');
      setIsNewModalOpen(true);
    }
  }, [initialRfq]);

  // When selected RFQ changes, auto-load line items
  useEffect(() => {
    if (procurementMode === 'rfq' && selectedRfqId) {
      const targetRfq = rfqs.find(r => String(r.id) === String(selectedRfqId));
      if (targetRfq && targetRfq.items) {
        setItems(targetRfq.items.map(it => ({
          item_id: it.item || it.item_id,
          rfq_item_id: it.id,
          item_code: it.item_code,
          item_name: it.item_name,
          item_unit: it.item_unit || 'KG',
          quoted_quantity: parseFloat(it.target_quantity).toFixed(4),
          quoted_unit_price: '0.00',
          discount_percentage: '0.00',
          specifications: it.specifications || ''
        })));
      }
    } else if (procurementMode === 'sole_source' && selectedReqId) {
      const targetReq = requisitions.find(r => String(r.id) === String(selectedReqId));
      if (targetReq && targetReq.items) {
        setItems(targetReq.items.map(it => ({
          item_id: it.item || it.item_id,
          rfq_item_id: null,
          item_code: it.item_code,
          item_name: it.item_name,
          item_unit: it.item_unit || 'KG',
          quoted_quantity: parseFloat(it.quantity_requested).toFixed(4),
          quoted_unit_price: parseFloat(it.estimated_unit_cost || 0).toFixed(2),
          discount_percentage: '0.00',
          specifications: it.notes || ''
        })));
      }
    }
  }, [procurementMode, selectedRfqId, selectedReqId, rfqs, requisitions]);

  // Live Landed Cost Calculations
  const calculations = useMemo(() => {
    let subtotal = 0;
    items.forEach(line => {
      const q = parseFloat(line.quoted_quantity) || 0;
      const p = parseFloat(line.quoted_unit_price) || 0;
      const d = parseFloat(line.discount_percentage) || 0;
      const net = q * p * (1 - d / 100);
      subtotal += net;
    });

    const tax = parseFloat(taxAmount) || 0;
    const shipping = parseFloat(shippingAndHandling) || 0;
    const customs = parseFloat(customsAndDuties) || 0;
    const fx = parseFloat(exchangeRate) || 1.0;

    const totalQuoted = subtotal + tax + shipping + customs;
    const landedCostEtb = totalQuoted * fx;

    return {
      subtotal: subtotal.toFixed(2),
      totalQuoted: totalQuoted.toFixed(2),
      landedCostEtb: landedCostEtb.toFixed(2)
    };
  }, [items, taxAmount, shippingAndHandling, customsAndDuties, exchangeRate]);

  const handleLineChange = (index, field, value) => {
    const updated = [...items];
    updated[index][field] = value;
    setItems(updated);
  };

  const handleCreateQuotation = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      if (!supplierId) throw new Error('Please select a supplier.');
      if (procurementMode === 'sole_source' && !soleSourceJustification.trim()) {
        throw new Error('Mandatory sole-source justification is required when bypassing competitive RFQ bidding.');
      }
      if (items.length === 0) throw new Error('Quotation must contain at least one line item.');

      const invalidLines = items.filter(l => parseFloat(l.quoted_unit_price) <= 0);
      if (invalidLines.length > 0) {
        throw new Error('All quoted unit prices must be strictly positive.');
      }

      const payload = {
        rfq_id: procurementMode === 'rfq' && selectedRfqId ? parseInt(selectedRfqId, 10) : null,
        requisition_id: procurementMode === 'sole_source' && selectedReqId ? parseInt(selectedReqId, 10) : null,
        supplier_id: parseInt(supplierId, 10),
        supplier_reference: supplierReference.trim(),
        sole_source_justification: soleSourceJustification.trim(),
        quotation_date: quotationDate,
        valid_until: validUntil,
        delivery_lead_time_days: parseInt(deliveryLeadTimeDays, 10) || 7,
        payment_terms: paymentTerms.trim(),
        currency: currency,
        exchange_rate: parseFloat(exchangeRate).toFixed(4),
        tax_amount: parseFloat(taxAmount || 0).toFixed(2),
        shipping_and_handling: parseFloat(shippingAndHandling || 0).toFixed(2),
        customs_and_duties: parseFloat(customsAndDuties || 0).toFixed(2),
        items: items.map(l => ({
          item_id: parseInt(l.item_id, 10),
          rfq_item_id: l.rfq_item_id ? parseInt(l.rfq_item_id, 10) : null,
          quoted_quantity: parseFloat(l.quoted_quantity).toFixed(4),
          quoted_unit_price: parseFloat(l.quoted_unit_price).toFixed(2),
          discount_percentage: parseFloat(l.discount_percentage || 0).toFixed(2),
          specifications: l.specifications || ''
        }))
      };

      await axios.post(`${API_V1}/procurement/quotations/`, payload, { headers: getHeaders() });
      setSuccessBanner('Supplier quotation submitted successfully!');
      setIsNewModalOpen(false);
      setSupplierReference('');
      setSoleSourceJustification('');
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to submit quotation.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleEvaluateQuotation = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(
        `${API_V1}/procurement/quotations/${selectedQuote.id}/evaluate/`,
        { evaluation_notes: evaluationNotes.trim() },
        { headers: getHeaders() }
      );
      setSuccessBanner(`Quotation #${selectedQuote.quotation_number} marked as under evaluation.`);
      setIsEvaluateModalOpen(false);
      setIsDetailModalOpen(false);
      setEvaluationNotes('');
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to evaluate quotation.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const filteredQuotes = quotations.filter(q => {
    if (statusFilter !== 'all' && q.status !== statusFilter) return false;
    if (searchTerm.trim()) {
      const s = searchTerm.toLowerCase();
      const numMatch = (q.quotation_number || '').toLowerCase().includes(s);
      const supMatch = (q.supplier_name || '').toLowerCase().includes(s);
      const rfqMatch = (q.rfq_number || '').toLowerCase().includes(s);
      if (!numMatch && !supMatch && !rfqMatch) return false;
    }
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'submitted':
        return <span style={{ ...badgeStyle, backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>Submitted</span>;
      case 'under_evaluation':
        return <span style={{ ...badgeStyle, backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' }}>Under Evaluation</span>;
      case 'accepted':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' }}>Awarded</span>;
      case 'partially_awarded':
        return <span style={{ ...badgeStyle, backgroundColor: '#f5f3ff', color: '#6d28d9', border: '1px solid #ddd6fe' }}>Split Awarded</span>;
      case 'converted_to_po':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4' }}>Converted to PO</span>;
      case 'rejected':
        return <span style={{ ...badgeStyle, backgroundColor: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>Rejected</span>;
      case 'expired':
        return <span style={{ ...badgeStyle, backgroundColor: '#f1f5f9', color: '#64748b', border: '1px solid #cbd5e1' }}>Expired</span>;
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
              placeholder="Search quote #, supplier, or RFQ..."
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
            <option value="submitted">Submitted</option>
            <option value="under_evaluation">Under Evaluation</option>
            <option value="accepted">Awarded</option>
            <option value="partially_awarded">Split Awarded</option>
            <option value="converted_to_po">Converted to PO</option>
            <option value="rejected">Rejected</option>
            <option value="expired">Expired</option>
          </select>
        </div>

        <button
          id="btn-new-quotation"
          onClick={() => setIsNewModalOpen(true)}
          style={btnPrimaryStyle}
        >
          <Plus size={16} /> Record Supplier Bid
        </button>
      </div>

      {/* Quotations Table */}
      <div style={cardStyle}>
        <div style={cardHeaderStyle}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
            Supplier Quotations ({filteredQuotes.length})
          </h3>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading supplier bids...</div>
        ) : filteredQuotes.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
            <DollarSign size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No supplier quotations recorded</p>
            <p style={{ margin: '4px 0 0', fontSize: '13px' }}>Record bids against published RFQs or sole-source requisitions.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr style={theadRowStyle}>
                  <th style={thStyle}>Quote Number</th>
                  <th style={thStyle}>Supplier</th>
                  <th style={thStyle}>RFQ / Origin</th>
                  <th style={thStyle}>Currency</th>
                  <th style={thStyle}>Quoted Total</th>
                  <th style={thStyle}>Landed Cost (ETB)</th>
                  <th style={thStyle}>Validity</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredQuotes.map(quote => (
                  <tr key={quote.id} style={trStyle}>
                    <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                      {quote.quotation_number}
                    </td>
                    <td style={{ ...tdStyle, fontWeight: '600' }}>{quote.supplier_name}</td>
                    <td style={tdStyle}>
                      {quote.rfq_number ? (
                        <span style={{ color: '#0369a1', fontWeight: '700' }}>{quote.rfq_number}</span>
                      ) : (
                        <span style={{ color: '#b45309', fontWeight: '700' }}>Sole Source (PR #{quote.requisition_number})</span>
                      )}
                    </td>
                    <td style={tdStyle}>{quote.currency}</td>
                    <td style={{ ...tdStyle, fontWeight: '700' }}>
                      {quote.currency} {parseFloat(quote.total_quoted_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td style={{ ...tdStyle, fontWeight: '900', color: '#0f766e' }}>
                      ETB {parseFloat(quote.total_landed_cost_etb || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td style={tdStyle}>{new Date(quote.valid_until).toLocaleDateString()}</td>
                    <td style={tdStyle}>{getStatusBadge(quote.status)}</td>
                    <td style={tdStyle}>
                      <button
                        onClick={() => { setSelectedQuote(quote); setIsDetailModalOpen(true); }}
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

      {/* Modal: Record Supplier Quotation */}
      <AnimatePresence>
        {isNewModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '820px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f172a' }}>Record Supplier Quotation</h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Enter vendor pricing, line item discounts, freight, and compute landed cost in ETB.
                  </p>
                </div>
                <button onClick={() => setIsNewModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleCreateQuotation} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Sourcing Mode Switcher */}
                <div style={{ display: 'flex', gap: '14px', backgroundColor: '#f1f5f9', padding: '6px', borderRadius: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setProcurementMode('rfq')}
                    style={{
                      flex: 1,
                      padding: '8px 14px',
                      borderRadius: '8px',
                      border: 'none',
                      backgroundColor: procurementMode === 'rfq' ? '#ffffff' : 'transparent',
                      color: procurementMode === 'rfq' ? '#0f766e' : '#64748b',
                      fontWeight: '800',
                      fontSize: '12px',
                      cursor: 'pointer',
                      boxShadow: procurementMode === 'rfq' ? '0 2px 6px rgba(0,0,0,0.05)' : 'none'
                    }}
                  >
                    Competitive RFQ Bidding
                  </button>
                  <button
                    type="button"
                    onClick={() => setProcurementMode('sole_source')}
                    style={{
                      flex: 1,
                      padding: '8px 14px',
                      borderRadius: '8px',
                      border: 'none',
                      backgroundColor: procurementMode === 'sole_source' ? '#ffffff' : 'transparent',
                      color: procurementMode === 'sole_source' ? '#0f766e' : '#64748b',
                      fontWeight: '800',
                      fontSize: '12px',
                      cursor: 'pointer',
                      boxShadow: procurementMode === 'sole_source' ? '0 2px 6px rgba(0,0,0,0.05)' : 'none'
                    }}
                  >
                    Direct / Sole-Source Procurement
                  </button>
                </div>

                {/* Sourcing Link */}
                {procurementMode === 'rfq' ? (
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Linked RFQ *</label>
                    <select
                      value={selectedRfqId}
                      onChange={(e) => setSelectedRfqId(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      <option value="">Select published RFQ...</option>
                      {rfqs.filter(r => r.status === 'published' || r.status === 'closed').map(r => (
                        <option key={r.id} value={r.id}>{r.rfq_number} — {r.title} ({r.items?.length || 0} lines)</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={formGroupStyle}>
                      <label style={labelStyle}>Source Requisition *</label>
                      <select
                        value={selectedReqId}
                        onChange={(e) => setSelectedReqId(e.target.value)}
                        style={inputStyle}
                        required
                      >
                        <option value="">Select approved requisition...</option>
                        {requisitions.map(r => (
                          <option key={r.id} value={r.id}>#{r.requisition_number} ({r.department})</option>
                        ))}
                      </select>
                    </div>

                    <div style={formGroupStyle}>
                      <label style={{ ...labelStyle, color: '#b45309' }}>Mandatory Sole-Source Justification *</label>
                      <textarea
                        rows={2}
                        placeholder="State why competitive bidding was bypassed (e.g. exclusive supplier warranty, emergency repair, standardized OEM parts)."
                        value={soleSourceJustification}
                        onChange={(e) => setSoleSourceJustification(e.target.value)}
                        style={{ ...inputStyle, resize: 'vertical', borderColor: '#fde68a' }}
                        required
                      />
                    </div>
                  </div>
                )}

                {/* Vendor and Commercials */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Supplier *</label>
                    <select
                      value={supplierId}
                      onChange={(e) => setSupplierId(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      <option value="">Select supplier...</option>
                      {suppliers.map(s => (
                        <option key={s.id} value={s.id}>{s.name} ({s.tin_number || 'No TIN'})</option>
                      ))}
                    </select>
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Vendor Proposal Ref #</label>
                    <input
                      type="text"
                      placeholder="e.g. QUOTE-2026-902"
                      value={supplierReference}
                      onChange={(e) => setSupplierReference(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Valid Until (Expiry) *</label>
                    <input
                      type="date"
                      value={validUntil}
                      onChange={(e) => setValidUntil(e.target.value)}
                      style={inputStyle}
                      required
                    />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Lead Time (Days)</label>
                    <input
                      type="number"
                      min="1"
                      value={deliveryLeadTimeDays}
                      onChange={(e) => setDeliveryLeadTimeDays(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Currency</label>
                    <select
                      value={currency}
                      onChange={(e) => {
                        const c = e.target.value;
                        setCurrency(c);
                        if (c === 'ETB') setExchangeRate('1.0000');
                      }}
                      style={inputStyle}
                    >
                      <option value="ETB">ETB (Birr)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                    </select>
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Exchange Rate to ETB</label>
                    <input
                      type="number"
                      step="0.0001"
                      min="0.0001"
                      value={exchangeRate}
                      disabled={currency === 'ETB'}
                      onChange={(e) => setExchangeRate(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* Bidding Items Table */}
                <div>
                  <label style={labelStyle}>Line Item Pricing & Discounts *</label>
                  <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                    <table style={tableStyle}>
                      <thead style={{ backgroundColor: '#f8fafc' }}>
                        <tr>
                          <th style={{ ...thStyle, width: '30%' }}>Item Description</th>
                          <th style={{ ...thStyle, width: '18%' }}>Quoted Qty</th>
                          <th style={{ ...thStyle, width: '22%' }}>Unit Price ({currency})</th>
                          <th style={{ ...thStyle, width: '15%' }}>Discount %</th>
                          <th style={{ ...thStyle, width: '15%' }}>Net Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((line, idx) => {
                          const net = (parseFloat(line.quoted_quantity) || 0) * (parseFloat(line.quoted_unit_price) || 0) * (1 - (parseFloat(line.discount_percentage) || 0) / 100);
                          return (
                            <tr key={idx} style={trStyle}>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>{line.item_code} — {line.item_name}</td>
                              <td style={tdStyle}>
                                <input
                                  type="number"
                                  step="0.0001"
                                  min="0.0001"
                                  value={line.quoted_quantity}
                                  onChange={(e) => handleLineChange(idx, 'quoted_quantity', e.target.value)}
                                  style={{ ...inputStyle, padding: '6px' }}
                                  required
                                />
                              </td>
                              <td style={tdStyle}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0.01"
                                  placeholder="0.00"
                                  value={line.quoted_unit_price}
                                  onChange={(e) => handleLineChange(idx, 'quoted_unit_price', e.target.value)}
                                  style={{ ...inputStyle, padding: '6px' }}
                                  required
                                />
                              </td>
                              <td style={tdStyle}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  max="100"
                                  value={line.discount_percentage}
                                  onChange={(e) => handleLineChange(idx, 'discount_percentage', e.target.value)}
                                  style={{ ...inputStyle, padding: '6px' }}
                                />
                              </td>
                              <td style={{ ...tdStyle, fontWeight: '700' }}>
                                {currency} {net.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Header-Level Add-ons (Tax, Freight, Customs) */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', backgroundColor: '#f8fafc', padding: '14px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Taxes / VAT ({currency})</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={taxAmount}
                      onChange={(e) => setTaxAmount(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Freight & Shipping ({currency})</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={shippingAndHandling}
                      onChange={(e) => setShippingAndHandling(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Customs & Tariffs ({currency})</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={customsAndDuties}
                      onChange={(e) => setCustomsAndDuties(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* Live Landed Cost Summary Card */}
                <div style={{ backgroundColor: '#f0fdfa', border: '1.5px solid #99f6e4', padding: '14px 20px', borderRadius: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontSize: '11px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase' }}>
                      Commercial Subtotal: {currency} {calculations.subtotal}
                    </span>
                    <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#64748b' }}>
                      Total Quoted ({currency}): <strong>{currency} {calculations.totalQuoted}</strong>
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '11px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase' }}>
                      Total Landed Cost in ETB:
                    </span>
                    <h3 style={{ margin: '2px 0 0', color: '#0f766e', fontSize: '20px', fontWeight: '900' }}>
                      ETB {parseFloat(calculations.landedCostEtb).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </h3>
                  </div>
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
                    {actionSubmitting ? 'Recording Bid...' : 'Submit Quotation'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Quotation Details & Evaluation */}
      <AnimatePresence>
        {isDetailModalOpen && selectedQuote && (
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
                      Quotation #{selectedQuote.quotation_number}
                    </h3>
                    {getStatusBadge(selectedQuote.status)}
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Supplier: <strong>{selectedQuote.supplier_name}</strong> | Ref: {selectedQuote.supplier_reference || 'N/A'} | Valid until: {new Date(selectedQuote.valid_until).toLocaleDateString()}
                  </p>
                </div>
                <button onClick={() => setIsDetailModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {selectedQuote.sole_source_justification && (
                  <div style={{ backgroundColor: '#fffbeb', border: '1px solid #fde68a', padding: '12px', borderRadius: '10px', fontSize: '12px', color: '#b45309' }}>
                    <strong>Sole-Source Rationale:</strong> {selectedQuote.sole_source_justification}
                  </div>
                )}

                <h4 style={{ margin: '4px 0 0', color: '#0f172a', fontSize: '14px', fontWeight: '800' }}>
                  Quoted Line Items ({selectedQuote.items?.length || 0})
                </h4>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>SKU / Item</th>
                        <th style={thStyle}>Quoted Qty</th>
                        <th style={thStyle}>Unit Price</th>
                        <th style={thStyle}>Discount</th>
                        <th style={thStyle}>Line Total</th>
                        <th style={thStyle}>Award Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedQuote.items || []).map((line, idx) => (
                        <tr key={idx} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            {line.item_code} — {line.item_name}
                          </td>
                          <td style={tdStyle}>{parseFloat(line.quoted_quantity).toFixed(4)} {line.item_unit}</td>
                          <td style={tdStyle}>{selectedQuote.currency} {parseFloat(line.quoted_unit_price).toFixed(2)}</td>
                          <td style={tdStyle}>{parseFloat(line.discount_percentage || 0).toFixed(1)}%</td>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            {selectedQuote.currency} {parseFloat(line.line_total || 0).toFixed(2)}
                          </td>
                          <td style={tdStyle}>
                            <span style={{
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '11px',
                              fontWeight: '700',
                              backgroundColor: line.award_status === 'awarded' ? '#f0fdf4' : line.award_status === 'rejected' ? '#fef2f2' : '#f1f5f9',
                              color: line.award_status === 'awarded' ? '#166534' : line.award_status === 'rejected' ? '#991b1b' : '#64748b'
                            }}>
                              {line.award_status || 'pending'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Financial Summary */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', backgroundColor: '#f8fafc', padding: '12px', borderRadius: '10px' }}>
                  <div>
                    <span style={{ fontSize: '10px', color: '#64748b', fontWeight: '800', textTransform: 'uppercase' }}>Subtotal:</span>
                    <p style={{ margin: 0, fontWeight: '700', fontSize: '13px' }}>{selectedQuote.currency} {parseFloat(selectedQuote.subtotal || 0).toFixed(2)}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '10px', color: '#64748b', fontWeight: '800', textTransform: 'uppercase' }}>Tax / Freight:</span>
                    <p style={{ margin: 0, fontWeight: '700', fontSize: '13px' }}>{selectedQuote.currency} {(parseFloat(selectedQuote.tax_amount || 0) + parseFloat(selectedQuote.shipping_and_handling || 0)).toFixed(2)}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '10px', color: '#64748b', fontWeight: '800', textTransform: 'uppercase' }}>Exchange Rate:</span>
                    <p style={{ margin: 0, fontWeight: '700', fontSize: '13px' }}>{parseFloat(selectedQuote.exchange_rate || 1).toFixed(4)}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '10px', color: '#0f766e', fontWeight: '800', textTransform: 'uppercase' }}>Landed Cost (ETB):</span>
                    <p style={{ margin: 0, fontWeight: '900', color: '#0f766e', fontSize: '14px' }}>ETB {parseFloat(selectedQuote.total_landed_cost_etb || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsDetailModalOpen(false)} style={btnSecondaryStyle}>
                    Close
                  </button>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    {selectedQuote.status === 'submitted' && (
                      <button
                        type="button"
                        onClick={() => setIsEvaluateModalOpen(true)}
                        style={{ ...btnPrimaryStyle, backgroundColor: '#b45309' }}
                      >
                        <Clock size={14} /> Begin Committee Evaluation
                      </button>
                    )}

                    {onNavigateToAward && selectedQuote.rfq_id && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsDetailModalOpen(false);
                          onNavigateToAward({ id: selectedQuote.rfq_id, rfq_number: selectedQuote.rfq_number });
                        }}
                        style={{ ...btnPrimaryStyle, backgroundColor: '#7c3aed' }}
                      >
                        <Award size={14} /> Open Split-Award Matrix
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Evaluation Notes */}
      <AnimatePresence>
        {isEvaluateModalOpen && (
          <div style={{ ...modalOverlayStyle, zIndex: 1100 }}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '460px' }}
            >
              <div style={modalHeaderStyle}>
                <h3 style={{ margin: 0, fontWeight: '800', color: '#b45309' }}>Evaluate Supplier Quotation</h3>
                <button onClick={() => setIsEvaluateModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleEvaluateQuotation} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#475569' }}>
                  Mark Quotation #{selectedQuote?.quotation_number} from {selectedQuote?.supplier_name} as <strong>Under Evaluation</strong>:
                </p>

                <textarea
                  value={evaluationNotes}
                  onChange={(e) => setEvaluationNotes(e.target.value)}
                  placeholder="Record commercial compliance, delivery lead time suitability, or price competitiveness commentary..."
                  rows={4}
                  style={{ ...inputStyle, resize: 'vertical' }}
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button type="button" onClick={() => setIsEvaluateModalOpen(false)} style={btnSecondaryStyle}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting}
                    style={{ ...btnPrimaryStyle, backgroundColor: '#b45309' }}
                  >
                    {actionSubmitting ? 'Updating...' : 'Confirm Evaluation Status'}
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
