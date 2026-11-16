path = r"hotel-frontend\src\pages\CashierDashboard.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. State additions
old_state = "  // Payment method selection removed — payment is handled by Waiter"
new_state = """  // Multi-Tender Payment Settlement (ADR-005)
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedTenderMethod, setSelectedTenderMethod] = useState('Cash');
  const [tenderReference, setTenderReference] = useState('');
  const [occupiedRooms, setOccupiedRooms] = useState([]);
  const [selectedReservationId, setSelectedReservationId] = useState('');
  const [loadingOccupiedRooms, setLoadingOccupiedRooms] = useState(false);"""

assert old_state in content, "old_state not found"
content = content.replace(old_state, new_state, 1)

# 2. Methods
old_handler = "  const handleDirectComplete = async (order) => {"
new_methods = """  const fetchOccupiedRooms = async () => {
    setLoadingOccupiedRooms(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.get(`${API_BASE}rooms/occupied/`, { headers });
      setOccupiedRooms(res.data || []);
    } catch (err) {
      console.error('Failed to fetch occupied rooms:', err);
    } finally {
      setLoadingOccupiedRooms(false);
    }
  };

  const openPaymentModal = (order) => {
    setSelectedOrder(order);
    setSelectedTenderMethod('Cash');
    setTenderReference('');
    setSelectedReservationId('');
    setIsPaymentModalOpen(true);
    fetchOccupiedRooms();
  };

  const handleExecuteSettlement = async () => {
    if (!selectedOrder) return;
    if (selectedTenderMethod === 'Room Charge' && !selectedReservationId) {
      alert('Please select a checked-in guest room to post the room charge.');
      return;
    }
    setIsBusy(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      const payload = {
        payment_method: selectedTenderMethod,
        payment_reference: tenderReference.trim() || undefined,
        reservation_id: selectedTenderMethod === 'Room Charge' ? selectedReservationId : undefined,
      };

      if (selectedOrder.is_session && selectedOrder.session_id) {
        const res = await axios.post(
          `${API_BASE}sessions/${selectedOrder.session_id}/settle/`,
          payload,
          { headers }
        );
        alert(res.data?.message || 'Dining session settled successfully and table released.');
      } else {
        const res = await axios.post(
          `${API_BASE}orders/${selectedOrder.id}/complete/`,
          payload,
          { headers }
        );
        alert(res.data?.message || 'Order completed successfully.');
      }
      setIsPaymentModalOpen(false);
      setSelectedOrder(null);
      await fetchDataUpdate();
    } catch (err) {
      alert(err.response?.data?.error || err.response?.data?.detail || 'Settlement failed.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleDirectComplete = async (order) => {"""

assert old_handler in content, "old_handler not found"
content = content.replace(old_handler, new_methods, 1)

# 3. Action buttons in sidebar
old_btn = """                            {!selectedOrder.has_pending_handover && (
                              <button
                                onClick={() => handleDirectComplete(selectedOrder)}
                                disabled={isBusy}
                                style={{ width: '100%', padding: '8px 14px', background: '#fff', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '6px', fontWeight: '600', fontSize: '12px', cursor: 'pointer' }}
                              >
                                Direct Cash Settlement (Counter)
                              </button>
                            )}"""

new_btn = """                            {!selectedOrder.has_pending_handover && (
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                                <button
                                  type="button"
                                  onClick={() => handleDirectComplete(selectedOrder)}
                                  disabled={isBusy}
                                  style={{ width: '100%', padding: '10px 10px', background: '#fff', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '6px', fontWeight: '600', fontSize: '12px', cursor: 'pointer' }}
                                >
                                  Quick Cash
                                </button>
                                <button
                                  type="button"
                                  onClick={() => openPaymentModal(selectedOrder)}
                                  disabled={isBusy}
                                  style={{ width: '100%', padding: '10px 10px', background: '#0f766e', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '700', fontSize: '12px', cursor: 'pointer' }}
                                >
                                  Multi-Tender
                                </button>
                              </div>
                            )}"""

assert old_btn in content, "old_btn not found"
content = content.replace(old_btn, new_btn, 1)

# 4. Modal Dialog before final close of return
modal_markup = """
      {/* Multi-Tender Settlement Modal (ADR-005) */}
      {isPaymentModalOpen && selectedOrder && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(15,23,42,0.45)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100, padding: '20px', backdropFilter: 'blur(6px)' }}>
          <div style={{ backgroundColor: '#fff', borderRadius: '16px', padding: '24px', maxWidth: '520px', width: '100%', boxShadow: '0 20px 60px rgba(15,23,42,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '800', color: '#0f172a' }}>
                  {selectedOrder.is_session ? `Settle Table ${selectedOrder.table_code} Session` : `Settle Order #${selectedOrder.id}`}
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Total Due: <strong>{settings?.currency_symbol || 'ETB'} {Number(selectedOrder.total_amount || 0).toFixed(2)}</strong>
                </p>
              </div>
              <button type="button" onClick={() => setIsPaymentModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '8px' }}>
                Select Tender Method
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {['Cash', 'Card', 'Digital Payment', 'Room Charge'].map((tender) => (
                  <button
                    key={tender}
                    type="button"
                    onClick={() => setSelectedTenderMethod(tender)}
                    style={{
                      padding: '10px 4px',
                      borderRadius: '8px',
                      border: selectedTenderMethod === tender ? '2px solid #0f766e' : '1px solid #cbd5e1',
                      backgroundColor: selectedTenderMethod === tender ? '#f0fdfa' : '#fff',
                      color: selectedTenderMethod === tender ? '#0f766e' : '#475569',
                      fontWeight: selectedTenderMethod === tender ? '700' : '500',
                      fontSize: '11px',
                      textAlign: 'center',
                      cursor: 'pointer'
                    }}
                  >
                    {tender === 'Digital Payment' ? 'Telebirr/Chapa' : tender}
                  </button>
                ))}
              </div>
            </div>

            {selectedTenderMethod === 'Card' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>
                  POS Terminal / Auth Reference
                </label>
                <input
                  type="text"
                  placeholder="e.g. POS-AUTH-98421"
                  value={tenderReference}
                  onChange={(e) => setTenderReference(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>
            )}

            {selectedTenderMethod === 'Digital Payment' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>
                  Digital Transaction Reference (Telebirr / Chapa)
                </label>
                <input
                  type="text"
                  placeholder="e.g. TLB-TX-55421"
                  value={tenderReference}
                  onChange={(e) => setTenderReference(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>
            )}

            {selectedTenderMethod === 'Room Charge' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>
                  Post to Checked-In Guest Room Folio
                </label>
                <select
                  value={selectedReservationId}
                  onChange={(e) => setSelectedReservationId(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box', backgroundColor: '#fff' }}
                >
                  <option value="">-- Select In-House Room --</option>
                  {occupiedRooms.map((r) => (
                    <option key={r.reservation_id} value={r.reservation_id}>
                      Room {r.room_number} — {r.guest_name} ({r.room_type})
                    </option>
                  ))}
                </select>
                {occupiedRooms.length === 0 && !loadingOccupiedRooms && (
                  <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#ef4444' }}>
                    No active checked-in rooms found.
                  </p>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button
                type="button"
                onClick={() => setIsPaymentModalOpen(false)}
                disabled={isBusy}
                style={{ padding: '10px 16px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '8px', color: '#475569', fontWeight: '600', cursor: 'pointer', fontSize: '13px' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteSettlement}
                disabled={isBusy}
                style={{ padding: '10px 20px', background: '#0f766e', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: '700', cursor: 'pointer', fontSize: '13px' }}
              >
                {isBusy ? 'Processing...' : 'Confirm & Settle Payment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
"""

old_return_end = "    </div>\n  );\n};"
if old_return_end in content:
    content = content.replace(old_return_end, modal_markup, 1)
else:
    # Try CRLF
    old_return_end_crlf = "    </div>\r\n  );\r\n};"
    assert old_return_end_crlf in content, "old_return_end not found"
    content = content.replace(old_return_end_crlf, modal_markup.replace("\n", "\r\n"), 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("CashierDashboard.js updated successfully!")
