import os

path = r"hotel-frontend\src\RoomManager.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
old_import = """import {
  PlusCircle, X, Trash2, Edit3, ImageIcon,
  LayoutGrid, List, CheckCircle, User, RefreshCw, Wrench,
  Globe, CalendarCheck2, ClipboardList, ScanLine,
  Receipt
} from 'lucide-react';"""

new_import = """import {
  PlusCircle, X, Trash2, Edit3, ImageIcon,
  LayoutGrid, List, CheckCircle, User, RefreshCw, Wrench,
  Globe, CalendarCheck2, ClipboardList, ScanLine,
  Receipt, Moon, AlertTriangle, ShieldCheck
} from 'lucide-react';"""

assert old_import in content, "old_import not found"
content = content.replace(old_import, new_import, 1)

# 2. State & Handlers
old_state_anchor = "  const [housekeepingItems, setHousekeepingItems] = useState([]);"
new_state_block = """  const [housekeepingItems, setHousekeepingItems] = useState([]);

  // PMS Night Audit Engine States
  const [nightAuditStatus, setNightAuditStatus] = useState(null);
  const [nightAuditLoading, setNightAuditLoading] = useState(false);
  const [isNightAuditModalOpen, setIsNightAuditModalOpen] = useState(false);
  const [nightAuditNotes, setNightAuditNotes] = useState('');
  const [nightAuditForce, setNightAuditForce] = useState(false);
  const [nightAuditResult, setNightAuditResult] = useState(null);
  const [nightAuditError, setNightAuditError] = useState(null);
  const [executingNightAudit, setExecutingNightAudit] = useState(false);

  const fetchNightAuditStatus = async () => {
    setNightAuditLoading(true);
    setNightAuditError(null);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.get(`${API_BASE_URL}/v1/night-audit/status/`, { headers });
      setNightAuditStatus(res.data);
    } catch (err) {
      console.error('Failed to load night audit status:', err);
      setNightAuditError(err.response?.data?.error || err.message);
    } finally {
      setNightAuditLoading(false);
    }
  };

  const handleExecuteNightAudit = async () => {
    setExecutingNightAudit(true);
    setNightAuditError(null);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.post(
        `${API_BASE_URL}/v1/night-audit/execute/`,
        { notes: nightAuditNotes, force: nightAuditForce },
        { headers }
      );
      setNightAuditResult(res.data);
      setIsNightAuditModalOpen(false);
      setNightAuditNotes('');
      setNightAuditForce(false);
      await fetchNightAuditStatus();
      await fetchRooms();
      await fetchReservations();
    } catch (err) {
      console.error('Night audit failed:', err);
      setNightAuditError(err.response?.data?.error || err.message);
    } finally {
      setExecutingNightAudit(false);
    }
  };"""

assert old_state_anchor in content, "old_state_anchor not found"
content = content.replace(old_state_anchor, new_state_block, 1)

# Add useEffect for activeSection === 'night_audit'
old_ue = "  useEffect(() => { fetchRooms(); fetchReservations(); fetchPublicSiteInfo(); fetchHousekeepingItems(); }, []);"
new_ue = """  useEffect(() => { fetchRooms(); fetchReservations(); fetchPublicSiteInfo(); fetchHousekeepingItems(); }, []);
  useEffect(() => {
    if (activeSection === 'night_audit') {
      fetchNightAuditStatus();
    }
  }, [activeSection]);"""

assert old_ue in content, "old_ue not found"
content = content.replace(old_ue, new_ue, 1)

# 3. Night Audit Desk in JSX
old_audit_block = """      {isNightAuditSection ? (
        <div style={auditBoard}>
          <div style={auditCard}>
            <h3 style={{ marginTop: 0 }}>Night Audit Snapshot</h3>
            <p style={opsText}>Review arrivals, in-house guests, and cleaning tasks before closing the shift.</p>
            <div style={auditStatsGrid}>
              <div style={auditMiniCard}><strong>{visibleReservations.filter((item) => item.status === 'confirmed').length}</strong><span>Confirmed arrivals</span></div>
              <div style={auditMiniCard}><strong>{visibleReservations.filter((item) => item.status === 'checked_in').length}</strong><span>In-house guests</span></div>
              <div style={auditMiniCard}><strong>{rooms.filter((room) => room.status === 'Cleaning').length}</strong><span>Cleaning queue</span></div>
              <div style={auditMiniCard}><strong>{bookedOnlineCount}</strong><span>Booked online</span></div>
            </div>
          </div>
        </div>
      ) :"""

new_audit_block = """      {isNightAuditSection ? (
        <div style={{ padding: '0 0 40px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
          {/* Active Business Date Hero Card */}
          <div style={{
            backgroundColor: '#0f172a',
            borderRadius: '16px',
            padding: '24px 28px',
            color: '#ffffff',
            marginBottom: '24px',
            boxShadow: '0 10px 25px -5px rgba(15, 23, 42, 0.2)',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '20px'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontSize: '13px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Moon size={16} /> PMS Night Audit & Date Rollover Engine
              </div>
              <h2 style={{ fontSize: '26px', fontWeight: '800', margin: '8px 0 4px', color: '#f8fafc' }}>
                Operational Business Date: {nightAuditStatus?.current_business_date || 'Loading...'}
              </h2>
              <p style={{ margin: 0, color: '#94a3b8', fontSize: '14px' }}>
                Rollover will transition business date to <strong style={{ color: '#38bdf8' }}>{nightAuditStatus?.next_business_date || '...'}</strong>, accrue daily room rates, and post balanced GL entries.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                type="button"
                onClick={fetchNightAuditStatus}
                disabled={nightAuditLoading}
                style={{
                  padding: '10px 16px',
                  backgroundColor: '#1e293b',
                  color: '#e2e8f0',
                  border: '1px solid #334155',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontWeight: '600',
                  fontSize: '13px'
                }}
              >
                <RefreshCw size={14} className={nightAuditLoading ? 'spin' : ''} /> Refresh
              </button>
              <button
                type="button"
                onClick={() => { setIsNightAuditModalOpen(true); setNightAuditError(null); }}
                disabled={nightAuditLoading}
                style={{
                  padding: '12px 24px',
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontWeight: '700',
                  fontSize: '14px',
                  boxShadow: '0 4px 14px rgba(2, 132, 199, 0.39)'
                }}
              >
                <ShieldCheck size={18} /> Execute Night Audit
              </button>
            </div>
          </div>

          {/* Error Message */}
          {nightAuditError && (
            <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '10px', padding: '14px 18px', color: '#b91c1c', marginBottom: '20px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <AlertTriangle size={18} /> {nightAuditError}
            </div>
          )}

          {/* Success Result */}
          {nightAuditResult && (
            <div style={{ backgroundColor: '#f0fdf4', border: '1px solid #86efac', borderRadius: '12px', padding: '18px 22px', color: '#166534', marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '800', fontSize: '15px' }}>
                <CheckCircle size={18} color="#16a34a" /> Night Audit Successfully Completed!
              </div>
              <div style={{ marginTop: '10px', fontSize: '13px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                <div>Previous Date: <strong>{nightAuditResult.previous_business_date}</strong></div>
                <div>New Business Date: <strong>{nightAuditResult.new_business_date}</strong></div>
                <div>Rooms Accrued: <strong>{nightAuditResult.accrued_rooms_count}</strong></div>
                <div>Total Accrued Revenue: <strong>ETB {Number(nightAuditResult.total_room_revenue_accrued || 0).toFixed(2)}</strong></div>
                <div>GL Journal Entry: <strong>{nightAuditResult.gl_journal_entry || 'Auto-Posted'}</strong></div>
                <div>Closed By: <strong>{nightAuditResult.closed_by}</strong></div>
              </div>
            </div>
          )}

          {/* Pre-Audit Readiness Grid */}
          <h3 style={{ fontSize: '16px', fontWeight: '800', color: '#1e293b', marginBottom: '14px' }}>
            Pre-Audit Operational Readiness Checklist
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '28px' }}>
            {/* In-House Guests */}
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '18px', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b' }}>IN-HOUSE GUESTS</span>
                <User size={16} color="#0284c7" />
              </div>
              <div style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', margin: '8px 0 4px' }}>
                {nightAuditStatus?.in_house_guests_count ?? visibleReservations.filter(i => i.status === 'checked_in').length}
              </div>
              <div style={{ fontSize: '12px', color: '#0284c7', fontWeight: '600' }}>
                Projected Rate: ETB {Number(nightAuditStatus?.projected_room_revenue ?? 0).toFixed(2)}
              </div>
            </div>

            {/* Unsettled Orders */}
            <div style={{
              backgroundColor: '#ffffff',
              border: `1px solid ${nightAuditStatus?.unsettled_orders_count > 0 ? '#fca5a5' : '#bbf7d0'}`,
              borderRadius: '12px',
              padding: '18px',
              boxShadow: '0 2px 6px rgba(0,0,0,0.02)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b' }}>RESTAURANT ORDERS</span>
                <Receipt size={16} color={nightAuditStatus?.unsettled_orders_count > 0 ? '#ef4444' : '#16a34a'} />
              </div>
              <div style={{ fontSize: '24px', fontWeight: '800', color: nightAuditStatus?.unsettled_orders_count > 0 ? '#dc2626' : '#16a34a', margin: '8px 0 4px' }}>
                {nightAuditStatus?.unsettled_orders_count ?? 0}
              </div>
              <div style={{ fontSize: '12px', color: nightAuditStatus?.unsettled_orders_count > 0 ? '#b91c1c' : '#15803d', fontWeight: '600' }}>
                {nightAuditStatus?.unsettled_orders_count > 0 ? '⚠️ Unsettled orders remain' : '✓ All orders settled'}
              </div>
            </div>

            {/* Pending Arrivals */}
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '18px', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b' }}>PENDING ARRIVALS</span>
                <CalendarCheck2 size={16} color="#d97706" />
              </div>
              <div style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', margin: '8px 0 4px' }}>
                {nightAuditStatus?.pending_arrivals_count ?? visibleReservations.filter(i => i.status === 'confirmed').length}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                Confirmed reservations
              </div>
            </div>

            {/* Housekeeping Queue */}
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '18px', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b' }}>CLEANING QUEUE</span>
                <Wrench size={16} color="#8b5cf6" />
              </div>
              <div style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', margin: '8px 0 4px' }}>
                {nightAuditStatus?.cleaning_rooms_count ?? rooms.filter(r => r.status === 'Cleaning').length}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                Rooms awaiting inspection
              </div>
            </div>
          </div>

          {/* Historical Audits (Z-Reports) */}
          <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '16px', overflow: 'hidden', boxShadow: '0 4px 12px rgba(15,23,42,0.03)' }}>
            <div style={{ padding: '16px 20px', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: '800', color: '#1e293b' }}>Recent Closed Day Audits (Z-Reports)</span>
              <span style={{ fontSize: '12px', color: '#64748b' }}>Past Financial Day Closures</span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f1f5f9', color: '#475569', fontWeight: '700' }}>
                  <th style={{ padding: '12px 16px' }}>Audit Date</th>
                  <th style={{ padding: '12px 16px' }}>Closed By</th>
                  <th style={{ padding: '12px 16px' }}>Closed At</th>
                  <th style={{ padding: '12px 16px' }}>Room Revenue</th>
                  <th style={{ padding: '12px 16px' }}>Grand Total</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {nightAuditStatus?.recent_audits?.length > 0 ? (
                  nightAuditStatus.recent_audits.map((a, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f8fafc' }}>
                      <td style={{ padding: '12px 16px', fontWeight: '700', color: '#0f172a' }}>{a.audit_date}</td>
                      <td style={{ padding: '12px 16px', color: '#475569' }}>{a.closed_by || 'System'}</td>
                      <td style={{ padding: '12px 16px', color: '#64748b' }}>{a.closed_at ? new Date(a.closed_at).toLocaleString() : '—'}</td>
                      <td style={{ padding: '12px 16px', fontWeight: '600', color: '#0f172a' }}>ETB {Number(a.total_room_revenue || 0).toFixed(2)}</td>
                      <td style={{ padding: '12px 16px', fontWeight: '800', color: '#15803d' }}>ETB {Number(a.total_revenue || 0).toFixed(2)}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ backgroundColor: '#dcfce7', color: '#166534', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: '700' }}>Closed</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                      No closed audits recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Night Audit Confirmation Modal */}
          {isNightAuditModalOpen && (
            <div style={modalOverlay} onClick={() => !executingNightAudit && setIsNightAuditModalOpen(false)}>
              <div style={{ ...modalContent, maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldCheck size={20} color="#0284c7" />
                    <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>Confirm Night Audit Execution</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsNightAuditModalOpen(false)}
                    disabled={executingNightAudit}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}
                  >
                    <X size={20} />
                  </button>
                </div>

                <div style={{ backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '10px', padding: '14px', fontSize: '13px', color: '#0369a1', marginBottom: '16px' }}>
                  <p style={{ margin: '0 0 6px 0', fontWeight: '700' }}>Operational Action Summary:</p>
                  <ul style={{ margin: 0, paddingLeft: '18px', lineHeight: 1.5 }}>
                    <li>Active Date: <strong>{nightAuditStatus?.current_business_date}</strong> ➔ New Date: <strong>{nightAuditStatus?.next_business_date}</strong></li>
                    <li>Accrue room rate & taxes for <strong>{nightAuditStatus?.in_house_guests_count || 0}</strong> in-house room(s) (Est. ETB {Number(nightAuditStatus?.projected_room_revenue || 0).toFixed(2)})</li>
                    <li>Post balanced double-entry General Ledger journal entries (Accounts 1200 / 4000, 2200, 2300)</li>
                    <li>Finalize financial day snapshot (Z-Report DayAuditLog)</li>
                  </ul>
                </div>

                {nightAuditStatus?.unsettled_orders_count > 0 && (
                  <div style={{ backgroundColor: '#fff1f2', border: '1px solid #fecdd3', borderRadius: '10px', padding: '12px 14px', fontSize: '13px', color: '#be123c', marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '700' }}>
                      <AlertTriangle size={16} /> Warning: Unsettled Dining Orders
                    </div>
                    <p style={{ margin: '4px 0 8px 0', fontSize: '12px' }}>
                      There are {nightAuditStatus.unsettled_orders_count} unsettled restaurant order(s) open. Night audit will be blocked unless emergency manager override is enabled.
                    </p>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: '700', color: '#9f1239', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={nightAuditForce}
                        onChange={(e) => setNightAuditForce(e.target.checked)}
                      />
                      Emergency Manager Override: Proceed despite open orders
                    </label>
                  </div>
                )}

                <div style={{ marginBottom: '18px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>
                    Night Audit / Shift Notes (Optional)
                  </label>
                  <textarea
                    value={nightAuditNotes}
                    onChange={(e) => setNightAuditNotes(e.target.value)}
                    placeholder="Enter any shift handover notes, variance observations, or management commentary..."
                    rows={3}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setIsNightAuditModalOpen(false)}
                    disabled={executingNightAudit}
                    style={{ padding: '10px 18px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '8px', color: '#475569', fontWeight: '600', cursor: 'pointer', fontSize: '13px' }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleExecuteNightAudit}
                    disabled={executingNightAudit || (nightAuditStatus?.unsettled_orders_count > 0 && !nightAuditForce)}
                    style={{
                      padding: '10px 20px',
                      background: (nightAuditStatus?.unsettled_orders_count > 0 && !nightAuditForce) ? '#94a3b8' : '#0284c7',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '8px',
                      fontWeight: '700',
                      cursor: (nightAuditStatus?.unsettled_orders_count > 0 && !nightAuditForce) ? 'not-allowed' : 'pointer',
                      fontSize: '13px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    {executingNightAudit ? <RefreshCw size={14} className="spin" /> : <ShieldCheck size={16} />}
                    {executingNightAudit ? 'Executing Rollover...' : 'Confirm & Execute Night Audit'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) :"""

assert old_audit_block in content, "old_audit_block not found"
content = content.replace(old_audit_block, new_audit_block, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("RoomManager.js updated successfully!")

