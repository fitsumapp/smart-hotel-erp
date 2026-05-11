import React, { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import {
  PlusCircle, X, Search, User, Phone, Globe, CalendarDays,
  CreditCard, ClipboardList, ChevronDown, CheckCircle, Clock,
  AlertCircle, Filter, Download, Eye
} from 'lucide-react';
import { API_BASE_URL } from '../apiConfig';

const RESERVATIONS_API = `${API_BASE_URL}/users/reservations/`;
const ROOMS_API = `${API_BASE_URL}/users/rooms/`;
const RESERVE_API = `${API_BASE_URL}/users/rooms`;
const GUEST_API = `${API_BASE_URL}/users/guest-profiles/`;

const SOURCE_OPTIONS = ['front_desk', 'online', 'phone', 'walk_in'];
const STATUS_COLORS = {
  pending: { bg: 'rgba(245,158,11,0.15)', color: '#fcd34d', label: 'Pending' },
  confirmed: { bg: 'rgba(37,99,235,0.15)', color: '#93c5fd', label: 'Confirmed' },
  checked_in: { bg: 'rgba(22,163,74,0.15)', color: '#86efac', label: 'Checked In' },
  checked_out: { bg: 'rgba(100,116,139,0.15)', color: '#94a3b8', label: 'Checked Out' },
  cancelled: { bg: 'rgba(239,68,68,0.15)', color: '#fca5a5', label: 'Cancelled' },
};

const emptyBooking = {
  guest_name: '', guest_email: '', guest_phone: '', adults: 1, children: 0,
  check_in_date: '', check_out_date: '', notes: '', pay_now: false,
  source: 'walk_in',
  nationality: '', id_type: 'Kebele ID', id_number: '',
  gender: 'Male', dob: '', id_issue_place: '', id_issue_date: '',
  country: 'Ethiopia', city: '', sub_city: '', nights: 1,
  payment_method: 'Cash', advance_paid: '', balance: '',
  emergency_name: '', emergency_phone: '', emergency_relation: ''
};

export default function BookingsManager() {
  const [reservations, setReservations] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedReservation, setSelectedReservation] = useState(null);
  const [form, setForm] = useState(emptyBooking);
  const [selectedRoomId, setSelectedRoomId] = useState('');
  const [guestHistory, setGuestHistory] = useState([]);
  const [showHistoryPanel, setShowHistoryPanel] = useState(false);
  const [actionLoading, setActionLoading] = useState({});

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const [resRes, roomRes] = await Promise.all([
        axios.get(RESERVATIONS_API),
        axios.get(ROOMS_API),
      ]);
      setReservations(resRes.data);
      setRooms(roomRes.data);
    } catch (err) { console.error(err); }
  };

  const filtered = useMemo(() => {
    let list = reservations;
    if (statusFilter !== 'all') list = list.filter(r => r.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(r =>
        r.guest_name?.toLowerCase().includes(q) ||
        r.guest_phone?.toLowerCase().includes(q) ||
        r.room_number?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [reservations, statusFilter, search]);

  const stats = useMemo(() => ({
    total: reservations.length,
    confirmed: reservations.filter(r => r.status === 'confirmed').length,
    checkedIn: reservations.filter(r => r.status === 'checked_in').length,
    pending: reservations.filter(r => r.status === 'pending').length,
  }), [reservations]);

  const handleCreateBooking = async (e) => {
    e.preventDefault();
    if (!selectedRoomId) { alert('Please select a room.'); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${RESERVE_API}/${selectedRoomId}/reserve-now/`, {
        source: form.source === 'online' ? 'public' : 'reception',
        pay_now: form.pay_now,
        guest_name: form.guest_name,
        guest_email: form.guest_email,
        guest_phone: form.guest_phone,
        check_in_date: form.check_in_date,
        check_out_date: form.check_out_date,
        adults: form.adults,
        children: form.children,
        notes: `Gender: ${form.gender} | DOB: ${form.dob}
ID Issued: ${form.id_issue_place} on ${form.id_issue_date}
Address: ${form.sub_city}, ${form.city}, ${form.country}
Payment: ${form.payment_method} | Adv: ETB ${form.advance_paid}
Emergency: ${form.emergency_name} (${form.emergency_phone}) - ${form.emergency_relation}
Notes: ${form.notes}`,
      });

      // Save guest profile
      if (res.data?.reservation?.id) {
        await axios.post(GUEST_API, {
          reservation: res.data.reservation.id,
          full_name: form.guest_name,
          phone: form.guest_phone,
          nationality: form.nationality,
          id_type: form.id_type,
          id_number: form.id_number,
        }).catch(() => {});
      }

      if (res.data?.checkout_url) {
        window.open(res.data.checkout_url, '_blank', 'noopener,noreferrer');
      } else {
        alert(res.data?.message || 'Booking created successfully.');
      }
      setIsModalOpen(false);
      setForm(emptyBooking);
      setSelectedRoomId('');
      fetchAll();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to create booking.');
    } finally { setLoading(false); }
  };

  const viewGuestHistory = async (phone) => {
    if (!phone) return;
    try {
      const res = await axios.get(`${GUEST_API}?phone=${encodeURIComponent(phone)}`);
      setGuestHistory(res.data);
      setShowHistoryPanel(true);
    } catch (err) { console.error(err); }
  };

  const handlePayDeposit = (res) => {
    if (res.chapa_checkout_url) {
      window.open(res.chapa_checkout_url, '_blank', 'noopener,noreferrer');
    } else {
      alert('No Chapa payment link available for this reservation.');
    }
  };

  const availableRooms = rooms.filter(r =>
    ['Available', 'Reserved'].includes(r.status) || r.id === Number(selectedRoomId)
  );

  return (
    <div style={{ padding: '20px', backgroundColor: '#020617', minHeight: '100vh', color: '#fff' }}>
      {/* Hero */}
      <div style={heroCard}>
        <div>
          <p style={eyebrow}>Front Office</p>
          <h2 style={{ margin: '8px 0', fontSize: '28px' }}>Bookings Manager</h2>
          <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.6 }}>
            Full reservation management with guest profiles, Chapa deposits, and booking history.
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignContent: 'start', justifyContent: 'flex-end' }}>
          <span style={pill}><Globe size={14} /> Online Booking</span>
          <span style={pill}><CreditCard size={14} /> Chapa Deposits</span>
          <span style={pill}><User size={14} /> Guest Profiles</span>
        </div>
      </div>

      {/* Stats */}
      <div style={statsGrid}>
        {[
          { label: 'Total Bookings', value: stats.total, color: '#38bdf8', bg: '#eff6ff' },
          { label: 'Confirmed', value: stats.confirmed, color: '#2563eb', bg: '#eff6ff' },
          { label: 'In-House', value: stats.checkedIn, color: '#16a34a', bg: '#f0fdf4' },
          { label: 'Pending', value: stats.pending, color: '#f59e0b', bg: '#fffbeb' },
        ].map(s => (
          <div key={s.label} style={statCard}>
            <div style={{ width: 40, height: 40, borderRadius: 10, backgroundColor: s.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ClipboardList size={18} color={s.color} />
            </div>
            <div>
              <p style={{ margin: 0, fontSize: 10, fontWeight: 700, color: '#94a3b8' }}>{s.label.toUpperCase()}</p>
              <h3 style={{ margin: 0, fontSize: 22, color: '#0f172a' }}>{s.value}</h3>
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={searchBox}>
          <Search size={16} color="#64748b" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search guest, phone, room..."
            style={searchInput}
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="all">All Statuses</option>
          {Object.entries(STATUS_COLORS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <button onClick={() => { setIsModalOpen(true); setForm(emptyBooking); }} style={addBtn}>
          <PlusCircle size={18} /> New Booking
        </button>
      </div>

      {/* Bookings Table */}
      <div style={tableWrap}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e293b', backgroundColor: 'rgba(30,41,59,0.4)' }}>
              {['Guest', 'Room', 'Check-In', 'Check-Out', 'Source', 'Payment', 'Status', 'Actions'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(res => {
              const sc = STATUS_COLORS[res.status] || STATUS_COLORS.pending;
              return (
                <tr key={res.id} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={td}>
                    <div style={{ fontWeight: 600 }}>{res.guest_name}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>{res.guest_phone || '—'}</div>
                  </td>
                  <td style={td}>
                    <div>#{res.room_number}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>{res.room_name}</div>
                  </td>
                  <td style={td}>{res.check_in_date}</td>
                  <td style={td}>{res.check_out_date}</td>
                  <td style={td}>
                    <span style={{ ...pill, fontSize: 10, padding: '3px 8px' }}>{res.source}</span>
                  </td>
                  <td style={td}>
                    <span style={{ fontSize: 11, color: res.payment_status === 'paid' ? '#86efac' : '#fcd34d', fontWeight: 700 }}>
                      {res.payment_status?.toUpperCase()}
                    </span>
                    <div style={{ fontSize: 10, color: '#64748b' }}>ETB {res.deposit_amount}</div>
                  </td>
                  <td style={td}>
                    <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700, backgroundColor: sc.bg, color: sc.color }}>
                      {sc.label}
                    </span>
                  </td>
                  <td style={td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={() => { setSelectedReservation(res); viewGuestHistory(res.guest_phone); }}
                        style={iconBtn}
                        title="View Guest"
                      ><Eye size={14} /></button>
                      {res.chapa_checkout_url && res.payment_status !== 'paid' && (
                        <button onClick={() => handlePayDeposit(res)} style={{ ...iconBtn, backgroundColor: 'rgba(37,99,235,0.2)', color: '#93c5fd' }} title="Pay Deposit">
                          <CreditCard size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!filtered.length && (
              <tr><td colSpan={8} style={{ padding: 30, textAlign: 'center', color: '#475569' }}>No bookings found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <AnimatePresence>
        {/* New Booking Modal */}
        {isModalOpen && (
          <div style={overlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={modal}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
                <div>
                  <p style={eyebrow}>Front Office</p>
                  <h3 style={{ margin: 0 }}>New Booking</h3>
                </div>
                <X style={{ cursor: 'pointer' }} onClick={() => setIsModalOpen(false)} />
              </div>

              <form onSubmit={handleCreateBooking} style={{ maxHeight: '78vh', overflowY: 'auto', paddingRight: 10, display: 'flex', flexDirection: 'column', gap: 20 }}>
                
                <div style={formGrid}>
                  {/* Section 1: Guest Information */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>1</span>
                      <h4 style={sectionTitle}>Guest Information / የእንግዳ መረጃ</h4>
                    </div>
                    <div style={grid2}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Full Name / ሙሉ ስም *</label>
                        <input style={formInput} required value={form.guest_name} onChange={e => setForm({ ...form, guest_name: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Gender / ፆታ</label>
                        <select style={formInput} value={form.gender} onChange={e => setForm({ ...form, gender: e.target.value })}>
                          <option value="Male">Male / ወንድ</option>
                          <option value="Female">Female / ሴት</option>
                        </select>
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Nationality / ዜግነት</label>
                        <input style={formInput} value={form.nationality} onChange={e => setForm({ ...form, nationality: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Date of Birth / የትውልድ ቀን</label>
                        <input type="date" style={formInput} value={form.dob} onChange={e => setForm({ ...form, dob: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Phone / ስልክ</label>
                        <input style={formInput} value={form.guest_phone} onChange={e => setForm({ ...form, guest_phone: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Email / ኢሜል</label>
                        <input type="email" style={formInput} value={form.guest_email} onChange={e => setForm({ ...form, guest_email: e.target.value })} />
                      </div>
                    </div>
                  </div>

                  {/* Section 2: Identification Details */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>2</span>
                      <h4 style={sectionTitle}>Identification Details / የመታወቂያ መረጃ</h4>
                    </div>
                    <div style={grid2}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>ID Type / የመታወቂያ አይነት</label>
                        <select style={formInput} value={form.id_type} onChange={e => setForm({ ...form, id_type: e.target.value })}>
                          <option value="Passport">Passport</option>
                          <option value="Kebele ID">Kebele ID</option>
                          <option value="Driving License">Driving License</option>
                          <option value="Other">Other</option>
                        </select>
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>ID Number / የመታወቂያ ቁጥር</label>
                        <input style={formInput} value={form.id_number} onChange={e => setForm({ ...form, id_number: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Place of Issue / የተሰጠበት ቦታ</label>
                        <input style={formInput} value={form.id_issue_place} onChange={e => setForm({ ...form, id_issue_place: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Date of Issue / የተሰጠበት ቀን</label>
                        <input type="date" style={formInput} value={form.id_issue_date} onChange={e => setForm({ ...form, id_issue_date: e.target.value })} />
                      </div>
                    </div>
                  </div>

                  {/* Section 3: Address Information */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>3</span>
                      <h4 style={sectionTitle}>Address Information / አድራሻ</h4>
                    </div>
                    <div style={grid3}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Country / ሀገር</label>
                        <input style={formInput} value={form.country} onChange={e => setForm({ ...form, country: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>City / ከተማ</label>
                        <input style={formInput} value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Sub City / Kebele</label>
                        <input style={formInput} value={form.sub_city} onChange={e => setForm({ ...form, sub_city: e.target.value })} />
                      </div>
                    </div>
                  </div>

                  {/* Section 4: Stay Details */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>4</span>
                      <h4 style={sectionTitle}>Stay Details / የቆይታ ዝርዝር</h4>
                    </div>
                    <div style={grid2}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Check-in Date *</label>
                        <input type="date" style={formInput} required value={form.check_in_date} onChange={e => setForm({ ...form, check_in_date: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Check-out Date *</label>
                        <input type="date" style={formInput} required value={form.check_out_date} onChange={e => setForm({ ...form, check_out_date: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Number of Nights</label>
                        <input type="number" min="1" style={formInput} value={form.nights} onChange={e => setForm({ ...form, nights: e.target.value })} />
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div style={inputGroup}>
                          <label style={labelStyle}>Adults</label>
                          <input type="number" min="1" style={formInput} value={form.adults} onChange={e => setForm({ ...form, adults: e.target.value })} />
                        </div>
                        <div style={inputGroup}>
                          <label style={labelStyle}>Children</label>
                          <input type="number" min="0" style={formInput} value={form.children} onChange={e => setForm({ ...form, children: e.target.value })} />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Section 5: Room Details */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>5</span>
                      <h4 style={sectionTitle}>Room Details / የክፍል መረጃ</h4>
                    </div>
                    <div style={grid2}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Select Room *</label>
                        <select style={formInput} required value={selectedRoomId} onChange={e => setSelectedRoomId(e.target.value)}>
                          <option value="">Select Room</option>
                          {availableRooms.map(r => (
                            <option key={r.id} value={r.id}>#{r.room_number} — {r.name} ({r.room_type})</option>
                          ))}
                        </select>
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Rate (ETB)</label>
                        <input style={formInput} disabled value={availableRooms.find(r => r.id === Number(selectedRoomId))?.base_price || ''} />
                      </div>
                      <div style={{...inputGroup, gridColumn: 'span 2'}}>
                        <label style={labelStyle}>Source</label>
                        <select style={formInput} value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}>
                          {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>)}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Section 6: Payment Information */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>6</span>
                      <h4 style={sectionTitle}>Payment Information / የክፍያ መረጃ</h4>
                    </div>
                    <div style={grid3}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Payment Method</label>
                        <select style={formInput} value={form.payment_method} onChange={e => setForm({ ...form, payment_method: e.target.value })}>
                          <option value="Cash">Cash</option>
                          <option value="Card">Card</option>
                          <option value="Transfer">Transfer</option>
                          <option value="Chapa">Chapa Link</option>
                        </select>
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Advance Paid (ETB)</label>
                        <input type="number" style={formInput} value={form.advance_paid} onChange={e => setForm({ ...form, advance_paid: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Balance (ETB)</label>
                        <input type="number" style={formInput} value={form.balance} onChange={e => setForm({ ...form, balance: e.target.value })} />
                      </div>
                    </div>
                  </div>

                  {/* Section 7: Emergency Contact */}
                  <div style={formSection}>
                    <div style={sectionHeader}>
                      <span style={sectionNumber}>7</span>
                      <h4 style={sectionTitle}>Emergency Contact / የአደጋ ጊዜ ተጠሪ</h4>
                    </div>
                    <div style={grid3}>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Name / ስም</label>
                        <input style={formInput} value={form.emergency_name} onChange={e => setForm({ ...form, emergency_name: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Phone / ስልክ</label>
                        <input style={formInput} value={form.emergency_phone} onChange={e => setForm({ ...form, emergency_phone: e.target.value })} />
                      </div>
                      <div style={inputGroup}>
                        <label style={labelStyle}>Relationship / ዝምድና</label>
                        <input style={formInput} value={form.emergency_relation} onChange={e => setForm({ ...form, emergency_relation: e.target.value })} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer Controls */}
                <div style={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={inputGroup}>
                    <label style={labelStyle}>Special Notes / ማስታወሻ</label>
                    <textarea style={{ ...formInput, minHeight: 60 }} placeholder="Any extra requirements..." value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
                  </div>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={{ display: 'flex', gap: 10, alignItems: 'center', color: '#cbd5e1', fontSize: 13, cursor: 'pointer' }}>
                      <input type="checkbox" checked={form.pay_now} onChange={e => setForm({ ...form, pay_now: e.target.checked })} style={{ width: 18, height: 18, accentColor: '#3b82f6' }} />
                      <span>Collect Chapa deposit immediately</span>
                    </label>
                    
                    <button type="submit" disabled={loading} style={{...saveBtn, width: 'auto', padding: '12px 30px', marginTop: 0}}>
                      {loading ? 'Processing...' : 'Confirm Registration'}
                    </button>
                  </div>
                </div>
              </form>
            </motion.div>
          </div>
        )}

        {/* Guest Profile Panel */}
        {selectedReservation && (
          <div style={overlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={{ ...modal, maxWidth: 640 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ margin: 0 }}>Guest Profile</h3>
                <X style={{ cursor: 'pointer' }} onClick={() => { setSelectedReservation(null); setShowHistoryPanel(false); }} />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                {[
                  ['Guest Name', selectedReservation.guest_name],
                  ['Phone', selectedReservation.guest_phone || '—'],
                  ['Check-In', selectedReservation.check_in_date],
                  ['Check-Out', selectedReservation.check_out_date],
                  ['Room', `#${selectedReservation.room_number} — ${selectedReservation.room_name}`],
                  ['Status', selectedReservation.status],
                  ['Total Amount', `ETB ${selectedReservation.total_amount}`],
                  ['Payment', selectedReservation.payment_status],
                  ['Confirmation', selectedReservation.confirmation_code],
                  ['Source', selectedReservation.source],
                ].map(([label, value]) => (
                  <div key={label} style={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 12, padding: 12 }}>
                    <small style={{ display: 'block', fontSize: 9, fontWeight: 800, color: '#64748b', marginBottom: 4, textTransform: 'uppercase' }}>{label}</small>
                    <strong style={{ fontSize: 13 }}>{value}</strong>
                  </div>
                ))}
              </div>

              {guestHistory.length > 0 && (
                <>
                  <p style={sectionLabel}>Past Stay History</p>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {guestHistory.slice(0, 5).map(g => (
                      <div key={g.id} style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, padding: 10, fontSize: 12, color: '#cbd5e1' }}>
                        <strong>{g.full_name}</strong> — {g.id_type}: {g.id_number || '—'} | {g.nationality || 'N/A'}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {selectedReservation.chapa_checkout_url && selectedReservation.payment_status !== 'paid' && (
                <button
                  onClick={() => handlePayDeposit(selectedReservation)}
                  style={{ ...saveBtn, marginTop: 16, backgroundColor: '#2563eb' }}
                >
                  <CreditCard size={16} /> Pay Chapa Deposit
                </button>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Styles
const heroCard = { background: 'linear-gradient(135deg,rgba(15,23,42,0.95) 0%,rgba(30,41,59,0.95) 50%,rgba(14,116,144,0.85) 100%)', border: '1px solid rgba(56,189,248,0.18)', borderRadius: 24, padding: 24, marginBottom: 22, display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20 };
const eyebrow = { margin: 0, color: '#7dd3fc', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700 };
const pill = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 999, backgroundColor: 'rgba(15,23,42,0.45)', border: '1px solid rgba(125,211,252,0.22)', color: '#e0f2fe', fontSize: 12, fontWeight: 600 };
const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 15, marginBottom: 22 };
const statCard = { backgroundColor: '#fff', padding: 15, borderRadius: 15, display: 'flex', alignItems: 'center', gap: 12 };
const searchBox = { display: 'flex', alignItems: 'center', gap: 8, backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, padding: '10px 14px', flex: 1, maxWidth: 360 };
const searchInput = { background: 'none', border: 'none', color: '#fff', outline: 'none', fontSize: 13, width: '100%' };
const selectStyle = { backgroundColor: '#0f172a', border: '1px solid #1e293b', color: '#cbd5e1', padding: '10px 14px', borderRadius: 10, fontSize: 13, cursor: 'pointer' };
const addBtn = { backgroundColor: '#3f5d45', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: 30, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 };
const tableWrap = { backgroundColor: '#0f172a', borderRadius: 16, border: '1px solid #1e293b', overflow: 'hidden' };
const th = { padding: '14px 16px', fontSize: 11, fontWeight: 700, color: '#64748b', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.06em' };
const td = { padding: '12px 16px', fontSize: 13 };
const iconBtn = { backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid #1e293b', color: '#cbd5e1', borderRadius: 8, padding: '6px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center' };
const overlay = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: 20 };
const modal = { backgroundColor: '#0f172a', padding: '30px 30px 20px', borderRadius: 24, width: 'min(1000px, 95vw)', border: '1px solid #334155', maxHeight: '92vh', display: 'flex', flexDirection: 'column' };
const sectionLabel = { margin: '8px 0 4px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#7dd3fc', letterSpacing: '0.08em' };
const grid2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 };
const grid3 = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 };
const inp = { backgroundColor: '#1e293b', border: '1px solid #334155', color: '#fff', padding: 11, borderRadius: 10, width: '100%', boxSizing: 'border-box', fontSize: 13 };
const saveBtn = { width: '100%', backgroundColor: '#bef264', color: '#000', border: 'none', padding: 14, borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 14 };

// New Form Styles
const formGrid = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' };
const formSection = { backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 16, padding: '20px 20px 24px' };
const sectionHeader = { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18, borderBottom: '1px solid #1e293b', paddingBottom: 12 };
const sectionNumber = { backgroundColor: '#38bdf8', color: '#0f172a', width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 };
const sectionTitle = { margin: 0, fontSize: 14, color: '#f8fafc', fontWeight: 600 };
const inputGroup = { display: 'flex', flexDirection: 'column', gap: 6 };
const labelStyle = { fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' };
const formInput = { backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', padding: '10px 14px', borderRadius: 10, fontSize: 13, outline: 'none', transition: 'border-color 0.2s' };
