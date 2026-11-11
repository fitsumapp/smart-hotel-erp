import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  FileText, CheckCircle2, AlertTriangle,
  Search, Eye, X, Scale
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../../apiConfig';
import { apiErrorMessage } from '../../apiClient';

const API_V1 = `${API_BASE_URL}/v1`;

export default function InvoiceMatchingDesk({ userData }) {
  const [invoices, setInvoices] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState('');
  const [successBanner, setSuccessBanner] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal states
  const [isMatchModalOpen, setIsMatchModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // New Invoice Form State
  const [selectedPoId, setSelectedPoId] = useState('');
  const [vendorInvoiceNumber, setVendorInvoiceNumber] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [dueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split('T')[0];
  });
  const [taxAmount, setTaxAmount] = useState('0.00');
  const [shippingAmount, setShippingAmount] = useState('0.00');
  const [lineItems, setLineItems] = useState([]);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorBanner('');
    try {
      const headers = getHeaders();
      const [invRes, posRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/invoices/`, { headers }).catch(err => ({ data: [] })),
        axios.get(`${API_V1}/procurement/orders/`, { headers }).catch(err => ({ data: [] }))
      ]);

      setInvoices(Array.isArray(invRes.data) ? invRes.data : (invRes.data?.results || []));
      setPurchaseOrders(Array.isArray(posRes.data) ? posRes.data : (posRes.data?.results || []));
    } catch (err) {
      console.error('Failed to load invoice matching data:', err);
      setErrorBanner(apiErrorMessage(err, 'Failed to load supplier invoices.'));
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // When PO is selected, populate 3-Way Match line items
  useEffect(() => {
    if (!selectedPoId) {
      setLineItems([]);
      return;
    }
    const po = purchaseOrders.find(p => String(p.id) === String(selectedPoId));
    if (po && po.items) {
      setLineItems(po.items.map(line => {
        const ordered = parseFloat(line.quantity_ordered || 0);
        const received = parseFloat(line.quantity_received || 0);
        const agreedPrice = parseFloat(line.unit_price || 0);
        return {
          po_item_id: line.id,
          item_id: line.item || line.item_id,
          item_code: line.item_code,
          item_name: line.item_name,
          item_unit: line.item_unit || 'KG',
          po_quantity: ordered,
          po_unit_price: agreedPrice,
          grn_received_quantity: received,
          invoiced_quantity: received.toFixed(4),
          invoiced_unit_price: agreedPrice.toFixed(2)
        };
      }));
    }
  }, [selectedPoId, purchaseOrders]);

  const handleLineChange = (index, field, value) => {
    const updated = [...lineItems];
    updated[index][field] = value;
    setLineItems(updated);
  };

  // 3-Way Match Financial Impact Calculations
  const reconciliation = useMemo(() => {
    let billedGoodsSubtotal = 0;
    let grniClearingTotal = 0;
    let totalPpv = 0; // Purchase Price Variance

    lineItems.forEach(line => {
      const billedQty = parseFloat(line.invoiced_quantity) || 0;
      const billedPrice = parseFloat(line.invoiced_unit_price) || 0;
      const poPrice = line.po_unit_price;

      const billedLineTotal = billedQty * billedPrice;
      const grniLineTotal = billedQty * poPrice;
      const linePpv = billedQty * (billedPrice - poPrice);

      billedGoodsSubtotal += billedLineTotal;
      grniClearingTotal += grniLineTotal;
      totalPpv += linePpv;
    });

    const tax = parseFloat(taxAmount) || 0;
    const shipping = parseFloat(shippingAmount) || 0;
    const totalPayable = billedGoodsSubtotal + tax + shipping;

    // Check double-entry balance:
    // Debits: GRNI (grniClearingTotal) + PPV (if > 0) + Tax + Shipping
    // Credits: AP (totalPayable) + PPV (if < 0)
    let totalDebit = grniClearingTotal + (totalPpv > 0 ? totalPpv : 0) + tax + shipping;
    let totalCredit = totalPayable + (totalPpv < 0 ? Math.abs(totalPpv) : 0);

    return {
      billedGoodsSubtotal: billedGoodsSubtotal.toFixed(2),
      grniClearingTotal: grniClearingTotal.toFixed(2),
      totalPpv: totalPpv.toFixed(2),
      totalPayable: totalPayable.toFixed(2),
      totalDebit: totalDebit.toFixed(2),
      totalCredit: totalCredit.toFixed(2),
      isBalanced: Math.abs(totalDebit - totalCredit) < 0.01
    };
  }, [lineItems, taxAmount, shippingAmount]);

  const handleRecordInvoice = async (e) => {
    e.preventDefault();
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      if (!selectedPoId) throw new Error('Please select a purchase order to match against.');
      if (!vendorInvoiceNumber.trim()) throw new Error('Vendor invoice number is required.');
      if (lineItems.length === 0) throw new Error('Invoice must contain at least one line item.');

      const targetPo = purchaseOrders.find(p => String(p.id) === String(selectedPoId));

      const payload = {
        purchase_order_id: parseInt(selectedPoId, 10),
        supplier_id: targetPo?.supplier || targetPo?.supplier_id,
        invoice_number: vendorInvoiceNumber.trim(),
        invoice_date: invoiceDate,
        due_date: dueDate,
        tax_amount: parseFloat(taxAmount || 0).toFixed(2),
        shipping_amount: parseFloat(shippingAmount || 0).toFixed(2),
        items: lineItems.map(l => ({
          po_item_id: l.po_item_id,
          billed_quantity: parseFloat(l.invoiced_quantity).toFixed(4),
          unit_price: parseFloat(l.invoiced_unit_price).toFixed(2)
        }))
      };

      await axios.post(`${API_V1}/procurement/invoices/match-and-record/`, payload, { headers: getHeaders() });
      setSuccessBanner(`Supplier invoice #${vendorInvoiceNumber} matched and recorded!`);
      setIsMatchModalOpen(false);
      setVendorInvoiceNumber('');
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to match and record supplier invoice.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleApproveInvoice = async (invoiceId) => {
    if (!window.confirm('Approve this matched invoice? This will recognize Accounts Payable liability and post the final GL journal entry.')) return;
    setActionSubmitting(true);
    setErrorBanner('');
    try {
      await axios.post(`${API_V1}/procurement/invoices/${invoiceId}/approve/`, {}, { headers: getHeaders() });
      setSuccessBanner(`Invoice approved! General Ledger journal entries posted successfully.`);
      setIsDetailModalOpen(false);
      fetchData();
    } catch (err) {
      setErrorBanner(apiErrorMessage(err, 'Failed to approve supplier invoice.'));
    } finally {
      setActionSubmitting(false);
    }
  };

  const filteredInvoices = invoices.filter(inv => {
    if (statusFilter !== 'all' && inv.status !== statusFilter) return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const numMatch = (inv.invoice_number || '').toLowerCase().includes(q);
      const poMatch = (inv.po_number || '').toLowerCase().includes(q);
      const supMatch = (inv.supplier_name || '').toLowerCase().includes(q);
      if (!numMatch && !poMatch && !supMatch) return false;
    }
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'approved':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' }}>Approved & Posted</span>;
      case 'matched':
        return <span style={{ ...badgeStyle, backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>Matched (Pending Approval)</span>;
      case 'variance_flagged':
        return <span style={{ ...badgeStyle, backgroundColor: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>Price Variance Flagged</span>;
      case 'paid':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4' }}>Paid</span>;
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
              placeholder="Search invoice #, PO #, supplier..."
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
            <option value="matched">Matched (Pending)</option>
            <option value="approved">Approved</option>
            <option value="variance_flagged">Variance Flagged</option>
            <option value="paid">Paid</option>
          </select>
        </div>

        <button
          id="btn-match-invoice"
          onClick={() => setIsMatchModalOpen(true)}
          style={btnPrimaryStyle}
        >
          <Scale size={16} /> 3-Way Match & Record Invoice
        </button>
      </div>

      {/* Invoice Table */}
      <div style={cardStyle}>
        <div style={cardHeaderStyle}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '800' }}>
            Supplier Invoices & 3-Way Matching ({filteredInvoices.length})
          </h3>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading supplier invoices...</div>
        ) : filteredInvoices.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
            <FileText size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0, fontWeight: '700', fontSize: '15px' }}>No supplier invoices recorded</p>
            <p style={{ margin: '4px 0 0', fontSize: '13px' }}>Click "3-Way Match & Record Invoice" to verify vendor billings.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr style={theadRowStyle}>
                  <th style={thStyle}>Invoice Number</th>
                  <th style={thStyle}>PO Reference</th>
                  <th style={thStyle}>Supplier</th>
                  <th style={thStyle}>Invoice Date</th>
                  <th style={thStyle}>Due Date</th>
                  <th style={thStyle}>Total Payable</th>
                  <th style={thStyle}>Match Status</th>
                  <th style={thStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredInvoices.map(inv => (
                  <tr key={inv.id} style={trStyle}>
                    <td style={{ ...tdStyle, fontWeight: '800', color: '#0f766e' }}>
                      {inv.invoice_number}
                    </td>
                    <td style={{ ...tdStyle, fontWeight: '700' }}>#{inv.po_number}</td>
                    <td style={{ ...tdStyle, fontWeight: '600' }}>{inv.supplier_name}</td>
                    <td style={tdStyle}>{new Date(inv.invoice_date).toLocaleDateString()}</td>
                    <td style={tdStyle}>{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '-'}</td>
                    <td style={{ ...tdStyle, fontWeight: '900', color: '#0f766e' }}>
                      ETB {parseFloat(inv.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td style={tdStyle}>{getStatusBadge(inv.status)}</td>
                    <td style={tdStyle}>
                      <button
                        onClick={() => { setSelectedInvoice(inv); setIsDetailModalOpen(true); }}
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

      {/* Modal: 3-Way Match & Record Invoice */}
      <AnimatePresence>
        {isMatchModalOpen && (
          <div style={modalOverlayStyle}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{ ...modalContentStyle, width: '860px' }}
            >
              <div style={modalHeaderStyle}>
                <div>
                  <h3 style={{ margin: 0, fontWeight: '800', color: '#0f766e' }}>
                    3-Way Match Verification & Invoice Intake
                  </h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Compare PO Agreed vs GRN Received vs Vendor Invoiced amounts.
                  </p>
                </div>
                <button onClick={() => setIsMatchModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleRecordInvoice} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: '14px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Target Purchase Order *</label>
                    <select
                      value={selectedPoId}
                      onChange={(e) => setSelectedPoId(e.target.value)}
                      style={inputStyle}
                      required
                    >
                      <option value="">Select PO...</option>
                      {purchaseOrders.map(p => (
                        <option key={p.id} value={p.id}>
                          {p.po_number} — {p.supplier_name} ({p.status})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Vendor Invoice Number *</label>
                    <input
                      type="text"
                      placeholder="e.g. INV-2026-9021"
                      value={vendorInvoiceNumber}
                      onChange={(e) => setVendorInvoiceNumber(e.target.value)}
                      style={inputStyle}
                      required
                    />
                  </div>

                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Invoice Date *</label>
                    <input
                      type="date"
                      value={invoiceDate}
                      onChange={(e) => setInvoiceDate(e.target.value)}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                {/* 3-Way Match Comparison Matrix */}
                {lineItems.length > 0 && (
                  <div>
                    <label style={labelStyle}>3-Way Reconciliation Matrix (PO vs GRN vs Vendor Bill)</label>
                    <div style={{ maxHeight: '220px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                      <table style={tableStyle}>
                        <thead style={{ backgroundColor: '#f8fafc' }}>
                          <tr>
                            <th style={{ ...thStyle, width: '22%' }}>SKU / Item</th>
                            <th style={{ ...thStyle, width: '13%' }}>PO Qty</th>
                            <th style={{ ...thStyle, width: '13%' }}>GRN Qty</th>
                            <th style={{ ...thStyle, width: '16%' }}>Billed Qty *</th>
                            <th style={{ ...thStyle, width: '18%' }}>Billed Unit Price *</th>
                            <th style={{ ...thStyle, width: '18%' }}>Variances</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lineItems.map((line, idx) => {
                            const billedQty = parseFloat(line.invoiced_quantity) || 0;
                            const billedPrice = parseFloat(line.invoiced_unit_price) || 0;
                            const qtyVariance = billedQty - line.grn_received_quantity;
                            const priceVariance = billedPrice - line.po_unit_price;

                            return (
                              <tr key={idx} style={trStyle}>
                                <td style={tdStyle}>
                                  <div style={{ fontWeight: '700', color: '#0f766e' }}>{line.item_code}</div>
                                  <div style={{ fontSize: '11px', color: '#64748b' }}>{line.item_name}</div>
                                </td>
                                <td style={tdStyle}>{line.po_quantity} {line.item_unit}</td>
                                <td style={{ ...tdStyle, fontWeight: '700', color: '#166534' }}>
                                  {line.grn_received_quantity} {line.item_unit}
                                </td>
                                <td style={tdStyle}>
                                  <input
                                    type="number"
                                    step="0.0001"
                                    min="0.0001"
                                    value={line.invoiced_quantity}
                                    onChange={(e) => handleLineChange(idx, 'invoiced_quantity', e.target.value)}
                                    style={{ ...inputStyle, padding: '6px' }}
                                    required
                                  />
                                </td>
                                <td style={tdStyle}>
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0.01"
                                    value={line.invoiced_unit_price}
                                    onChange={(e) => handleLineChange(idx, 'invoiced_unit_price', e.target.value)}
                                    style={{ ...inputStyle, padding: '6px' }}
                                    required
                                  />
                                </td>
                                <td style={tdStyle}>
                                  <div style={{ fontSize: '11px' }}>
                                    {qtyVariance !== 0 ? (
                                      <span style={{ color: '#dc2626', fontWeight: '800' }}>
                                        Qty: {qtyVariance > 0 ? `+${qtyVariance.toFixed(2)}` : qtyVariance.toFixed(2)}
                                      </span>
                                    ) : (
                                      <span style={{ color: '#059669', fontWeight: '700' }}>Qty: Match (0)</span>
                                    )}
                                  </div>
                                  <div style={{ fontSize: '11px' }}>
                                    {priceVariance !== 0 ? (
                                      <span style={{ color: priceVariance > 0 ? '#b45309' : '#059669', fontWeight: '800' }}>
                                        Price: {priceVariance > 0 ? `+${priceVariance.toFixed(2)} PPV` : `${priceVariance.toFixed(2)} Fav`}
                                      </span>
                                    ) : (
                                      <span style={{ color: '#059669', fontWeight: '700' }}>Price: Match</span>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Taxes & Freight */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div style={formGroupStyle}>
                    <label style={labelStyle}>Input VAT / Tax (ETB)</label>
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
                    <label style={labelStyle}>Freight & Shipping (ETB)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={shippingAmount}
                      onChange={(e) => setShippingAmount(e.target.value)}
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* General Ledger Accounting Reconciliation Preview */}
                <div style={{ backgroundColor: '#f0fdfa', border: '1.5px solid #99f6e4', padding: '16px 20px', borderRadius: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '11px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase' }}>
                      Double-Entry General Ledger Impact Preview:
                    </span>
                    <span style={{ fontWeight: '900', color: '#0f766e', fontSize: '16px' }}>
                      Accounts Payable: ETB {parseFloat(reconciliation.totalPayable).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', fontSize: '12px', color: '#334155', borderTop: '1px solid #ccfbf1', paddingTop: '10px' }}>
                    <div>
                      <strong style={{ color: '#0f766e' }}>DEBITS:</strong>
                      <div>• Clear GRNI (Acct 2010): ETB {reconciliation.grniClearingTotal}</div>
                      {parseFloat(reconciliation.totalPpv) > 0 && (
                        <div>• Unfavorable PPV (Acct 5040): ETB {reconciliation.totalPpv}</div>
                      )}
                      <div>• Input VAT (Acct 2200): ETB {parseFloat(taxAmount || 0).toFixed(2)}</div>
                      <div style={{ fontWeight: '800', marginTop: '4px' }}>Total Debits: ETB {reconciliation.totalDebit}</div>
                    </div>

                    <div>
                      <strong style={{ color: '#0f766e' }}>CREDITS:</strong>
                      <div>• Recognize AP (Acct 2000): ETB {reconciliation.totalPayable}</div>
                      {parseFloat(reconciliation.totalPpv) < 0 && (
                        <div>• Favorable PPV (Acct 5040): ETB {Math.abs(parseFloat(reconciliation.totalPpv)).toFixed(2)}</div>
                      )}
                      <div style={{ fontWeight: '800', marginTop: '4px' }}>Total Credits: ETB {reconciliation.totalCredit}</div>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsMatchModalOpen(false)} style={btnSecondaryStyle}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting || lineItems.length === 0}
                    style={btnPrimaryStyle}
                  >
                    {actionSubmitting ? 'Recording...' : 'Confirm 3-Way Match & Record'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Invoice Details & Final Approval */}
      <AnimatePresence>
        {isDetailModalOpen && selectedInvoice && (
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
                      Invoice #{selectedInvoice.invoice_number}
                    </h3>
                    {getStatusBadge(selectedInvoice.status)}
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Supplier: <strong>{selectedInvoice.supplier_name}</strong> | PO Ref: #{selectedInvoice.po_number}
                  </p>
                </div>
                <button onClick={() => setIsDetailModalOpen(false)} style={modalCloseBtn}><X size={18} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h4 style={{ margin: '4px 0 0', color: '#0f172a', fontSize: '13px', fontWeight: '800' }}>
                  Invoiced Line Items ({selectedInvoice.items?.length || 0})
                </h4>

                <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                  <table style={tableStyle}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr>
                        <th style={thStyle}>SKU / Description</th>
                        <th style={thStyle}>Billed Quantity</th>
                        <th style={thStyle}>Unit Price</th>
                        <th style={thStyle}>Line Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedInvoice.items || []).map((line, idx) => (
                        <tr key={idx} style={trStyle}>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>{line.item_code} — {line.item_name}</td>
                          <td style={tdStyle}>{parseFloat(line.billed_quantity).toFixed(4)} {line.item_unit}</td>
                          <td style={tdStyle}>ETB {parseFloat(line.unit_price).toFixed(2)}</td>
                          <td style={{ ...tdStyle, fontWeight: '700' }}>
                            ETB {(parseFloat(line.billed_quantity) * parseFloat(line.unit_price)).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f0fdfa', padding: '12px 18px', borderRadius: '10px' }}>
                  <span style={{ fontWeight: '700', color: '#0f766e' }}>Total Invoiced Liability (AP):</span>
                  <span style={{ fontWeight: '900', color: '#0f766e', fontSize: '16px' }}>
                    ETB {parseFloat(selectedInvoice.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', borderTop: '1px solid #f1f5f9', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setIsDetailModalOpen(false)} style={btnSecondaryStyle}>
                    Close
                  </button>

                  {selectedInvoice.status === 'matched' && (
                    <button
                      type="button"
                      disabled={actionSubmitting}
                      onClick={() => handleApproveInvoice(selectedInvoice.id)}
                      style={{ ...btnPrimaryStyle, backgroundColor: '#059669' }}
                    >
                      <CheckCircle2 size={15} /> Approve Invoice & Post General Ledger
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
