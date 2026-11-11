import React, { useState } from 'react';
import axios from 'axios';
import {
  ArrowLeft, Check, AlertTriangle, ShieldAlert,
  RotateCcw, Ban, CheckCircle2, FileText, Building
} from 'lucide-react';
import { API_BASE_URL } from '../../apiConfig';

const API_V1 = `${API_BASE_URL}/v1`;

export default function StocktakeVarianceDesk({ session, onBack, onSessionUpdated, userData }) {
  const [selectedForRecount, setSelectedForRecount] = useState({});
  const [recountReason, setRecountReason] = useState('');
  const [recountModalOpen, setRecountModalOpen] = useState(false);

  const [approvalNotes, setApprovalNotes] = useState('');
  const [emergencyOverride, setEmergencyOverride] = useState(false);
  const [emergencyJustification, setEmergencyJustification] = useState('');
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  const [processing, setProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const isCounter = Boolean(
    session.counted_by_username &&
    userData?.username &&
    session.counted_by_username.toLowerCase().trim() === userData.username.toLowerCase().trim()
  );
  const isSuperuser = Boolean(userData?.is_superuser || userData?.role === 'admin');

  // Check if session is already finalized
  const isFinalized = session.status === 'approved' || session.status === 'cancelled';

  const toggleSelectRecount = (id) => {
    setSelectedForRecount(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleRequestRecount = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);

    const itemIds = Object.keys(selectedForRecount).filter(k => selectedForRecount[k]).map(Number);
    if (itemIds.length === 0) {
      setErrorMsg('Please select at least one line item to request a physical recount.');
      return;
    }
    if (!recountReason.trim()) {
      setErrorMsg('A reason for the recount request is required.');
      return;
    }

    setProcessing(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const res = await axios.post(
        `${API_V1}/stocktaking/sessions/${session.id}/request-recount/`,
        { item_ids: itemIds, reason: recountReason.trim() },
        { headers }
      );

      setSuccessMsg(`Recount requested for ${itemIds.length} item(s). Session status updated to Recount Required.`);
      setRecountModalOpen(false);
      setSelectedForRecount({});
      setRecountReason('');
      if (onSessionUpdated) onSessionUpdated(res.data);
    } catch (err) {
      console.error('Recount request error:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setErrorMsg(`Recount request failed: ${detail}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleApproveStocktake = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);

    if (isCounter && !emergencyOverride) {
      setErrorMsg('Separation of Duties violation: Count submitters cannot approve their own stocktake.');
      return;
    }

    if (emergencyOverride && emergencyJustification.trim().length < 15) {
      setErrorMsg('Emergency superuser self-approval requires a detailed justification (minimum 15 characters).');
      return;
    }

    setProcessing(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const payload = {
        notes: approvalNotes.trim(),
        emergency_self_approval: emergencyOverride,
        justification: emergencyJustification.trim()
      };

      const res = await axios.post(
        `${API_V1}/stocktaking/sessions/${session.id}/approve/`,
        payload,
        { headers }
      );

      setSuccessMsg('Stocktake approved successfully! Stock balances updated and balanced GL Journal Entry posted.');
      setApprovalModalOpen(false);
      if (onSessionUpdated) onSessionUpdated(res.data);
    } catch (err) {
      console.error('Stocktake approval error:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setErrorMsg(`Approval failed: ${detail}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleCancelSession = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);

    if (!cancelReason.trim()) {
      setErrorMsg('Please specify a cancellation reason.');
      return;
    }

    setProcessing(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const res = await axios.post(
        `${API_V1}/stocktaking/sessions/${session.id}/cancel/`,
        { reason: cancelReason.trim() },
        { headers }
      );

      setSuccessMsg('Stocktake session cancelled. Stock balances were left untouched.');
      setCancelModalOpen(false);
      if (onSessionUpdated) onSessionUpdated(res.data);
    } catch (err) {
      console.error('Stocktake cancellation error:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setErrorMsg(`Cancellation failed: ${detail}`);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1300px', margin: '0 auto' }}>
      {/* Navigation header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: '8px',
            padding: '8px 14px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '600',
            color: '#334155'
          }}
        >
          <ArrowLeft size={16} /> Back to Sessions
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            padding: '6px 14px',
            borderRadius: '16px',
            fontSize: '12px',
            fontWeight: '800',
            backgroundColor: session.status === 'approved' ? '#f0fdf4' : (session.status === 'recount_required' ? '#fffbeb' : '#f8fafc'),
            color: session.status === 'approved' ? '#15803d' : (session.status === 'recount_required' ? '#b45309' : '#334155'),
            border: '1px solid #e2e8f0'
          }}>
            Status: {session.status?.replace('_', ' ').toUpperCase()}
          </span>

          {session.journal_entry_number && (
            <span style={{
              padding: '6px 14px',
              borderRadius: '16px',
              fontSize: '12px',
              fontWeight: '800',
              backgroundColor: '#eff6ff',
              color: '#1d4ed8',
              border: '1px solid #bfdbfe'
            }}>
              GL Journal: #{session.journal_entry_number}
            </span>
          )}
        </div>
      </div>

      {/* Session Summary Card */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        padding: '24px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 4px 12px rgba(15,23,42,0.03)',
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h1 style={{ fontSize: '20px', fontWeight: '800', color: '#0f172a', margin: '0 0 6px 0' }}>
              {session.title}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: '#64748b', fontSize: '13px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FileText size={15} /> <strong>{session.session_number}</strong>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Building size={15} /> Location: <strong>{session.location_name}</strong>
              </span>
              <span>
                Counted By: <strong>{session.counted_by_username || 'Pending'}</strong>
              </span>
              {session.reviewed_by_username && (
                <span>
                  Approved By: <strong>{session.reviewed_by_username}</strong>
                </span>
              )}
            </div>
          </div>

          {/* Metric Summary Pills */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '10px 16px',
              textAlign: 'right'
            }}>
              <div style={{ fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Theoretical Value</div>
              <div style={{ fontSize: '16px', fontWeight: '800', color: '#0f172a' }}>
                ETB {Number(session.total_theoretical_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '10px 16px',
              textAlign: 'right'
            }}>
              <div style={{ fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Counted Value</div>
              <div style={{ fontSize: '16px', fontWeight: '800', color: '#0f172a' }}>
                ETB {Number(session.total_counted_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{
              backgroundColor: Number(session.total_variance_value || 0) < 0 ? '#fef2f2' : (Number(session.total_variance_value || 0) > 0 ? '#f0fdf4' : '#f8fafc'),
              border: `1px solid ${Number(session.total_variance_value || 0) < 0 ? '#fca5a5' : (Number(session.total_variance_value || 0) > 0 ? '#bbf7d0' : '#e2e8f0')}`,
              borderRadius: '12px',
              padding: '10px 16px',
              textAlign: 'right'
            }}>
              <div style={{ fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Net Variance</div>
              <div style={{
                fontSize: '16px',
                fontWeight: '900',
                color: Number(session.total_variance_value || 0) < 0 ? '#dc2626' : (Number(session.total_variance_value || 0) > 0 ? '#16a34a' : '#475569')
              }}>
                {Number(session.total_variance_value || 0) > 0 ? '+' : ''}
                ETB {Number(session.total_variance_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>
        </div>

        {/* SoD Warning Banner if user is counter */}
        {isCounter && !isFinalized && (
          <div style={{
            marginTop: '16px',
            backgroundColor: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '10px',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontSize: '13px',
            color: '#b45309'
          }}>
            <ShieldAlert size={18} />
            <span>
              <strong>Separation of Duties Alert:</strong> You are recorded as the physical counter for this session ({session.counted_by_username}). To prevent conflict of interest, stocktake approvals must be signed off by a separate supervisor or manager.
            </span>
          </div>
        )}
      </div>

      {/* Messages */}
      {errorMsg && (
        <div style={{
          backgroundColor: '#fef2f2',
          border: '1px solid #fca5a5',
          borderRadius: '10px',
          padding: '14px 18px',
          color: '#b91c1c',
          marginBottom: '20px',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <AlertTriangle size={18} /> {errorMsg}
        </div>
      )}

      {successMsg && (
        <div style={{
          backgroundColor: '#f0fdf4',
          border: '1px solid #86efac',
          borderRadius: '10px',
          padding: '14px 18px',
          color: '#15803d',
          marginBottom: '20px',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <CheckCircle2 size={18} /> {successMsg}
        </div>
      )}

      {/* Variance Comparative Table */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
        boxShadow: '0 4px 12px rgba(15,23,42,0.03)',
        marginBottom: '24px'
      }}>
        <div style={{
          padding: '16px 20px',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ fontSize: '14px', fontWeight: '800', color: '#1e293b' }}>
            Variance Analysis & Discrepancy Breakdown ({session.items?.length || 0} items)
          </span>

          {!isFinalized && (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setRecountModalOpen(true)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  backgroundColor: '#ffffff',
                  border: '1px solid #d97706',
                  color: '#b45309',
                  borderRadius: '8px',
                  padding: '6px 14px',
                  fontSize: '12px',
                  fontWeight: '700',
                  cursor: 'pointer'
                }}
              >
                <RotateCcw size={14} /> Flag Items for Recount
              </button>
            </div>
          )}
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f1f5f9', color: '#475569', fontWeight: '700' }}>
              {!isFinalized && <th style={{ padding: '12px 14px', width: '40px' }}>Select</th>}
              <th style={{ padding: '12px 14px' }}>Item</th>
              <th style={{ padding: '12px 14px' }}>Unit Cost</th>
              <th style={{ padding: '12px 14px', textAlign: 'right' }}>Theoretical Qty</th>
              <th style={{ padding: '12px 14px', textAlign: 'right' }}>Final Count</th>
              <th style={{ padding: '12px 14px', textAlign: 'right' }}>Variance Qty</th>
              <th style={{ padding: '12px 14px', textAlign: 'right' }}>Variance Value (ETB)</th>
              <th style={{ padding: '12px 14px' }}>Status / Action</th>
            </tr>
          </thead>
          <tbody>
            {session.items?.map((it, idx) => {
              const varQty = Number(it.variance_quantity || 0);
              const varVal = Number(it.variance_value || 0);
              const isSelected = selectedForRecount[it.id];

              let varColor = '#64748b';
              let varBg = '#f8fafc';
              if (varQty > 0) {
                varColor = '#15803d';
                varBg = '#f0fdf4';
              } else if (varQty < 0) {
                varColor = '#b91c1c';
                varBg = '#fef2f2';
              }

              return (
                <tr key={it.id} style={{
                  backgroundColor: isSelected ? '#fffbeb' : (idx % 2 === 0 ? '#ffffff' : '#f8fafc'),
                  borderBottom: '1px solid #e2e8f0'
                }}>
                  {!isFinalized && (
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={Boolean(isSelected)}
                        onChange={() => toggleSelectRecount(it.id)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </td>
                  )}
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ fontWeight: '700', color: '#0f172a' }}>{it.item_name}</div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>{it.item_code} | {it.item_unit}</div>
                    {it.notes && (
                      <div style={{ fontSize: '11px', color: '#92400e', marginTop: '2px' }}>
                        Note: {it.notes}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 14px', color: '#475569' }}>
                    ETB {Number(it.unit_cost_snapshot || 0).toFixed(2)}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: '600', color: '#334155' }}>
                    {it.theoretical_quantity !== null ? Number(it.theoretical_quantity).toFixed(2) : '—'}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: '700', color: '#0f172a' }}>
                    {it.final_quantity !== null ? Number(it.final_quantity).toFixed(2) : (it.counted_quantity !== null ? Number(it.counted_quantity).toFixed(2) : '—')}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontWeight: '800',
                      backgroundColor: varBg,
                      color: varColor
                    }}>
                      {varQty > 0 ? '+' : ''}{varQty.toFixed(2)} {it.item_unit}
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: '800', color: varColor }}>
                    {varVal > 0 ? '+' : ''}ETB {varVal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {it.requires_recount ? (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '3px 8px',
                        borderRadius: '6px',
                        backgroundColor: '#fffbeb',
                        color: '#b45309',
                        fontSize: '11px',
                        fontWeight: '700'
                      }}>
                        <RotateCcw size={12} /> Recount Pending
                      </span>
                    ) : (
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        backgroundColor: '#f1f5f9',
                        color: '#475569',
                        fontSize: '11px',
                        fontWeight: '600'
                      }}>
                        {varQty === 0 ? 'Exact Match' : (varQty > 0 ? 'Surplus' : 'Deficit / Shrinkage')}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Action Footer Bar */}
      {!isFinalized && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          padding: '18px 24px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 4px 12px rgba(15,23,42,0.03)'
        }}>
          <div>
            <button
              type="button"
              onClick={() => setCancelModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#ffffff',
                border: '1px solid #ef4444',
                color: '#dc2626',
                borderRadius: '8px',
                padding: '10px 18px',
                fontSize: '13px',
                fontWeight: '700',
                cursor: 'pointer'
              }}
            >
              <Ban size={15} /> Cancel Session
            </button>
          </div>

          <div style={{ display: 'flex', gap: '14px' }}>
            <button
              type="button"
              onClick={() => setApprovalModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#0f766e',
                border: 'none',
                color: '#ffffff',
                borderRadius: '10px',
                padding: '12px 24px',
                fontSize: '14px',
                fontWeight: '800',
                cursor: 'pointer'
              }}
            >
              <Check size={16} /> Review & Approve Stocktake
            </button>
          </div>
        </div>
      )}

      {/* MODAL 1: Request Recount Dialog */}
      {recountModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15,23,42,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '500px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 12px 0', color: '#0f172a' }}>
              Request Physical Recount
            </h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
              Flag selected items for physical recount by warehouse staff. Please provide clear instructions.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                Recount Reason & Instructions *
              </label>
              <textarea
                rows={3}
                placeholder="e.g., Variance exceeds 10% tolerance; check upper shelf B3..."
                value={recountReason}
                onChange={(e) => setRecountReason(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setRecountModalOpen(false)}
                style={{
                  padding: '10px 16px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#f8fafc',
                  fontSize: '13px',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={processing}
                onClick={handleRequestRecount}
                style={{
                  padding: '10px 18px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: '#d97706',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: processing ? 'not-allowed' : 'pointer'
                }}
              >
                {processing ? 'Submitting...' : 'Confirm Recount Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Approve Stocktake Dialog with SoD & GL Preview */}
      {approvalModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15,23,42,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '28px',
            maxWidth: '560px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 12px 0', color: '#0f172a' }}>
              Approve Stocktake & Post General Ledger
            </h3>

            {/* General Ledger Preview Box */}
            <div style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px',
              marginBottom: '16px',
              fontSize: '12px'
            }}>
              <div style={{ fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>
                Automated Double-Entry GL Impact:
              </div>
              <ul style={{ margin: 0, paddingLeft: '18px', color: '#475569', lineHeight: '1.6' }}>
                <li>Surplus items post: <code>Dr 1300 (Inventory Asset) / Cr 5020 (Variance Expense)</code></li>
                <li>Deficit items post: <code>Dr 5020 (Variance Expense) / Cr 1300 (Inventory Asset)</code></li>
                <li>Actual physical counts will become authoritative current stock in location.</li>
              </ul>
            </div>

            {/* Separation of Duties Warning */}
            {isCounter && (
              <div style={{
                backgroundColor: '#fef2f2',
                border: '1px solid #fca5a5',
                borderRadius: '10px',
                padding: '14px',
                marginBottom: '16px',
                fontSize: '12px',
                color: '#991b1b'
              }}>
                <div style={{ fontWeight: '800', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <ShieldAlert size={16} /> Separation of Duties Restriction
                </div>
                You are registered as the counter for this session ({session.counted_by_username}). A different supervisor or administrator must approve this stocktake.
                {isSuperuser && (
                  <div style={{ marginTop: '8px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: '700' }}>
                      <input
                        type="checkbox"
                        checked={emergencyOverride}
                        onChange={(e) => setEmergencyOverride(e.target.checked)}
                      />
                      Enable Superuser Emergency Self-Approval (Audit Logged)
                    </label>
                  </div>
                )}
              </div>
            )}

            {/* Emergency Justification Input if activated */}
            {emergencyOverride && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#b91c1c' }}>
                  Emergency Self-Approval Justification (Min 15 chars) *
                </label>
                <textarea
                  rows={2}
                  placeholder="Detailed justification for emergency self-approval..."
                  value={emergencyJustification}
                  onChange={(e) => setEmergencyJustification(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #fca5a5',
                    fontSize: '12px'
                  }}
                />
              </div>
            )}

            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                Supervisor Approval Notes (Optional)
              </label>
              <textarea
                rows={2}
                placeholder="Physical counts and variances verified on-site..."
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '12px'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setApprovalModalOpen(false)}
                style={{
                  padding: '10px 16px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#f8fafc',
                  fontSize: '13px',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={processing || (isCounter && !emergencyOverride)}
                onClick={handleApproveStocktake}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: '#0f766e',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: '800',
                  cursor: (processing || (isCounter && !emergencyOverride)) ? 'not-allowed' : 'pointer',
                  opacity: (isCounter && !emergencyOverride) ? 0.6 : 1
                }}
              >
                {processing ? 'Posting GL...' : 'Authorize & Post GL'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Cancel Session Dialog */}
      {cancelModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15,23,42,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '480px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 12px 0', color: '#b91c1c' }}>
              Cancel Stocktake Session
            </h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
              Cancelling will release the session without making any changes to inventory stock balances or the general ledger.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                Cancellation Reason *
              </label>
              <textarea
                rows={2}
                placeholder="e.g., Session started in error, warehouse restructuring..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '12px'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setCancelModalOpen(false)}
                style={{
                  padding: '10px 16px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#f8fafc',
                  fontSize: '13px',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                Keep Session
              </button>
              <button
                type="button"
                disabled={processing}
                onClick={handleCancelSession}
                style={{
                  padding: '10px 18px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: '#ef4444',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: processing ? 'not-allowed' : 'pointer'
                }}
              >
                {processing ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
