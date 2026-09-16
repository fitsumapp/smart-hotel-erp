import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../apiConfig';
import {
  TrendingUp, DollarSign, ShoppingBag, Bed, ReceiptText,
  ArrowDownCircle, Wallet, AlertCircle, Loader2, RefreshCw, Calendar,
  ChevronDown, ChevronUp, CheckCircle2, ArrowUpRight, ArrowDownRight,
  LayoutList, BarChart3, Clock, BookOpen, FileText, PieChart,
  Landmark, PlusCircle, Trash2, X, Save, Receipt,
  Scale, TrendingDown, Banknote, ShieldCheck,
  Users, UserCheck, Briefcase, CreditCard, Edit2, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const fmt = (n, digits = 2) =>
  Number(n || 0).toLocaleString('en-ET', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

const fmtDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
};

const fmtDateTime = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
};

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('access_token')}`
});

const ACCOUNT_TYPE_COLOR = {
  asset: '#3b82f6',
  liability: '#ef4444',
  equity: '#8b5cf6',
  revenue: '#10b981',
  expense: '#f59e0b',
};

const ACCOUNT_TYPE_BG = {
  asset: 'rgba(59,130,246,0.08)',
  liability: 'rgba(239,68,68,0.08)',
  equity: 'rgba(139,92,246,0.08)',
  revenue: 'rgba(16,185,129,0.08)',
  expense: 'rgba(245,158,11,0.08)',
};

// ─────────────────────────────────────────────────────────────────────────────
// Shared UI Components
// ─────────────────────────────────────────────────────────────────────────────

const KpiCard = ({ label, value, icon, color, sub, trend }) => {
  const isUp = trend >= 0;
  return (
    <motion.div whileHover={{ y: -4 }} style={styles.kpiCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ textAlign: 'left' }}>
          <p style={styles.kpiLabel}>{label}</p>
          <h2 style={{ ...styles.kpiValue, color }}>{value}</h2>
          {sub && <p style={styles.kpiSub}>{sub}</p>}
        </div>
        <div style={{ ...styles.kpiIcon, backgroundColor: `${color}18`, color }}>{icon}</div>
      </div>
      {trend !== undefined && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '12px' }}>
          {isUp ? <ArrowUpRight size={14} color="#10b981" /> : <ArrowDownRight size={14} color="#ef4444" />}
          <span style={{ fontSize: '11px', fontWeight: '700', color: isUp ? '#10b981' : '#ef4444' }}>
            {Math.abs(trend).toFixed(1)}%
          </span>
          <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '600' }}>vs prev period</span>
        </div>
      )}
    </motion.div>
  );
};

const BarChart = ({ data }) => {
  if (!data || data.length === 0) return (
    <div style={styles.emptyChart}>
      <BarChart3 size={28} color="#cbd5e1" /><span style={styles.emptyText}>No trend data</span>
    </div>
  );
  const max = Math.max(...data.map(d => Math.max(d.revenue || 0, d.expense || 0)), 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '130px', paddingTop: '10px' }}>
      {data.map((d, i) => {
        const revPct = Math.max(((d.revenue || 0) / max) * 100, 1);
        const expPct = Math.max(((d.expense || 0) / max) * 100, 1);
        return (
          <div key={i} title={`${d.date}\nRevenue: ETB ${fmt(d.revenue)}\nExpense: ETB ${fmt(d.expense)}`}
            style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: '1px', height: '100%', justifyContent: 'center' }}>
            <motion.div
              initial={{ height: 0 }} animate={{ height: `${revPct}%` }}
              transition={{ delay: i * 0.03, duration: 0.5 }}
              style={{ width: '45%', background: 'linear-gradient(180deg,#0d9488,rgba(13,148,136,0.2))', borderRadius: '3px 3px 0 0', minHeight: '3px' }}
            />
            <motion.div
              initial={{ height: 0 }} animate={{ height: `${expPct}%` }}
              transition={{ delay: i * 0.03 + 0.1, duration: 0.5 }}
              style={{ width: '45%', background: 'linear-gradient(180deg,#ef4444,rgba(239,68,68,0.2))', borderRadius: '3px 3px 0 0', minHeight: '3px' }}
            />
          </div>
        );
      })}
    </div>
  );
};

const EmptyState = ({ icon, text }) => (
  <div style={styles.emptyChart}>
    {icon || <FileText size={28} color="#cbd5e1" />}
    <span style={styles.emptyText}>{text || 'No data available'}</span>
  </div>
);

const Modal = ({ open, onClose, title, children, width = '560px' }) => {
  if (!open) return null;
  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        style={{ ...styles.modal, maxWidth: width }}
        onClick={e => e.stopPropagation()}
      >
        <div style={styles.modalHeader}>
          <h3 style={styles.modalTitle}>{title}</h3>
          <button onClick={onClose} style={styles.modalClose}><X size={18} /></button>
        </div>
        <div style={styles.modalBody}>{children}</div>
      </motion.div>
    </div>
  );
};

const FormRow = ({ label, children }) => (
  <div style={{ marginBottom: '16px', textAlign: 'left' }}>
    <label style={styles.formLabel}>{label}</label>
    {children}
  </div>
);

const Input = ({ style, ...props }) => (
  <input style={{ ...styles.formInput, ...style }} {...props} />
);
const Select = ({ style, children, ...props }) => (
  <select style={{ ...styles.formInput, ...style }} {...props}>{children}</select>
);

const Spinner = () => (
  <div style={styles.spinnerWrap}>
    <Loader2 size={34} style={{ animation: 'spin 1s linear infinite', color: '#0d9488' }} />
    <span style={{ color: '#64748b', fontWeight: '600', fontSize: '13px', marginTop: '10px' }}>Loading…</span>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// TAB 1: Overview
// ─────────────────────────────────────────────────────────────────────────────
const PRESETS = [
  { label: 'Today', start: today(), end: today() },
  { label: '7 Days', start: daysAgo(7), end: today() },
  { label: '30 Days', start: daysAgo(30), end: today() },
  { label: 'This Month', start: (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`; })(), end: today() },
];

const OverviewTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState(daysAgo(30));
  const [endDate, setEndDate] = useState(today());
  const [activeSubTab, setActiveSubTab] = useState('ledger');

  const fetchData = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await axios.get(`${API_BASE_URL}/users/finance/stats/`, {
        headers: authHeaders(),
        params: { start_date: startDate, end_date: endDate }
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load finance data.');
    } finally { setLoading(false); }
  }, [startDate, endDate]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const metrics = data?.metrics || {};
  const chartTrend = data?.chart_trend || [];
  const ledger = data?.ledger || [];
  const closedDays = data?.closed_days || [];
  const totalRev = Number(metrics.total_revenue || 0);
  const roomPct = totalRev ? (Number(metrics.room_revenue || 0) / totalRev) * 100 : 0;
  const fbPct = totalRev ? (Number(metrics.fb_revenue || 0) / totalRev) * 100 : 0;
  const folioPct = totalRev ? (Number(metrics.folio_revenue || 0) / totalRev) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Date filter bar */}
      <div style={styles.filterBar}>
        <Calendar size={15} color="#64748b" />
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {PRESETS.map(p => (
            <button key={p.label} onClick={() => { setStartDate(p.start); setEndDate(p.end); }}
              style={{ ...styles.presetBtn, ...(startDate === p.start && endDate === p.end ? styles.presetBtnActive : {}) }}>
              {p.label}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto', flexWrap: 'wrap' }}>
          <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={{ padding: '6px 10px', fontSize: '12px' }} />
          <span style={{ color: '#94a3b8' }}>→</span>
          <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={{ padding: '6px 10px', fontSize: '12px' }} />
          <button onClick={fetchData} disabled={loading} style={styles.refreshBtn}>
            <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={16} color="#ef4444" /><span>{error}</span></div>}
      {loading ? <Spinner /> : (
        <AnimatePresence>
          {/* KPI Grid */}
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
            <div style={styles.kpiGrid}>
              <KpiCard label="Total Revenue" value={`ETB ${fmt(metrics.total_revenue)}`} icon={<DollarSign size={20} />} color="#0d9488" sub={`${startDate} → ${endDate}`} />
              <KpiCard label="Room Revenue" value={`ETB ${fmt(metrics.room_revenue)}`} icon={<Bed size={20} />} color="#3b82f6" sub={`${roomPct.toFixed(1)}% of total`} />
              <KpiCard label="F&B Revenue" value={`ETB ${fmt(metrics.fb_revenue)}`} icon={<ShoppingBag size={20} />} color="#8b5cf6" sub={`${fbPct.toFixed(1)}% of total`} />
              <KpiCard label="Extra Charges" value={`ETB ${fmt(metrics.folio_revenue)}`} icon={<ReceiptText size={20} />} color="#f59e0b" sub={`${folioPct.toFixed(1)}% of total`} />
              <KpiCard label="Total Expenses" value={`ETB ${fmt(metrics.total_expenses)}`} icon={<ArrowDownCircle size={20} />} color="#ef4444" />
              <KpiCard label="Net Profit" value={`ETB ${fmt(metrics.net_profit)}`} icon={<TrendingUp size={20} />}
                color={Number(metrics.net_profit) >= 0 ? '#10b981' : '#ef4444'}
                sub={Number(metrics.net_profit) >= 0 ? '✓ Profitable period' : '⚠ Loss period'} />
              <KpiCard label="Accounts Receivable" value={`ETB ${fmt(metrics.total_receivables)}`} icon={<Wallet size={20} />} color="#64748b" sub="Unpaid / outstanding" />
            </div>
          </motion.div>

          {/* Revenue Composition */}
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} style={styles.card}>
            <h3 style={styles.sectionTitle}>Revenue Composition</h3>
            <div style={styles.compositionBar}>
              {roomPct > 0 && <div style={{ ...styles.compSegment, width: `${roomPct}%`, backgroundColor: '#3b82f6' }} />}
              {fbPct > 0 && <div style={{ ...styles.compSegment, width: `${fbPct}%`, backgroundColor: '#8b5cf6' }} />}
              {folioPct > 0 && <div style={{ ...styles.compSegment, width: `${folioPct}%`, backgroundColor: '#f59e0b' }} />}
            </div>
            <div style={{ display: 'flex', gap: '18px', marginTop: '12px', flexWrap: 'wrap' }}>
              {[{ label: 'Rooms', pct: roomPct, color: '#3b82f6', val: metrics.room_revenue },
                { label: 'F&B', pct: fbPct, color: '#8b5cf6', val: metrics.fb_revenue },
                { label: 'Extra Charges', pct: folioPct, color: '#f59e0b', val: metrics.folio_revenue }
              ].map(seg => (
                <div key={seg.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '3px', backgroundColor: seg.color }} />
                  <span style={{ fontSize: '12px', color: '#475569', fontWeight: '600' }}>
                    {seg.label} — {seg.pct.toFixed(1)}% (ETB {fmt(seg.val)})
                  </span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Trend Chart */}
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.10 }} style={styles.card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={styles.sectionTitle}>Daily Revenue vs Expense Trend</h3>
              <div style={{ display: 'flex', gap: '14px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', fontWeight: '700', color: '#0d9488' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#0d9488' }} /> Revenue
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', fontWeight: '700', color: '#ef4444' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#ef4444' }} /> Expense
                </span>
              </div>
            </div>
            <BarChart data={chartTrend} />
          </motion.div>

          {/* Sub-tabs */}
          <div style={styles.tabBar}>
            {[{ id: 'ledger', label: 'Transaction Ledger', icon: <LayoutList size={14} /> },
              { id: 'audits', label: 'Day Audits (Z-Reports)', icon: <CheckCircle2 size={14} /> }
            ].map(tab => (
              <button key={tab.id} onClick={() => setActiveSubTab(tab.id)}
                style={{ ...styles.tabBtn, ...(activeSubTab === tab.id ? styles.tabBtnActive : {}) }}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {activeSubTab === 'ledger' && (
            <motion.div key="ledger" initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={styles.card}>
              <h3 style={{ ...styles.sectionTitle, marginBottom: '16px' }}>Transaction Ledger ({ledger.length})</h3>
              {ledger.length === 0 ? <EmptyState text="No transactions in this period" /> : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '480px', overflowY: 'auto' }}>
                  {ledger.map(entry => {
                    const isIn = entry.flow === 'in';
                    return (
                      <motion.div key={entry.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={styles.ledgerRow}>
                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, backgroundColor: isIn ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)' }}>
                          {isIn ? <ArrowUpRight size={14} color="#10b981" /> : <ArrowDownRight size={14} color="#ef4444" />}
                        </div>
                        <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                          <p style={styles.ledgerDesc}>{entry.description}</p>
                          <span style={styles.ledgerType}>{entry.type}</span>
                          <span style={{ ...styles.ledgerType, marginLeft: '8px', color: '#94a3b8' }}>{fmtDateTime(entry.date)}</span>
                        </div>
                        <span style={{ fontWeight: '800', fontSize: '14px', flexShrink: 0, color: isIn ? '#10b981' : '#ef4444' }}>
                          {isIn ? '+' : '-'} ETB {fmt(entry.amount)}
                        </span>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          )}

          {activeSubTab === 'audits' && (
            <motion.div key="audits" initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={styles.card}>
              <h3 style={{ ...styles.sectionTitle, marginBottom: '16px' }}>Day Audits — Z-Reports ({closedDays.length})</h3>
              {closedDays.length === 0 ? <EmptyState icon={<CheckCircle2 size={28} color="#cbd5e1" />} text="No audit records in this period" /> : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={styles.auditHeader}><span>Date</span><span>Status</span><span>Revenue</span><span>Cash</span><span>Telebirr</span><span>Closed By</span></div>
                  {closedDays.map((a, i) => (
                    <div key={i} style={styles.auditRow}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {a.is_closed ? <CheckCircle2 size={14} color="#10b981" /> : <Clock size={14} color="#f59e0b" />}
                        <span style={{ fontWeight: '700', fontSize: '12px' }}>{fmtDate(a.date)}</span>
                      </div>
                      <span style={{ ...styles.badge, backgroundColor: a.is_closed ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)', color: a.is_closed ? '#059669' : '#d97706' }}>
                        {a.is_closed ? 'Closed' : 'Open'}
                      </span>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: '#0f172a' }}>ETB {fmt(a.revenue)}</span>
                      <span style={{ fontSize: '12px', color: '#334155' }}>ETB {fmt(a.cash)}</span>
                      <span style={{ fontSize: '12px', color: '#334155' }}>ETB {fmt(a.telebirr)}</span>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>{a.closed_by || '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 2: Chart of Accounts (COA)
// ─────────────────────────────────────────────────────────────────────────────
const ChartOfAccountsTab = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ code: '', name: '', account_type: 'asset' });
  const [saving, setSaving] = useState(false);
  const [filterType, setFilterType] = useState('all');

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/users/finance/accounts/`, { headers: authHeaders() });
      setAccounts(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load chart of accounts.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  const handleCreate = async () => {
    setSaving(true);
    try {
      await axios.post(`${API_BASE_URL}/users/finance/accounts/`, form, { headers: authHeaders() });
      setShowModal(false);
      setForm({ code: '', name: '', account_type: 'asset' });
      fetchAccounts();
    } catch (err) {
      alert(err.response?.data?.detail || JSON.stringify(err.response?.data) || 'Failed to create account.');
    } finally { setSaving(false); }
  };

  const grouped = ['asset', 'liability', 'equity', 'revenue', 'expense'].reduce((acc, type) => {
    const filtered = accounts.filter(a => (filterType === 'all' ? true : a.account_type === filterType) && a.account_type === type);
    if (filtered.length > 0) acc[type] = filtered;
    return acc;
  }, {});

  const typeLabels = { asset: 'Assets', liability: 'Liabilities', equity: 'Equity', revenue: 'Revenue', expense: 'Expenses' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={styles.sectionTitle}>Chart of Accounts</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>
            General Ledger account structure — {accounts.length} accounts
          </p>
        </div>
        <button onClick={() => setShowModal(true)} style={styles.primaryBtn}>
          <PlusCircle size={15} /> New Account
        </button>
      </div>

      {/* Type filter */}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {['all', 'asset', 'liability', 'equity', 'revenue', 'expense'].map(t => (
          <button key={t} onClick={() => setFilterType(t)}
            style={{ ...styles.filterChip, ...(filterType === t ? { backgroundColor: ACCOUNT_TYPE_COLOR[t] || '#0d9488', color: '#fff', border: 'none' } : {}) }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : (
        Object.entries(grouped).length === 0 ? <EmptyState text="No accounts found" /> :
        Object.entries(grouped).map(([type, accts]) => (
          <motion.div key={type} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: ACCOUNT_TYPE_COLOR[type] }} />
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f172a' }}>{typeLabels[type]}</h4>
              <span style={{ ...styles.badge, backgroundColor: ACCOUNT_TYPE_BG[type], color: ACCOUNT_TYPE_COLOR[type] }}>{accts.length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 140px', gap: '8px', padding: '6px 12px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8' }}>
                <span>Code</span><span>Account Name</span><span style={{ textAlign: 'right' }}>Balance (ETB)</span>
              </div>
              {accts.map(acct => (
                <div key={acct.id} style={{ display: 'grid', gridTemplateColumns: '100px 1fr 140px', gap: '8px', padding: '10px 12px', borderRadius: '10px', backgroundColor: ACCOUNT_TYPE_BG[acct.account_type], alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: '800', color: ACCOUNT_TYPE_COLOR[acct.account_type], fontFamily: 'monospace' }}>{acct.code}</span>
                  <span style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b' }}>{acct.name}</span>
                  <span style={{ fontSize: '13px', fontWeight: '800', color: '#0f172a', textAlign: 'right' }}>
                    {fmt(acct.current_balance)}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        ))
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Create New GL Account">
        <FormRow label="Account Code *">
          <Input placeholder="e.g. 5400" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} />
        </FormRow>
        <FormRow label="Account Name *">
          <Input placeholder="e.g. Marketing Expense" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        </FormRow>
        <FormRow label="Account Type *">
          <Select value={form.account_type} onChange={e => setForm(f => ({ ...f, account_type: e.target.value }))}>
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
            <option value="equity">Equity</option>
            <option value="revenue">Revenue</option>
            <option value="expense">Expense</option>
          </Select>
        </FormRow>
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button onClick={() => setShowModal(false)} style={styles.secondaryBtn}>Cancel</button>
          <button onClick={handleCreate} disabled={saving || !form.code || !form.name} style={styles.primaryBtn}>
            {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Create Account'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 3: Journal Entries
// ─────────────────────────────────────────────────────────────────────────────
const JournalEntriesTab = () => {
  const [entries, setEntries] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    description: '',
    date: today(),
    items: [
      { account_code: '', debit: '', credit: '' },
      { account_code: '', debit: '', credit: '' },
    ]
  });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [jRes, aRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/users/finance/journal-entries/`, { headers: authHeaders() }),
        axios.get(`${API_BASE_URL}/users/finance/accounts/`, { headers: authHeaders() }),
      ]);
      setEntries(jRes.data);
      setAccounts(aRes.data);
    } catch (err) {
      setError('Failed to load journal entries.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const updateItem = (idx, field, val) => {
    setForm(f => ({ ...f, items: f.items.map((it, i) => i === idx ? { ...it, [field]: val } : it) }));
  };

  const addLine = () => setForm(f => ({ ...f, items: [...f.items, { account_code: '', debit: '', credit: '' }] }));
  const removeLine = (idx) => setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));

  const totalDebit = form.items.reduce((s, it) => s + (parseFloat(it.debit) || 0), 0);
  const totalCredit = form.items.reduce((s, it) => s + (parseFloat(it.credit) || 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01 && totalDebit > 0;

  const handlePost = async () => {
    if (!isBalanced) return alert('Journal entry is not balanced! Total Debits must equal Total Credits.');
    setSaving(true);
    try {
      await axios.post(`${API_BASE_URL}/users/finance/journal-entries/`, {
        description: form.description,
        date: form.date,
        items: form.items.map(it => ({
          account_code: it.account_code,
          debit: parseFloat(it.debit) || 0,
          credit: parseFloat(it.credit) || 0,
        }))
      }, { headers: authHeaders() });
      setShowModal(false);
      setForm({ description: '', date: today(), items: [{ account_code: '', debit: '', credit: '' }, { account_code: '', debit: '', credit: '' }] });
      fetchAll();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to post journal entry.');
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={styles.sectionTitle}>Journal Entries</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>
            Double-entry general ledger — {entries.length} entries
          </p>
        </div>
        <button onClick={() => setShowModal(true)} style={styles.primaryBtn}>
          <PlusCircle size={15} /> Post Journal Entry
        </button>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : (
        entries.length === 0 ? <EmptyState icon={<BookOpen size={28} color="#cbd5e1" />} text="No journal entries posted yet" /> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {entries.map(entry => (
              <motion.div key={entry.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} style={styles.card}>
                <div
                  onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                >
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '12px', fontFamily: 'monospace', fontWeight: '800', color: '#0d9488', backgroundColor: 'rgba(13,148,136,0.08)', padding: '2px 8px', borderRadius: '6px' }}>{entry.entry_number}</span>
                      <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '600' }}>{fmtDate(entry.date)}</span>
                    </div>
                    <p style={{ margin: '4px 0 0', fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>{entry.description || 'No description'}</p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ ...styles.badge, backgroundColor: 'rgba(16,185,129,0.1)', color: '#059669', fontWeight: '800', fontSize: '12px' }}>
                      ETB {fmt(entry.items?.reduce((s, it) => s + parseFloat(it.amount_debit || 0), 0))}
                    </span>
                    {expanded === entry.id ? <ChevronUp size={16} color="#94a3b8" /> : <ChevronDown size={16} color="#94a3b8" />}
                  </div>
                </div>

                <AnimatePresence>
                  {expanded === entry.id && entry.items && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}
                      style={{ overflow: 'hidden', marginTop: '14px', borderTop: '1px solid rgba(148,163,184,0.14)', paddingTop: '14px' }}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr 130px 130px', gap: '6px', padding: '6px 10px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8' }}>
                        <span>Account</span><span>Name</span><span style={{ textAlign: 'right' }}>Debit</span><span style={{ textAlign: 'right' }}>Credit</span>
                      </div>
                      {entry.items.map((it, idx) => (
                        <div key={idx} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 130px 130px', gap: '6px', padding: '8px 10px', borderRadius: '8px', backgroundColor: '#f8fafc', marginBottom: '3px', alignItems: 'center' }}>
                          <span style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: '700', color: '#0d9488' }}>{it.account?.code || '—'}</span>
                          <span style={{ fontSize: '12px', fontWeight: '600', color: '#334155' }}>{it.account?.name || '—'}</span>
                          <span style={{ fontSize: '12px', fontWeight: '800', color: parseFloat(it.amount_debit) > 0 ? '#0f172a' : '#cbd5e1', textAlign: 'right' }}>
                            {parseFloat(it.amount_debit) > 0 ? fmt(it.amount_debit) : '—'}
                          </span>
                          <span style={{ fontSize: '12px', fontWeight: '800', color: parseFloat(it.amount_credit) > 0 ? '#0f172a' : '#cbd5e1', textAlign: 'right' }}>
                            {parseFloat(it.amount_credit) > 0 ? fmt(it.amount_credit) : '—'}
                          </span>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        )
      )}

      {/* Post JV Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="Post Manual Journal Entry" width="680px">
        <FormRow label="Description"><Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="e.g. Salary expense for June" /></FormRow>
        <FormRow label="Date"><Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} /></FormRow>

        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <label style={styles.formLabel}>Journal Lines</label>
            <button onClick={addLine} style={{ ...styles.filterChip, fontSize: '11px', padding: '4px 10px' }}>+ Add Line</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 110px 110px 32px', gap: '6px', marginBottom: '6px', padding: '0 4px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8' }}>
            <span>Account</span><span style={{ textAlign: 'center' }}>Debit</span><span style={{ textAlign: 'center' }}>Credit</span><span />
          </div>
          {form.items.map((it, idx) => (
            <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 110px 110px 32px', gap: '6px', marginBottom: '6px', alignItems: 'center' }}>
              <Select value={it.account_code} onChange={e => updateItem(idx, 'account_code', e.target.value)} style={{ fontSize: '12px', padding: '8px' }}>
                <option value="">— Select Account —</option>
                {accounts.map(a => <option key={a.id} value={a.code}>{a.code} — {a.name}</option>)}
              </Select>
              <Input type="number" placeholder="0.00" value={it.debit} onChange={e => updateItem(idx, 'debit', e.target.value)} style={{ fontSize: '12px', padding: '8px', textAlign: 'right' }} />
              <Input type="number" placeholder="0.00" value={it.credit} onChange={e => updateItem(idx, 'credit', e.target.value)} style={{ fontSize: '12px', padding: '8px', textAlign: 'right' }} />
              <button onClick={() => form.items.length > 2 && removeLine(idx)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#ef4444', opacity: form.items.length <= 2 ? 0.3 : 1 }}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {/* Totals */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 110px 110px 32px', gap: '6px', marginTop: '8px', padding: '10px', borderRadius: '8px', backgroundColor: isBalanced ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)', border: `1px solid ${isBalanced ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
            <span style={{ fontSize: '11px', fontWeight: '800', color: '#475569', textAlign: 'right' }}>Totals</span>
            <span style={{ fontSize: '12px', fontWeight: '800', textAlign: 'right', color: '#0f172a' }}>{fmt(totalDebit)}</span>
            <span style={{ fontSize: '12px', fontWeight: '800', textAlign: 'right', color: '#0f172a' }}>{fmt(totalCredit)}</span>
            <span />
          </div>
          {!isBalanced && totalDebit > 0 && (
            <p style={{ fontSize: '11px', color: '#ef4444', fontWeight: '600', margin: '6px 0 0', textAlign: 'right' }}>
              ⚠ Difference: ETB {fmt(Math.abs(totalDebit - totalCredit))} — Entry must be balanced!
            </p>
          )}
          {isBalanced && (
            <p style={{ fontSize: '11px', color: '#059669', fontWeight: '700', margin: '6px 0 0', textAlign: 'right' }}>
              ✓ Balanced — Ready to post
            </p>
          )}
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button onClick={() => setShowModal(false)} style={styles.secondaryBtn}>Cancel</button>
          <button onClick={handlePost} disabled={saving || !isBalanced} style={{ ...styles.primaryBtn, opacity: !isBalanced ? 0.5 : 1 }}>
            {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle2 size={14} />}
            {saving ? 'Posting…' : 'Post Entry'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 4: Expense Manager
// ─────────────────────────────────────────────────────────────────────────────
const ExpensesTab = () => {
  const [expenses, setExpenses] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    description: '', amount: '', date: today(),
    expense_account: '', payment_account: '',
    supplier: '', reference_number: ''
  });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [eRes, aRes, sRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/users/finance/expenses/`, { headers: authHeaders() }),
        axios.get(`${API_BASE_URL}/users/finance/accounts/`, { headers: authHeaders() }),
        axios.get(`${API_BASE_URL}/users/suppliers/`, { headers: authHeaders() }),
      ]);
      setExpenses(eRes.data);
      setAccounts(aRes.data);
      setSuppliers(sRes.data);
    } catch (err) {
      setError('Failed to load expenses.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const expenseAccounts = accounts.filter(a => a.account_type === 'expense');
  const paymentAccounts = accounts.filter(a => ['asset', 'liability'].includes(a.account_type));

  const handleCreate = async () => {
    if (!form.description || !form.amount || !form.expense_account || !form.payment_account) {
      return alert('Please fill all required fields.');
    }
    setSaving(true);
    try {
      await axios.post(`${API_BASE_URL}/users/finance/expenses/`, {
        ...form,
        amount: parseFloat(form.amount),
        supplier: form.supplier || null,
      }, { headers: authHeaders() });
      setShowModal(false);
      setForm({ description: '', amount: '', date: today(), expense_account: '', payment_account: '', supplier: '', reference_number: '' });
      fetchAll();
    } catch (err) {
      alert(err.response?.data?.error || JSON.stringify(err.response?.data) || 'Failed to log expense.');
    } finally { setSaving(false); }
  };

  const totalExpenses = expenses.reduce((s, e) => s + parseFloat(e.amount || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={styles.sectionTitle}>Expense Manager</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>
            {expenses.length} records — Total: ETB {fmt(totalExpenses)}
          </p>
        </div>
        <button onClick={() => setShowModal(true)} style={styles.primaryBtn}>
          <PlusCircle size={15} /> Log Expense
        </button>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : (
        expenses.length === 0 ? <EmptyState icon={<Receipt size={28} color="#cbd5e1" />} text="No expenses logged yet" /> : (
          <div style={styles.card}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 160px 140px 120px', gap: '8px', padding: '8px 12px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px' }}>
              <span>Date</span><span>Description</span><span>Account</span><span>Paid Via</span><span style={{ textAlign: 'right' }}>Amount</span>
            </div>
            {expenses.map(exp => (
              <motion.div key={exp.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ display: 'grid', gridTemplateColumns: '120px 1fr 160px 140px 120px', gap: '8px', padding: '11px 12px', borderRadius: '10px', backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.1)', marginBottom: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', fontWeight: '700', color: '#64748b' }}>{fmtDate(exp.date)}</span>
                <div>
                  <p style={{ margin: 0, fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>{exp.description}</p>
                  {exp.reference_number && <p style={{ margin: 0, fontSize: '10px', color: '#94a3b8', fontWeight: '600' }}>Ref: {exp.reference_number}</p>}
                  {exp.supplier_name && <p style={{ margin: 0, fontSize: '10px', color: '#94a3b8', fontWeight: '600' }}>Supplier: {exp.supplier_name}</p>}
                </div>
                <span style={{ fontSize: '11px', fontWeight: '600', color: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.08)', padding: '3px 8px', borderRadius: '6px' }}>
                  {exp.expense_account_name || '—'}
                </span>
                <span style={{ fontSize: '11px', fontWeight: '600', color: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.08)', padding: '3px 8px', borderRadius: '6px' }}>
                  {exp.payment_account_name || '—'}
                </span>
                <span style={{ fontSize: '14px', fontWeight: '800', color: '#ef4444', textAlign: 'right' }}>
                  ETB {fmt(exp.amount)}
                </span>
              </motion.div>
            ))}
          </div>
        )
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Log New Expense" width="560px">
        <FormRow label="Description *"><Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="e.g. Monthly electricity bill" /></FormRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <FormRow label="Amount (ETB) *"><Input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} placeholder="0.00" /></FormRow>
          <FormRow label="Date *"><Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} /></FormRow>
        </div>
        <FormRow label="Expense Account (Category) *">
          <Select value={form.expense_account} onChange={e => setForm(f => ({ ...f, expense_account: e.target.value }))}>
            <option value="">— Select Expense Account —</option>
            {expenseAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </Select>
        </FormRow>
        <FormRow label="Payment Account (Paid From) *">
          <Select value={form.payment_account} onChange={e => setForm(f => ({ ...f, payment_account: e.target.value }))}>
            <option value="">— Select Payment Account —</option>
            {paymentAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </Select>
        </FormRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <FormRow label="Supplier (optional)">
            <Select value={form.supplier} onChange={e => setForm(f => ({ ...f, supplier: e.target.value }))}>
              <option value="">— No Supplier —</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </FormRow>
          <FormRow label="Reference / Invoice No.">
            <Input value={form.reference_number} onChange={e => setForm(f => ({ ...f, reference_number: e.target.value }))} placeholder="INV-001" />
          </FormRow>
        </div>
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '4px' }}>
          <button onClick={() => setShowModal(false)} style={styles.secondaryBtn}>Cancel</button>
          <button onClick={handleCreate} disabled={saving} style={styles.primaryBtn}>
            {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Log Expense'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 5: Budgeting
// ─────────────────────────────────────────────────────────────────────────────
const BudgetingTab = () => {
  const [budgets, setBudgets] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const curDate = new Date();
  const [form, setForm] = useState({ account: '', amount: '', year: curDate.getFullYear(), month: curDate.getMonth() + 1 });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [bRes, aRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/users/finance/budgets/`, { headers: authHeaders() }),
        axios.get(`${API_BASE_URL}/users/finance/accounts/`, { headers: authHeaders() }),
      ]);
      setBudgets(bRes.data);
      setAccounts(aRes.data);
    } catch (err) { setError('Failed to load budgets.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleSave = async () => {
    if (!form.account || !form.amount) return alert('Please fill all required fields.');
    setSaving(true);
    try {
      await axios.post(`${API_BASE_URL}/users/finance/budgets/`, {
        account: form.account,
        amount: parseFloat(form.amount),
        year: form.year,
        month: form.month,
      }, { headers: authHeaders() });
      setShowModal(false);
      setForm({ account: '', amount: '', year: curDate.getFullYear(), month: curDate.getMonth() + 1 });
      fetchAll();
    } catch (err) { alert(err.response?.data?.error || 'Failed to save budget.'); }
    finally { setSaving(false); }
  };

  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={styles.sectionTitle}>Budget Planning</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>
            Set monthly budget targets per GL account — {budgets.length} budgets set
          </p>
        </div>
        <button onClick={() => setShowModal(true)} style={styles.primaryBtn}>
          <PlusCircle size={15} /> Set Budget
        </button>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : (
        budgets.length === 0 ? <EmptyState icon={<TrendingDown size={28} color="#cbd5e1" />} text="No budgets set yet. Start by setting monthly targets." /> : (
          <div style={styles.card}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 180px', gap: '8px', padding: '8px 12px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px' }}>
              <span>Account</span><span style={{ textAlign: 'center' }}>Month</span><span style={{ textAlign: 'center' }}>Year</span><span style={{ textAlign: 'right' }}>Budget Amount (ETB)</span>
            </div>
            {budgets.map(b => (
              <motion.div key={b.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 180px', gap: '8px', padding: '11px 12px', borderRadius: '10px', backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.1)', marginBottom: '4px', alignItems: 'center' }}>
                <div>
                  <span style={{ fontSize: '12px', fontFamily: 'monospace', fontWeight: '700', color: '#0d9488' }}>{b.account_code} </span>
                  <span style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>{b.account_name}</span>
                </div>
                <span style={{ fontSize: '13px', fontWeight: '700', color: '#475569', textAlign: 'center' }}>{MONTHS[b.month - 1]}</span>
                <span style={{ fontSize: '13px', fontWeight: '700', color: '#475569', textAlign: 'center' }}>{b.year}</span>
                <div style={{ textAlign: 'right' }}>
                  {/* Progress bar vs actual account balance */}
                  <span style={{ fontSize: '14px', fontWeight: '800', color: '#8b5cf6' }}>ETB {fmt(b.amount)}</span>
                </div>
              </motion.div>
            ))}
          </div>
        )
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Set Monthly Budget">
        <FormRow label="GL Account *">
          <Select value={form.account} onChange={e => setForm(f => ({ ...f, account: e.target.value }))}>
            <option value="">— Select Account —</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name} ({a.account_type})</option>)}
          </Select>
        </FormRow>
        <FormRow label="Budget Amount (ETB) *"><Input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} placeholder="0.00" /></FormRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <FormRow label="Month">
            <Select value={form.month} onChange={e => setForm(f => ({ ...f, month: parseInt(e.target.value) }))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </Select>
          </FormRow>
          <FormRow label="Year"><Input type="number" value={form.year} onChange={e => setForm(f => ({ ...f, year: parseInt(e.target.value) }))} /></FormRow>
        </div>
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button onClick={() => setShowModal(false)} style={styles.secondaryBtn}>Cancel</button>
          <button onClick={handleSave} disabled={saving} style={styles.primaryBtn}>
            {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Save Budget'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 6: Financial Statements
// ─────────────────────────────────────────────────────────────────────────────
const FinancialStatementsTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState('pl'); // 'pl' | 'bs'

  useEffect(() => {
    setLoading(true);
    axios.get(`${API_BASE_URL}/users/finance/statements/`, { headers: authHeaders() })
      .then(res => { setData(res.data); setLoading(false); })
      .catch(err => { setError('Failed to load financial statements.'); setLoading(false); });
  }, []);

  const is = data?.income_statement;
  const bs = data?.balance_sheet;

  const StatTable = ({ title, rows, total, totalLabel, positive = true, color }) => (
    <div style={{ marginBottom: '24px' }}>
      <h4 style={{ margin: '0 0 10px', fontSize: '13px', fontWeight: '800', color: color || '#1e293b', textTransform: 'uppercase', letterSpacing: '0.4px' }}>{title}</h4>
      {rows?.map(r => (
        <div key={r.code} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', marginBottom: '3px', backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.08)' }}>
          <div>
            <span style={{ fontSize: '11px', fontFamily: 'monospace', fontWeight: '700', color: '#94a3b8' }}>{r.code} </span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>{r.name}</span>
          </div>
          <span style={{ fontSize: '13px', fontWeight: '800', color: r.balance < 0 ? '#ef4444' : '#0f172a' }}>
            ETB {fmt(Math.abs(r.balance))}
          </span>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 12px', borderRadius: '10px', backgroundColor: color ? `${color}12` : '#e0f2fe', marginTop: '6px', borderLeft: `3px solid ${color || '#3b82f6'}` }}>
        <span style={{ fontSize: '13px', fontWeight: '800', color: '#0f172a' }}>{totalLabel}</span>
        <span style={{ fontSize: '15px', fontWeight: '900', color: color || '#3b82f6' }}>ETB {fmt(Math.abs(total))}</span>
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={styles.sectionTitle}>Financial Statements</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>Real-time balance sheet & income statement from General Ledger</p>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button onClick={() => setView('pl')} style={{ ...styles.filterChip, ...(view === 'pl' ? { backgroundColor: '#0d9488', color: '#fff', border: 'none' } : {}) }}>P&L Statement</button>
          <button onClick={() => setView('bs')} style={{ ...styles.filterChip, ...(view === 'bs' ? { backgroundColor: '#3b82f6', color: '#fff', border: 'none' } : {}) }}>Balance Sheet</button>
        </div>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : (
        <motion.div key={view} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={styles.card}>
          {view === 'pl' && is && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px', padding: '14px 16px', borderRadius: '12px', background: is.net_income >= 0 ? 'linear-gradient(135deg, rgba(16,185,129,0.08), rgba(13,148,136,0.08))' : 'linear-gradient(135deg, rgba(239,68,68,0.08), rgba(239,68,68,0.04))', border: `1px solid ${is.net_income >= 0 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: is.net_income >= 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)' }}>
                  {is.net_income >= 0 ? <TrendingUp size={20} color="#10b981" /> : <TrendingDown size={20} color="#ef4444" />}
                </div>
                <div style={{ textAlign: 'left' }}>
                  <p style={{ margin: 0, fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase' }}>Net Income</p>
                  <p style={{ margin: 0, fontSize: '22px', fontWeight: '900', color: is.net_income >= 0 ? '#10b981' : '#ef4444' }}>ETB {fmt(is.net_income)}</p>
                </div>
              </div>
              <StatTable title="Revenue" rows={is.revenue} total={is.total_revenue} totalLabel="Total Revenue" color="#10b981" />
              <StatTable title="Expenses" rows={is.expenses} total={is.total_expenses} totalLabel="Total Expenses" color="#ef4444" />
            </>
          )}
          {view === 'bs' && bs && (
            <>
              <div style={{ display: 'flex', gap: '20px', marginBottom: '20px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Total Assets', val: bs.total_assets, color: '#3b82f6' },
                  { label: 'Total Liabilities', val: bs.total_liabilities, color: '#ef4444' },
                  { label: 'Total Equity', val: bs.total_equity, color: '#8b5cf6' },
                ].map(item => (
                  <div key={item.label} style={{ flex: 1, minWidth: '140px', padding: '14px 18px', borderRadius: '12px', backgroundColor: `${item.color}10`, border: `1px solid ${item.color}25`, textAlign: 'left' }}>
                    <p style={{ margin: '0 0 4px', fontSize: '11px', fontWeight: '700', color: item.color, textTransform: 'uppercase' }}>{item.label}</p>
                    <p style={{ margin: 0, fontSize: '18px', fontWeight: '900', color: item.color }}>ETB {fmt(item.val)}</p>
                  </div>
                ))}
              </div>
              <StatTable title="Assets" rows={bs.assets} total={bs.total_assets} totalLabel="Total Assets" color="#3b82f6" />
              <StatTable title="Liabilities" rows={bs.liabilities} total={bs.total_liabilities} totalLabel="Total Liabilities" color="#ef4444" />
              <StatTable title="Equity" rows={bs.equity} total={bs.total_equity} totalLabel="Total Equity" color="#8b5cf6" />
              <div style={{ padding: '12px 16px', borderRadius: '12px', backgroundColor: Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)) < 1 ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)', border: `1px solid ${Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)) < 1 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`, display: 'flex', alignItems: 'center', gap: '10px', marginTop: '10px' }}>
                <Scale size={16} color={Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)) < 1 ? '#10b981' : '#ef4444'} />
                <span style={{ fontSize: '12px', fontWeight: '700', color: Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)) < 1 ? '#059669' : '#ef4444' }}>
                  {Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)) < 1 ? '✓ Balance Sheet is balanced (Assets = Liabilities + Equity)' : `⚠ Imbalance detected: ETB ${fmt(Math.abs(bs.total_assets - (bs.total_liabilities + bs.total_equity)))}`}
                </span>
              </div>
            </>
          )}
        </motion.div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 7: Tax Report
// ─────────────────────────────────────────────────────────────────────────────
const TaxReportTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState((() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`; })());
  const [endDate, setEndDate] = useState(today());

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/users/finance/tax-report/`, {
        headers: authHeaders(),
        params: { start_date: startDate, end_date: endDate }
      });
      setData(res.data);
    } catch (err) { setError('Failed to load tax report.'); }
    finally { setLoading(false); }
  }, [startDate, endDate]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={styles.sectionTitle}>VAT & Tax Report</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>Tax collected by period for filing</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={{ padding: '7px 10px', fontSize: '12px' }} />
          <span style={{ color: '#94a3b8' }}>→</span>
          <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={{ padding: '7px 10px', fontSize: '12px' }} />
          <button onClick={fetchData} disabled={loading} style={styles.refreshBtn}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Generate
          </button>
        </div>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}
      {loading ? <Spinner /> : data && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          {/* Summary KPIs */}
          <div style={styles.kpiGrid}>
            <KpiCard label="Total VAT Collected" value={`ETB ${fmt(data.aggregated?.vat_collected)}`} icon={<ShieldCheck size={20} />} color="#ef4444" sub="VAT 15%" />
            <KpiCard label="Service Charge" value={`ETB ${fmt(data.aggregated?.service_charge_collected)}`} icon={<Banknote size={20} />} color="#f59e0b" sub="Collected this period" />
            <KpiCard label="Total Tax Collected" value={`ETB ${fmt(data.aggregated?.total_tax_collected)}`} icon={<Scale size={20} />} color="#8b5cf6" sub="VAT + Service Charge" />
          </div>

          {/* Breakdown cards */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '4px' }}>
            <div style={{ flex: 1, padding: '20px', borderRadius: '16px', backgroundColor: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.15)', minWidth: '220px', textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(139,92,246,0.12)' }}>
                  <ShoppingBag size={18} color="#8b5cf6" />
                </div>
                <h4 style={{ margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f172a' }}>F&B (Restaurant & Bar)</h4>
              </div>
              {[{ label: 'Subtotal', val: data.restaurant?.subtotal },
                { label: 'VAT', val: data.restaurant?.vat },
                { label: 'Service Charge', val: data.restaurant?.service_charge },
                { label: 'Total Collected', val: data.restaurant?.total, main: true }
              ].map(row => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: '#64748b' }}>{row.label}</span>
                  <span style={{ fontSize: row.main ? '14px' : '12px', fontWeight: row.main ? '900' : '700', color: row.main ? '#8b5cf6' : '#1e293b' }}>ETB {fmt(row.val)}</span>
                </div>
              ))}
            </div>

            <div style={{ flex: 1, padding: '20px', borderRadius: '16px', backgroundColor: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)', minWidth: '220px', textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(59,130,246,0.12)' }}>
                  <Bed size={18} color="#3b82f6" />
                </div>
                <h4 style={{ margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f172a' }}>Room Revenue</h4>
              </div>
              {[{ label: 'Subtotal', val: data.rooms?.subtotal },
                { label: 'VAT', val: data.rooms?.vat },
                { label: 'Service Charge', val: data.rooms?.service_charge },
                { label: 'Total Revenue', val: data.rooms?.total, main: true }
              ].map(row => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: '#64748b' }}>{row.label}</span>
                  <span style={{ fontSize: row.main ? '14px' : '12px', fontWeight: row.main ? '900' : '700', color: row.main ? '#3b82f6' : '#1e293b' }}>ETB {fmt(row.val)}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: '14px 18px', borderRadius: '12px', backgroundColor: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
            <ShieldCheck size={18} color="#10b981" />
            <span style={{ fontSize: '12px', fontWeight: '700', color: '#059669' }}>
              Period: {fmtDate(data.start_date)} → {fmtDate(data.end_date)} &nbsp;|&nbsp;
              Total tax liability: ETB {fmt(data.aggregated?.total_tax_collected)} — Submit to tax authority.
            </span>
          </div>
        </motion.div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TAB 8: Payroll Management
// ─────────────────────────────────────────────────────────────────────────────

const DEPT_COLORS = {
  reception: '#3b82f6', kitchen: '#f59e0b', bar: '#8b5cf6',
  housekeeping: '#10b981', maintenance: '#64748b', accounts: '#0d9488',
  management: '#ef4444', security: '#f97316', waiter: '#ec4899', other: '#94a3b8',
};

const PAYROLL_STATUSES = {
  draft:    { label: 'Draft',    bg: 'rgba(100,116,139,0.12)', color: '#475569' },
  approved: { label: 'Approved', bg: 'rgba(59,130,246,0.12)',  color: '#2563eb' },
  paid:     { label: 'Paid',     bg: 'rgba(16,185,129,0.12)', color: '#059669' },
};

const DEPARTMENTS = [
  { value: 'reception',    label: 'Reception / Front Office' },
  { value: 'kitchen',      label: 'Kitchen' },
  { value: 'bar',          label: 'Bar' },
  { value: 'housekeeping', label: 'Housekeeping' },
  { value: 'maintenance',  label: 'Maintenance' },
  { value: 'accounts',     label: 'Accounts & Finance' },
  { value: 'management',   label: 'Management' },
  { value: 'security',     label: 'Security' },
  { value: 'waiter',       label: 'Waiter / Service Staff' },
  { value: 'other',        label: 'Other' },
];

const emptyPayroll = () => ({
  employee_name: '', employee_id: '', department: 'other', position: '',
  pay_period_start: daysAgo(30), pay_period_end: today(),
  payment_date: today(),
  basic_salary: '', overtime_pay: '0', bonus: '0', allowances: '0',
  income_tax: '0', pension_employee: '0', pension_employer: '0', other_deductions: '0',
  status: 'draft', notes: '',
});

const calcPayroll = (f) => {
  const n = (v) => parseFloat(v) || 0;
  const gross = n(f.basic_salary) + n(f.overtime_pay) + n(f.bonus) + n(f.allowances);
  const deductions = n(f.income_tax) + n(f.pension_employee) + n(f.other_deductions);
  return { gross, net: gross - deductions };
};

const PayrollTab = () => {
  const nowDate  = new Date();
  const [year,  setYear]  = useState(nowDate.getFullYear());
  const [month, setMonth] = useState(nowDate.getMonth() + 1);
  const [summary, setSummary] = useState(null);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const [filterDept, setFilterDept] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [search, setSearch] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [editEntry, setEditEntry] = useState(null);
  const [form, setForm] = useState(emptyPayroll());
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = { year, month };
      if (filterDept)   params.department = filterDept;
      if (filterStatus) params.status     = filterStatus;

      const [sumRes, listRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/users/finance/payroll-summary/`, { headers: authHeaders(), params: { year, month } }),
        axios.get(`${API_BASE_URL}/users/finance/payroll/`,         { headers: authHeaders(), params }),
      ]);
      setSummary(sumRes.data);
      setEntries(listRes.data?.results || listRes.data || []);
    } catch (e) { setError('Failed to load payroll data.'); }
    finally { setLoading(false); }
  }, [year, month, filterDept, filterStatus]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const prevMonth = () => { if (month === 1) { setMonth(12); setYear(y => y - 1); } else setMonth(m => m - 1); };
  const nextMonth = () => { if (month === 12) { setMonth(1); setYear(y => y + 1); } else setMonth(m => m + 1); };
  const monthName = new Date(year, month - 1).toLocaleString('en-GB', { month: 'long', year: 'numeric' });

  const openAdd  = () => { setEditEntry(null); setForm(emptyPayroll()); setSaveErr(null); setShowModal(true); };
  const openEdit = (e) => {
    setEditEntry(e);
    setForm({
      employee_name: e.employee_name, employee_id: e.employee_id || '',
      department: e.department, position: e.position || '',
      pay_period_start: e.pay_period_start, pay_period_end: e.pay_period_end,
      payment_date: e.payment_date || today(),
      basic_salary: e.basic_salary, overtime_pay: e.overtime_pay,
      bonus: e.bonus, allowances: e.allowances,
      income_tax: e.income_tax, pension_employee: e.pension_employee,
      pension_employer: e.pension_employer, other_deductions: e.other_deductions,
      status: e.status, notes: e.notes || '',
    });
    setSaveErr(null);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.employee_name.trim()) { setSaveErr('Employee name is required.'); return; }
    if (!form.basic_salary)         { setSaveErr('Basic salary is required.'); return; }
    setSaving(true); setSaveErr(null);
    try {
      if (editEntry) {
        await axios.put(`${API_BASE_URL}/users/finance/payroll/${editEntry.id}/`, form, { headers: authHeaders() });
      } else {
        await axios.post(`${API_BASE_URL}/users/finance/payroll/`, form, { headers: authHeaders() });
      }
      setShowModal(false);
      fetchAll();
    } catch (e) {
      setSaveErr(e.response?.data ? JSON.stringify(e.response.data) : 'Save failed.');
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this payroll entry?')) return;
    try {
      await axios.delete(`${API_BASE_URL}/users/finance/payroll/${id}/`, { headers: authHeaders() });
      fetchAll();
    } catch { alert('Delete failed.'); }
  };

  const { gross: liveGross, net: liveNet } = calcPayroll(form);
  const s = summary?.summary || {};

  const filtered = entries.filter(e =>
    !search || e.employee_name.toLowerCase().includes(search.toLowerCase()) ||
    (e.employee_id || '').toLowerCase().includes(search.toLowerCase())
  );

  const InputField = ({ label, name, type = 'text', ...rest }) => (
    <div>
      <label style={styles.formLabel}>{label}</label>
      <input
        type={type} value={form[name] ?? ''} style={styles.formInput}
        onChange={e => setForm(f => ({ ...f, [name]: e.target.value }))} {...rest}
      />
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={styles.sectionTitle}>Payroll Management</h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', fontWeight: '500' }}>
            Staff salaries, deductions & GL auto-posting
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button onClick={prevMonth} style={{ ...styles.secondaryBtn, padding: '8px 10px' }}><ChevronLeft size={14} /></button>
          <span style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a', minWidth: '130px', textAlign: 'center' }}>{monthName}</span>
          <button onClick={nextMonth} style={{ ...styles.secondaryBtn, padding: '8px 10px' }}><ChevronRight size={14} /></button>
          <button onClick={fetchAll} style={styles.refreshBtn}><RefreshCw size={13} /></button>
          <button onClick={openAdd} style={styles.primaryBtn}><PlusCircle size={14} /> Add Entry</button>
        </div>
      </div>

      {error && <div style={styles.errorBox}><AlertCircle size={15} color="#ef4444" />{error}</div>}

      {/* KPI Cards */}
      {loading ? <Spinner /> : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div style={styles.kpiGrid}>
            <KpiCard label="Headcount" value={s.headcount || 0} icon={<Users size={20} />} color="#3b82f6" sub={`${monthName}`} />
            <KpiCard label="Total Gross Pay" value={`ETB ${fmt(s.total_gross)}`} icon={<Briefcase size={20} />} color="#0d9488" sub="Incl. overtime & bonus" />
            <KpiCard label="Total Net Pay" value={`ETB ${fmt(s.total_net)}`} icon={<CreditCard size={20} />} color="#10b981" sub="After all deductions" />
            <KpiCard label="Income Tax (PAYE)" value={`ETB ${fmt(s.total_tax)}`} icon={<ShieldCheck size={20} />} color="#ef4444" sub="Withheld for tax auth." />
            <KpiCard label="Pension (Employee)" value={`ETB ${fmt(s.total_pension_employee)}`} icon={<UserCheck size={20} />} color="#8b5cf6" sub="7% employee contrib." />
            <KpiCard label="Pension (Employer)" value={`ETB ${fmt(s.total_pension_employer)}`} icon={<Wallet size={20} />} color="#f59e0b" sub="11% employer contrib." />
          </div>

          {/* Department Breakdown */}
          {summary?.by_department?.length > 0 && (
            <div style={{ ...styles.card, marginTop: '4px' }}>
              <h4 style={{ ...styles.sectionTitle, marginBottom: '16px' }}>Payroll by Department</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(() => {
                  const maxGross = Math.max(...(summary.by_department.map(d => d.total_gross)), 1);
                  return summary.by_department.map(d => (
                    <div key={d.code} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: '#475569', width: '160px', flexShrink: 0 }}>{d.department}</span>
                      <div style={{ flex: 1, height: '10px', backgroundColor: '#f1f5f9', borderRadius: '99px', overflow: 'hidden' }}>
                        <motion.div
                          initial={{ width: 0 }} animate={{ width: `${(d.total_gross / maxGross) * 100}%` }}
                          transition={{ duration: 0.7, ease: 'easeOut' }}
                          style={{ height: '100%', borderRadius: '99px', backgroundColor: DEPT_COLORS[d.code] || '#94a3b8' }}
                        />
                      </div>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: '#1e293b', width: '90px', textAlign: 'right', flexShrink: 0 }}>
                        ETB {fmt(d.total_gross)}
                      </span>
                      <span style={{ fontSize: '10px', color: '#94a3b8', width: '60px', textAlign: 'right', flexShrink: 0 }}>
                        {d.headcount} staff
                      </span>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {/* Filter Bar */}
          <div style={{ ...styles.filterBar, marginTop: '4px' }}>
            <input
              type="text" placeholder="Search employee name / ID…"
              value={search} onChange={e => setSearch(e.target.value)}
              style={{ ...styles.formInput, flex: 1, minWidth: '160px', padding: '7px 12px', fontSize: '12px' }}
            />
            <select value={filterDept} onChange={e => setFilterDept(e.target.value)} style={{ ...styles.formInput, width: '180px', padding: '7px 12px', fontSize: '12px' }}>
              <option value="">All Departments</option>
              {DEPARTMENTS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ ...styles.formInput, width: '130px', padding: '7px 12px', fontSize: '12px' }}>
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="approved">Approved</option>
              <option value="paid">Paid</option>
            </select>
          </div>

          {/* Payroll List */}
          <div style={{ ...styles.card, padding: '0', overflow: 'hidden' }}>
            {/* Table Header */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.9fr 0.7fr 1fr 1fr 0.8fr 0.8fr', gap: '8px', padding: '10px 16px', fontSize: '9px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
              <span>Employee</span><span>Department</span><span>Period</span>
              <span style={{ textAlign: 'right' }}>Gross</span>
              <span style={{ textAlign: 'right' }}>Net Pay</span>
              <span style={{ textAlign: 'center' }}>Status</span>
              <span style={{ textAlign: 'right' }}>Actions</span>
            </div>

            {filtered.length === 0 ? (
              <div style={styles.emptyChart}><Users size={28} color="#cbd5e1" /><span style={styles.emptyText}>No payroll entries for this period</span></div>
            ) : filtered.map((e, i) => {
              const st = PAYROLL_STATUSES[e.status] || PAYROLL_STATUSES.draft;
              const deptColor = DEPT_COLORS[e.department] || '#94a3b8';
              return (
                <motion.div
                  key={e.id}
                  initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                  style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.9fr 0.7fr 1fr 1fr 0.8fr 0.8fr', gap: '8px', padding: '12px 16px', alignItems: 'center', borderBottom: '1px solid rgba(148,163,184,0.07)', backgroundColor: i % 2 === 0 ? '#fff' : '#fafbfc' }}
                >
                  <div>
                    <p style={{ margin: 0, fontSize: '12px', fontWeight: '700', color: '#0f172a' }}>{e.employee_name}</p>
                    <p style={{ margin: '2px 0 0', fontSize: '10px', color: '#94a3b8', fontWeight: '500' }}>{e.employee_id || '—'} · {e.position || '—'}</p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <div style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: deptColor, flexShrink: 0 }} />
                    <span style={{ fontSize: '11px', color: '#475569', fontWeight: '600' }}>
                      {DEPARTMENTS.find(d => d.value === e.department)?.label?.split('/')[0] || e.department}
                    </span>
                  </div>
                  <div>
                    <p style={{ margin: 0, fontSize: '10px', color: '#64748b', fontWeight: '600' }}>
                      {fmtDate(e.pay_period_start)}
                    </p>
                    <p style={{ margin: '2px 0 0', fontSize: '10px', color: '#94a3b8' }}>
                      → {fmtDate(e.pay_period_end)}
                    </p>
                  </div>
                  <p style={{ margin: 0, fontSize: '12px', fontWeight: '700', color: '#1e293b', textAlign: 'right' }}>ETB {fmt(e.gross_pay)}</p>
                  <p style={{ margin: 0, fontSize: '13px', fontWeight: '800', color: '#059669', textAlign: 'right' }}>ETB {fmt(e.net_pay)}</p>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <span style={{ ...styles.badge, backgroundColor: st.bg, color: st.color }}>{st.label}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '5px' }}>
                    <button onClick={() => openEdit(e)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#3b82f6' }} title="Edit">
                      <Edit2 size={13} />
                    </button>
                    {e.status === 'draft' && (
                      <button onClick={() => handleDelete(e.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#ef4444' }} title="Delete">
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Add / Edit Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={styles.modalOverlay}>
            <motion.div initial={{ scale: 0.93, y: 30 }} animate={{ scale: 1, y: 0 }} style={{ ...styles.modal, maxWidth: '680px', maxHeight: '92vh', overflowY: 'auto' }}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>{editEntry ? 'Edit Payroll Entry' : 'New Payroll Entry'}</h3>
                <button onClick={() => setShowModal(false)} style={styles.modalClose}><X size={18} /></button>
              </div>
              <div style={{ ...styles.modalBody, display: 'flex', flexDirection: 'column', gap: '16px' }}>

                {/* Employee Info */}
                <div style={{ padding: '12px 16px', borderRadius: '12px', backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.15)' }}>
                  <p style={{ margin: '0 0 12px', fontSize: '10px', fontWeight: '800', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#64748b' }}>Employee Information</p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <InputField label="Employee Name *" name="employee_name" placeholder="e.g. Alem Girma" />
                    <InputField label="Employee ID" name="employee_id" placeholder="e.g. EMP-001" />
                    <div>
                      <label style={styles.formLabel}>Department *</label>
                      <select value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))} style={styles.formInput}>
                        {DEPARTMENTS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                      </select>
                    </div>
                    <InputField label="Position / Job Title" name="position" placeholder="e.g. Senior Chef" />
                  </div>
                </div>

                {/* Pay Period */}
                <div style={{ padding: '12px 16px', borderRadius: '12px', backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.15)' }}>
                  <p style={{ margin: '0 0 12px', fontSize: '10px', fontWeight: '800', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#64748b' }}>Pay Period</p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                    <InputField label="Period Start" name="pay_period_start" type="date" />
                    <InputField label="Period End" name="pay_period_end" type="date" />
                    <InputField label="Payment Date" name="payment_date" type="date" />
                  </div>
                </div>

                {/* Earnings */}
                <div style={{ padding: '12px 16px', borderRadius: '12px', backgroundColor: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.15)' }}>
                  <p style={{ margin: '0 0 12px', fontSize: '10px', fontWeight: '800', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#059669' }}>Earnings (ETB)</p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px' }}>
                    <InputField label="Basic Salary *" name="basic_salary" type="number" min="0" placeholder="0.00" />
                    <InputField label="Overtime Pay" name="overtime_pay" type="number" min="0" placeholder="0.00" />
                    <InputField label="Bonus" name="bonus" type="number" min="0" placeholder="0.00" />
                    <InputField label="Allowances" name="allowances" type="number" min="0" placeholder="0.00" />
                  </div>
                </div>

                {/* Deductions */}
                <div style={{ padding: '12px 16px', borderRadius: '12px', backgroundColor: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.15)' }}>
                  <p style={{ margin: '0 0 12px', fontSize: '10px', fontWeight: '800', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#dc2626' }}>Deductions (ETB)</p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px' }}>
                    <InputField label="Income Tax (PAYE)" name="income_tax" type="number" min="0" placeholder="0.00" />
                    <InputField label="Pension (Employee 7%)" name="pension_employee" type="number" min="0" placeholder="0.00" />
                    <InputField label="Pension (Employer 11%)" name="pension_employer" type="number" min="0" placeholder="0.00" />
                    <InputField label="Other Deductions" name="other_deductions" type="number" min="0" placeholder="0.00" />
                  </div>
                </div>

                {/* Live Gross / Net Preview */}
                <div style={{ display: 'flex', gap: '12px' }}>
                  <div style={{ flex: 1, padding: '14px', borderRadius: '12px', backgroundColor: 'rgba(13,148,136,0.06)', border: '1px solid rgba(13,148,136,0.2)', textAlign: 'center' }}>
                    <p style={{ margin: '0 0 4px', fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Gross Pay</p>
                    <p style={{ margin: 0, fontSize: '20px', fontWeight: '800', color: '#0d9488' }}>ETB {fmt(liveGross)}</p>
                  </div>
                  <div style={{ flex: 1, padding: '14px', borderRadius: '12px', backgroundColor: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', textAlign: 'center' }}>
                    <p style={{ margin: '0 0 4px', fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Net Pay</p>
                    <p style={{ margin: 0, fontSize: '20px', fontWeight: '800', color: '#059669' }}>ETB {fmt(liveNet)}</p>
                  </div>
                </div>

                {/* Status & Notes */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
                  <div>
                    <label style={styles.formLabel}>Status</label>
                    <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} style={styles.formInput}>
                      <option value="draft">Draft</option>
                      <option value="approved">Approved</option>
                      <option value="paid">Paid (Posts GL Entry)</option>
                    </select>
                  </div>
                  <div>
                    <label style={styles.formLabel}>Notes</label>
                    <input type="text" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} style={styles.formInput} placeholder="Optional notes…" />
                  </div>
                </div>

                {saveErr && <div style={styles.errorBox}><AlertCircle size={14} color="#ef4444" />{saveErr}</div>}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', paddingTop: '4px' }}>
                  <button onClick={() => setShowModal(false)} style={styles.secondaryBtn}><X size={14} /> Cancel</button>
                  <button onClick={handleSave} disabled={saving} style={styles.primaryBtn}>
                    {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
                    {editEntry ? 'Update' : 'Save Entry'}
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main FinanceDashboard
// ─────────────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'overview',    label: 'Overview',         icon: <BarChart3 size={15} /> },
  { id: 'coa',        label: 'Chart of Accounts', icon: <Landmark size={15} /> },
  { id: 'journal',    label: 'Journal Entries',   icon: <BookOpen size={15} /> },
  { id: 'expenses',   label: 'Expenses',          icon: <Receipt size={15} /> },
  { id: 'budgets',    label: 'Budgeting',         icon: <PieChart size={15} /> },
  { id: 'statements', label: 'Fin. Statements',   icon: <FileText size={15} /> },
  { id: 'tax',        label: 'Tax Report',        icon: <ShieldCheck size={15} /> },
  { id: 'payroll',    label: 'Payroll',           icon: <Users size={15} /> },
];

const FinanceDashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div style={styles.page} id="finance-dashboard-root">
      {/* Header */}
      <div style={styles.pageHeader}>
        <div style={{ textAlign: 'left' }}>
          <h1 style={styles.pageTitle}>Finance & Accounts</h1>
          <p style={styles.pageSub}>Double-entry general ledger • All amounts in ETB</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ padding: '6px 12px', borderRadius: '20px', backgroundColor: 'rgba(16,185,129,0.1)', fontSize: '11px', fontWeight: '700', color: '#059669' }}>
            ● Live System
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={styles.mainTabBar}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            id={`finance-tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{ ...styles.mainTabBtn, ...(activeTab === tab.id ? styles.mainTabBtnActive : {}) }}
          >
            {tab.icon}
            <span style={{ whiteSpace: 'nowrap' }}>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          {activeTab === 'overview'    && <OverviewTab />}
          {activeTab === 'coa'         && <ChartOfAccountsTab />}
          {activeTab === 'journal'     && <JournalEntriesTab />}
          {activeTab === 'expenses'    && <ExpensesTab />}
          {activeTab === 'budgets'     && <BudgetingTab />}
          {activeTab === 'statements'  && <FinancialStatementsTab />}
          {activeTab === 'tax'         && <TaxReportTab />}
          {activeTab === 'payroll'     && <PayrollTab />}
        </motion.div>
      </AnimatePresence>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        #finance-dashboard-root * { box-sizing: border-box; }
        #finance-dashboard-root button:hover { filter: brightness(0.94); }
        #finance-dashboard-root input:focus, #finance-dashboard-root select:focus, #finance-dashboard-root textarea:focus {
          outline: 2px solid rgba(13,148,136,0.4); outline-offset: 1px;
        }
      `}</style>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const styles = {
  page: { display: 'flex', flexDirection: 'column', gap: '20px', fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif" },
  pageHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' },
  pageTitle: { fontSize: '26px', fontWeight: '800', margin: '0 0 4px', letterSpacing: '-0.5px', color: '#0f172a' },
  pageSub: { margin: 0, fontSize: '12px', color: '#64748b', fontWeight: '500' },
  mainTabBar: {
    display: 'flex', gap: '2px', flexWrap: 'wrap',
    backgroundColor: '#f1f5f9', borderRadius: '14px', padding: '4px',
  },
  mainTabBtn: {
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '8px 14px', border: 'none', borderRadius: '10px',
    backgroundColor: 'transparent', color: '#64748b',
    fontWeight: '600', fontSize: '12px', cursor: 'pointer', transition: 'all 0.2s',
    fontFamily: 'inherit',
  },
  mainTabBtnActive: {
    backgroundColor: '#fff', color: '#0d9488',
    boxShadow: '0 1px 6px rgba(15,23,42,0.08)', fontWeight: '800',
  },
  filterBar: {
    display: 'flex', alignItems: 'center', gap: '10px',
    backgroundColor: '#fff', borderRadius: '14px', padding: '12px 16px',
    border: '1px solid rgba(148,163,184,0.18)', boxShadow: '0 2px 8px rgba(15,23,42,0.04)',
    flexWrap: 'wrap',
  },
  presetBtn: {
    padding: '5px 11px', borderRadius: '8px', fontSize: '12px', fontWeight: '600',
    cursor: 'pointer', border: '1px solid rgba(148,163,184,0.3)',
    backgroundColor: '#f8fafc', color: '#475569', transition: 'all 0.15s', fontFamily: 'inherit',
  },
  presetBtnActive: { backgroundColor: '#0d9488', color: '#fff', border: '1px solid #0d9488' },
  refreshBtn: {
    display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px',
    borderRadius: '10px', backgroundColor: '#0d9488', color: '#fff', border: 'none',
    cursor: 'pointer', fontWeight: '700', fontSize: '12px', transition: 'all 0.2s', fontFamily: 'inherit',
  },
  primaryBtn: {
    display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 18px',
    borderRadius: '10px', backgroundColor: '#0d9488', color: '#fff', border: 'none',
    cursor: 'pointer', fontWeight: '700', fontSize: '13px', transition: 'all 0.2s', fontFamily: 'inherit',
  },
  secondaryBtn: {
    display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 18px',
    borderRadius: '10px', backgroundColor: '#f1f5f9', color: '#475569',
    border: '1px solid rgba(148,163,184,0.3)', cursor: 'pointer',
    fontWeight: '600', fontSize: '13px', fontFamily: 'inherit',
  },
  errorBox: {
    display: 'flex', alignItems: 'center', gap: '10px',
    backgroundColor: '#fef2f2', border: '1px solid rgba(239,68,68,0.2)',
    borderRadius: '12px', padding: '12px 16px', color: '#991b1b', fontSize: '13px', fontWeight: '600',
  },
  card: {
    backgroundColor: '#fff', borderRadius: '18px', padding: '24px',
    border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 4px 16px rgba(15,23,42,0.04)',
  },
  kpiGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '14px', marginBottom: '4px' },
  kpiCard: {
    backgroundColor: '#fff', borderRadius: '16px', padding: '18px',
    border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 4px 16px rgba(15,23,42,0.04)',
    cursor: 'default', transition: 'all 0.2s ease',
  },
  kpiLabel: { margin: '0 0 5px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.6px', textTransform: 'uppercase', color: '#64748b' },
  kpiValue: { margin: '0', fontSize: '20px', fontWeight: '800', letterSpacing: '-0.4px' },
  kpiSub: { margin: '3px 0 0', fontSize: '10px', color: '#94a3b8', fontWeight: '500' },
  kpiIcon: { width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  sectionTitle: { margin: 0, fontSize: '15px', fontWeight: '800', color: '#0f172a', letterSpacing: '-0.2px', textAlign: 'left' },
  compositionBar: { display: 'flex', height: '12px', borderRadius: '99px', overflow: 'hidden', backgroundColor: '#f1f5f9', marginTop: '12px', gap: '2px' },
  compSegment: { height: '100%', transition: 'width 0.6s ease', borderRadius: '99px' },
  tabBar: { display: 'flex', gap: '0', borderBottom: '1px solid rgba(148,163,184,0.16)' },
  tabBtn: {
    display: 'flex', alignItems: 'center', gap: '5px', padding: '9px 16px',
    border: 'none', borderBottom: '2px solid transparent', backgroundColor: 'transparent',
    color: '#64748b', fontWeight: '600', fontSize: '12px', cursor: 'pointer',
    transition: 'all 0.2s', marginBottom: '-1px', fontFamily: 'inherit',
  },
  tabBtnActive: { color: '#0d9488', borderBottom: '2px solid #0d9488', fontWeight: '700' },
  ledgerRow: {
    display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px',
    borderRadius: '10px', border: '1px solid rgba(148,163,184,0.1)', backgroundColor: '#f8fafc',
  },
  ledgerDesc: { margin: '0 0 2px', fontSize: '12px', fontWeight: '700', color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  ledgerType: { fontSize: '9px', fontWeight: '700', letterSpacing: '0.4px', color: '#64748b', textTransform: 'uppercase' },
  filterChip: {
    padding: '5px 12px', borderRadius: '8px', border: '1px solid rgba(148,163,184,0.3)',
    backgroundColor: '#f8fafc', color: '#475569', fontSize: '12px', fontWeight: '600',
    cursor: 'pointer', transition: 'all 0.15s', fontFamily: 'inherit',
  },
  badge: { display: 'inline-flex', alignItems: 'center', padding: '3px 8px', borderRadius: '20px', fontSize: '10px', fontWeight: '700' },
  auditHeader: {
    display: 'grid', gridTemplateColumns: '1.2fr 0.5fr 1fr 0.8fr 0.8fr 1fr', gap: '8px',
    padding: '6px 12px', fontSize: '9px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase', color: '#94a3b8',
  },
  auditRow: {
    display: 'grid', gridTemplateColumns: '1.2fr 0.5fr 1fr 0.8fr 0.8fr 1fr', gap: '8px',
    alignItems: 'center', padding: '10px 12px', borderRadius: '10px',
    backgroundColor: '#f8fafc', border: '1px solid rgba(148,163,184,0.1)', marginBottom: '3px',
  },
  emptyChart: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '10px', padding: '40px', minHeight: '160px' },
  emptyText: { fontSize: '13px', color: '#94a3b8', fontWeight: '600' },
  spinnerWrap: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px', gap: '0' },
  modalOverlay: {
    position: 'fixed', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', zIndex: 1000,
    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px',
  },
  modal: {
    backgroundColor: '#fff', borderRadius: '20px', width: '100%',
    boxShadow: '0 24px 64px rgba(15,23,42,0.16)', overflow: 'hidden',
  },
  modalHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '20px 24px', borderBottom: '1px solid rgba(148,163,184,0.14)',
  },
  modalTitle: { margin: 0, fontSize: '16px', fontWeight: '800', color: '#0f172a' },
  modalClose: { background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#94a3b8', display: 'flex' },
  modalBody: { padding: '24px' },
  formLabel: { display: 'block', fontSize: '11px', fontWeight: '700', color: '#475569', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' },
  formInput: {
    display: 'block', width: '100%', padding: '10px 12px', borderRadius: '10px',
    border: '1px solid rgba(148,163,184,0.3)', fontSize: '13px', fontWeight: '500',
    color: '#1e293b', backgroundColor: '#f8fafc', fontFamily: 'inherit',
    transition: 'all 0.15s',
  },
};

export default FinanceDashboard;
