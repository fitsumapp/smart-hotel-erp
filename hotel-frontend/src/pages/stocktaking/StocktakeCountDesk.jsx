import React, { useState } from 'react';
import axios from 'axios';
import {
  Lock, Eye, ArrowLeft, Check, AlertTriangle, FileText,
  Building, Package, Save, ShieldAlert, CheckCircle2
} from 'lucide-react';
import { API_BASE_URL } from '../../apiConfig';

const API_V1 = `${API_BASE_URL}/v1`;

export default function StocktakeCountDesk({ session, onBack, onSessionUpdated, userData }) {
  const [counts, setCounts] = useState(() => {
    const initial = {};
    if (session?.items) {
      session.items.forEach(it => {
        initial[it.id] = {
          counted_quantity: it.recounted_quantity ?? it.counted_quantity ?? '',
          notes: it.notes || ''
        };
      });
    }
    return initial;
  });

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const isBlind = session.counting_mode === 'blind';
  const isRecount = session.status === 'recount_required';

  const handleCountChange = (itemId, val) => {
    setCounts(prev => ({
      ...prev,
      [itemId]: { ...prev[itemId], counted_quantity: val }
    }));
  };

  const handleNotesChange = (itemId, val) => {
    setCounts(prev => ({
      ...prev,
      [itemId]: { ...prev[itemId], notes: val }
    }));
  };

  const handleSubmitCounts = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    setSaving(true);

    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const countEntries = Object.entries(counts)
        .filter(([_, v]) => v.counted_quantity !== '' && v.counted_quantity !== null)
        .map(([id, v]) => ({
          id: parseInt(id, 10),
          [isRecount ? 'recounted_quantity' : 'counted_quantity']: parseFloat(v.counted_quantity),
          notes: v.notes || ''
        }));

      if (countEntries.length === 0) {
        setErrorMsg('Please enter at least one counted quantity before submitting.');
        setSaving(false);
        return;
      }

      const endpoint = isRecount
        ? `${API_V1}/stocktaking/sessions/${session.id}/submit-recount/`
        : `${API_V1}/stocktaking/sessions/${session.id}/record-counts/`;

      const payload = isRecount ? { recounts: countEntries } : { counts: countEntries };

      const res = await axios.post(endpoint, payload, { headers });
      setSuccessMsg(
        isRecount
          ? 'Recounted quantities submitted successfully. Session moved to Under Review.'
          : 'Physical counts recorded successfully. Mode is permanently locked (Owner Decision D-4).'
      );
      if (onSessionUpdated) {
        onSessionUpdated(res.data);
      }
    } catch (err) {
      console.error('Count submission error:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setErrorMsg(`Submission failed: ${detail}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '16px',
            fontSize: '12px',
            fontWeight: '800',
            backgroundColor: isBlind ? '#eff6ff' : '#f0fdf4',
            color: isBlind ? '#1d4ed8' : '#15803d',
            border: `1px solid ${isBlind ? '#bfdbfe' : '#bbf7d0'}`
          }}>
            {isBlind ? <Lock size={14} /> : <Eye size={14} />}
            {isBlind ? 'BLIND COUNT MODE' : 'VISIBLE COUNT MODE'}
          </span>

          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '16px',
            fontSize: '12px',
            fontWeight: '800',
            backgroundColor: isRecount ? '#fffbeb' : '#f8fafc',
            color: isRecount ? '#b45309' : '#475569',
            border: `1px solid ${isRecount ? '#fde68a' : '#e2e8f0'}`
          }}>
            Status: {session.status?.replace('_', ' ').toUpperCase()}
          </span>
        </div>
      </div>

      {/* Session Title Card */}
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
                <Building size={15} /> Location: <strong>{session.location_name} ({session.location_code})</strong>
              </span>
              {session.category_name && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Package size={15} /> Category: <strong>{session.category_name}</strong>
                </span>
              )}
            </div>
          </div>

          {session.is_mode_locked && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: '#f1f5f9',
              padding: '6px 12px',
              borderRadius: '8px',
              fontSize: '11px',
              fontWeight: '700',
              color: '#475569'
            }}>
              <Lock size={13} color="#64748b" /> Mode Locked (Decision D-4)
            </div>
          )}
        </div>

        {/* Blind mode explanation banner */}
        {isBlind && (
          <div style={{
            marginTop: '16px',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontSize: '13px',
            color: '#334155'
          }}>
            <ShieldAlert size={18} color="#0284c7" />
            <span>
              <strong>Zero-Leak Blind Count Active:</strong> Theoretical stock balances are strictly hidden from counter view to guarantee uncompromised physical verification. Count exactly what is physically on the shelf.
            </span>
          </div>
        )}

        {isRecount && (
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
            color: '#92400e'
          }}>
            <AlertTriangle size={18} color="#d97706" />
            <span>
              <strong>Recount Requested:</strong> One or more items were flagged by the supervisor due to high variance. Re-verify physical stock on highlighted items and submit recounted figures.
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

      {/* Counting Grid Form */}
      <form onSubmit={handleSubmitCounts}>
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
              Physical Inventory Items ({session.items?.length || 0})
            </span>
            <span style={{ fontSize: '12px', color: '#64748b' }}>
              Enter verified quantity physically observed in <strong>{session.location_name}</strong>
            </span>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f1f5f9', color: '#475569', fontWeight: '700' }}>
                <th style={{ padding: '12px 16px' }}>Item Code</th>
                <th style={{ padding: '12px 16px' }}>Item Description</th>
                <th style={{ padding: '12px 16px' }}>Unit</th>
                {!isBlind && <th style={{ padding: '12px 16px' }}>Expected System Stock</th>}
                {isBlind && <th style={{ padding: '12px 16px' }}>System Balance</th>}
                <th style={{ padding: '12px 16px', width: '180px' }}>
                  {isRecount ? 'Recount Quantity *' : 'Counted Quantity *'}
                </th>
                <th style={{ padding: '12px 16px' }}>Observations / Notes</th>
              </tr>
            </thead>
            <tbody>
              {session.items?.map((it, idx) => {
                const requiresRecount = it.requires_recount;
                const rowBg = requiresRecount ? '#fffbeb' : (idx % 2 === 0 ? '#ffffff' : '#f8fafc');

                return (
                  <tr key={it.id} style={{ backgroundColor: rowBg, borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px 16px', fontWeight: '700', color: '#0f172a' }}>
                      {it.item_code}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: '600', color: '#1e293b' }}>{it.item_name}</div>
                      {requiresRecount && (
                        <div style={{ fontSize: '11px', color: '#b45309', fontWeight: '700', marginTop: '3px' }}>
                          ⚠️ Supervisor flagged for recount: {it.notes}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b' }}>
                      {it.item_unit}
                    </td>

                    {/* Expected System Stock Column */}
                    {!isBlind && (
                      <td style={{ padding: '12px 16px', fontWeight: '700', color: '#334155' }}>
                        {it.theoretical_quantity !== null ? `${it.theoretical_quantity} ${it.item_unit}` : '—'}
                      </td>
                    )}

                    {/* Blind Mode Masking Column */}
                    {isBlind && (
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          color: '#64748b',
                          backgroundColor: '#f1f5f9',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: '600'
                        }}>
                          <Lock size={12} /> Hidden
                        </span>
                      </td>
                    )}

                    {/* Count input */}
                    <td style={{ padding: '12px 16px' }}>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="0.00"
                        value={counts[it.id]?.counted_quantity ?? ''}
                        onChange={(e) => handleCountChange(it.id, e.target.value)}
                        required={requiresRecount || session.status === 'draft'}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          border: `2px solid ${requiresRecount ? '#f59e0b' : '#cbd5e1'}`,
                          borderRadius: '8px',
                          fontSize: '14px',
                          fontWeight: '700',
                          outline: 'none',
                          color: '#0f172a'
                        }}
                      />
                    </td>

                    {/* Notes input */}
                    <td style={{ padding: '12px 16px' }}>
                      <input
                        type="text"
                        placeholder="Damaged, misplaced, shelf loc..."
                        value={counts[it.id]?.notes ?? ''}
                        onChange={(e) => handleNotesChange(it.id, e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          border: '1px solid #cbd5e1',
                          borderRadius: '8px',
                          fontSize: '13px',
                          outline: 'none'
                        }}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Action bar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '14px' }}>
          <button
            type="button"
            onClick={onBack}
            style={{
              padding: '12px 20px',
              backgroundColor: '#f1f5f9',
              border: '1px solid #cbd5e1',
              borderRadius: '10px',
              fontSize: '14px',
              fontWeight: '700',
              color: '#475569',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={saving || session.status === 'approved' || session.status === 'cancelled'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 24px',
              backgroundColor: '#0f766e',
              border: 'none',
              borderRadius: '10px',
              fontSize: '14px',
              fontWeight: '800',
              color: '#ffffff',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.7 : 1
            }}
          >
            {saving ? <Save size={16} className="animate-spin" /> : <Check size={16} />}
            {isRecount ? 'Submit Physical Recount' : 'Save & Submit Physical Counts'}
          </button>
        </div>
      </form>
    </div>
  );
}
