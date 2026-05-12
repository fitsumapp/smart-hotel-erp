import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CalendarDays, ExternalLink, Globe, Hotel, LoaderCircle, ShieldCheck, Sparkles, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { API_BASE_URL, getTenantSchemaHint } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const initialBooking = {
  guest_name: '',
  guest_email: '',
  guest_phone: '',
  check_in_date: '',
  check_out_date: '',
  adults: 1,
  children: 0,
  notes: '',
};

const CustomerDashboard = () => {
  const tenantSchema = getTenantSchemaHint();
  const [rooms, setRooms] = useState([]);
  const [filters, setFilters] = useState({ check_in_date: '', check_out_date: '' });
  const [booking, setBooking] = useState(initialBooking);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [message, setMessage] = useState('');
  const [photoViewer, setPhotoViewer] = useState({ open: false, photos: [], currentIndex: 0 });

  useEffect(() => {
    fetchRooms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.check_in_date, filters.check_out_date]);

  const fetchRooms = async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (filters.check_in_date) query.set('check_in_date', filters.check_in_date);
      if (filters.check_out_date) query.set('check_out_date', filters.check_out_date);
      if (tenantSchema) query.set('tenant', tenantSchema);
      const res = await axios.get(`${API_BASE}public-booking/rooms/?${query.toString()}`, {
        headers: tenantSchema ? { 'X-Tenant-Schema': tenantSchema } : {},
      });
      setRooms(res.data);
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to load rooms right now.');
    } finally {
      setLoading(false);
    }
  };

  const openBooking = (room) => {
    setSelectedRoom(room);
    setBooking((prev) => ({
      ...prev,
      check_in_date: filters.check_in_date || prev.check_in_date,
      check_out_date: filters.check_out_date || prev.check_out_date,
    }));
    setMessage('');
  };

  const openPhotoViewer = (photos, idx) => setPhotoViewer({ open: true, photos, currentIndex: idx });
  const closePhotoViewer = () => setPhotoViewer({ open: false, photos: [], currentIndex: 0 });
  const nextPhoto = (e) => { e.stopPropagation(); setPhotoViewer(prev => ({...prev, currentIndex: (prev.currentIndex + 1) % prev.photos.length})); };
  const prevPhoto = (e) => { e.stopPropagation(); setPhotoViewer(prev => ({...prev, currentIndex: (prev.currentIndex - 1 + prev.photos.length) % prev.photos.length})); };

  const closeBooking = () => {
    setSelectedRoom(null);
    setBooking(initialBooking);
    setPaying(false);
  };

  const computedDeposit = useMemo(() => {
    if (!selectedRoom) return '0.00';
    const basePrice = Number(selectedRoom.base_price || 0);
    const depositAmount = Number(selectedRoom.deposit_amount || 0);
    if (selectedRoom.deposit_type === 'Percentage') {
      return ((basePrice * depositAmount) / 100).toFixed(2);
    }
    return depositAmount > 0 ? depositAmount.toFixed(2) : basePrice.toFixed(2);
  }, [selectedRoom]);

  const submitReservation = async () => {
    if (!selectedRoom) return;
    setPaying(true);
    setMessage('');
    try {
      const res = await axios.post(`${API_BASE}public-booking/rooms/${selectedRoom.id}/reserve/`, {
        ...booking,
        tenant: tenantSchema,
      }, {
        headers: tenantSchema ? { 'X-Tenant-Schema': tenantSchema } : {},
      });
      window.location.href = res.data.checkout_url;
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to create reservation.');
      setPaying(false);
    }
  };

  return (
    <div style={styles.page}>
      <section style={styles.hero}>
        <div>
          <p style={styles.kicker}>Public Booking Engine</p>
          <h1 style={styles.title}>Book your room online, pay securely, and arrive with QR confirmation.</h1>
          <p style={styles.subtitle}>
            Browse available rooms, choose your stay dates, pay the required deposit with Chapa, and receive a confirmation code for fast reception check-in.
          </p>
        </div>
        <div style={styles.heroStack}>
          <FeaturePill icon={<Globe size={14} />} text="Live availability validation" />
          <FeaturePill icon={<ShieldCheck size={14} />} text="Secure Chapa payment redirect" />
          <FeaturePill icon={<Sparkles size={14} />} text="Confirmation with QR check-in" />
        </div>
      </section>

      <section style={styles.searchBar}>
        <div style={styles.searchField}>
          <label style={styles.label}>Check-in</label>
          <input type="date" value={filters.check_in_date} onChange={(e) => setFilters({ ...filters, check_in_date: e.target.value })} style={styles.input} />
        </div>
        <div style={styles.searchField}>
          <label style={styles.label}>Check-out</label>
          <input type="date" value={filters.check_out_date} onChange={(e) => setFilters({ ...filters, check_out_date: e.target.value })} style={styles.input} />
        </div>
      </section>

      {loading ? <div style={styles.loader}><LoaderCircle size={20} /> Loading available rooms...</div> : null}
      {message && !selectedRoom ? <div style={styles.message}>{message}</div> : null}

      <section style={styles.grid}>
        {rooms.map((room) => {
          const photos = [room.main_image, room.image_2, room.image_3].filter(Boolean);
          return (
            <article key={room.id} style={styles.card}>
              <div style={styles.imageShell}>
                {photos.length > 0 ? (
                  <div style={photos.length > 1 ? styles.multiImgGrid : styles.singleImgBox}>
                    {photos.map((p, idx) => (
                      <div key={idx} style={{ ...(photos.length > 1 && idx === 0 ? { gridColumn: 'span 2', gridRow: 'span 2' } : {}), overflow: 'hidden' }}>
                        <img 
                          src={p} 
                          alt={room.name} 
                          onClick={() => openPhotoViewer(photos, idx)}
                          style={{...styles.image, cursor: 'pointer', transition: 'transform 0.3s ease'}} 
                          onMouseOver={e => e.currentTarget.style.transform = 'scale(1.05)'}
                          onMouseOut={e => e.currentTarget.style.transform = 'scale(1)'}
                        />
                      </div>
                    ))}
                  </div>
                ) : <div style={styles.imageFallback}><Hotel size={24} /></div>}
                <div style={styles.priceTag}>ETB {Number(room.base_price || 0).toFixed(2)}</div>
              </div>
              <div style={styles.body}>
              <div style={styles.roomHead}>
                <div>
                  <h3 style={styles.roomName}>{room.name}</h3>
                  <p style={styles.roomMeta}>Room {room.room_number} • {room.room_type}</p>
                </div>
                <span style={room.is_available ? styles.available : styles.unavailable}>{room.is_available ? 'Available' : 'Reserved'}</span>
              </div>
              <p style={styles.description}>{room.description || 'Comfortable room prepared for online booking.'}</p>
              {!room.is_online_enabled ? <div style={styles.fallbackNote}>Visible because no rooms are explicitly marked online yet.</div> : null}
              <div style={styles.amenities}>
                {(room.common_amenities || []).map((item) => <span key={`${room.id}-${item}`} style={styles.amenity}>{item}</span>)}
              </div>
              <div style={styles.detailGrid}>
                <div style={styles.detailBox}><strong>Adults</strong><span>{room.max_adults}</span></div>
                <div style={styles.detailBox}><strong>Children</strong><span>{room.max_children}</span></div>
                <div style={styles.detailBox}><strong>Check-in</strong><span>{room.check_in_time}</span></div>
                <div style={styles.detailBox}><strong>Check-out</strong><span>{room.check_out_time}</span></div>
              </div>
              <button style={{ ...styles.reserveBtn, opacity: room.is_available ? 1 : 0.45 }} disabled={!room.is_available} onClick={() => openBooking(room)}>
                <CalendarDays size={16} />
                Reserve Now
              </button>
            </div>
          </article>
          );
        })}
      </section>
      {!loading && rooms.length === 0 ? <div style={styles.message}>No rooms are available yet. Add rooms first from the admin side.</div> : null}

      {selectedRoom ? (
        <div style={styles.overlay}>
          <div style={styles.modal}>
            <div style={styles.modalHead}>
              <div>
                <p style={styles.kicker}>Reserve Now</p>
                <h2 style={{ margin: '6px 0 0' }}>{selectedRoom.name}</h2>
              </div>
              <button onClick={closeBooking} style={styles.closeBtn}>Close</button>
            </div>

            <div style={styles.modalInfo}>
              <div style={styles.depositCard}>
                <small>Deposit due now</small>
                <strong>ETB {computedDeposit}</strong>
                <span>{selectedRoom.deposit_type === 'Percentage' ? `${selectedRoom.deposit_amount}% upfront` : 'Fixed advance payment'}</span>
              </div>
              <div style={styles.depositCard}>
                <small>Total room rate</small>
                <strong>ETB {Number(selectedRoom.base_price || 0).toFixed(2)}</strong>
                <span>Per night before add-ons</span>
              </div>
            </div>

            <div style={styles.formGrid}>
              <input placeholder="Guest full name" value={booking.guest_name} onChange={(e) => setBooking({ ...booking, guest_name: e.target.value })} style={styles.input} />
              <input placeholder="Phone number" value={booking.guest_phone} onChange={(e) => setBooking({ ...booking, guest_phone: e.target.value })} style={styles.input} />
              <input placeholder="Email address" value={booking.guest_email} onChange={(e) => setBooking({ ...booking, guest_email: e.target.value })} style={styles.input} />
              <input type="date" value={booking.check_in_date} onChange={(e) => setBooking({ ...booking, check_in_date: e.target.value })} style={styles.input} />
              <input type="date" value={booking.check_out_date} onChange={(e) => setBooking({ ...booking, check_out_date: e.target.value })} style={styles.input} />
              <input type="number" min="1" value={booking.adults} onChange={(e) => setBooking({ ...booking, adults: e.target.value })} style={styles.input} placeholder="Adults" />
              <input type="number" min="0" value={booking.children} onChange={(e) => setBooking({ ...booking, children: e.target.value })} style={styles.input} placeholder="Children" />
              <textarea placeholder="Special requests" value={booking.notes} onChange={(e) => setBooking({ ...booking, notes: e.target.value })} style={{ ...styles.input, minHeight: 110, gridColumn: '1 / -1' }} />
            </div>

            {message ? <div style={styles.message}>{message}</div> : null}

            <button onClick={submitReservation} style={styles.payBtn} disabled={paying}>
              <ExternalLink size={16} />
              {paying ? 'Redirecting to Chapa...' : 'Pay Deposit and Confirm'}
            </button>
          </div>
        </div>
      ) : null}

      {/* Photo Viewer Modal */}
      {photoViewer.open && photoViewer.photos.length > 0 && (
        <div style={{...styles.overlay, zIndex: 1000}} onClick={closePhotoViewer}>
          <div style={{position: 'absolute', top: 20, right: 20, cursor: 'pointer', backgroundColor: 'rgba(0,0,0,0.5)', borderRadius: '50%', padding: 10, zIndex: 1010}} onClick={(e) => { e.stopPropagation(); closePhotoViewer(); }}>
            <X size={24} color="#fff" />
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%', position: 'relative' }} onClick={e => e.stopPropagation()}>
            {photoViewer.photos.length > 1 && (
              <button onClick={prevPhoto} style={styles.navBtnLeft}><ChevronLeft size={36} color="#000" /></button>
            )}
            
            <img 
              src={photoViewer.photos[photoViewer.currentIndex]} 
              alt="Room" 
              style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain', borderRadius: 16, boxShadow: '0 20px 50px rgba(0,0,0,0.5)' }} 
            />
            
            {photoViewer.photos.length > 1 && (
              <button onClick={nextPhoto} style={styles.navBtnRight}><ChevronRight size={36} color="#000" /></button>
            )}
            
            <div style={{ position: 'absolute', bottom: 20, backgroundColor: 'rgba(0,0,0,0.6)', color: '#fff', padding: '6px 14px', borderRadius: 20, fontSize: 14, fontWeight: 700 }}>
              {photoViewer.currentIndex + 1} / {photoViewer.photos.length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const FeaturePill = ({ icon, text }) => (
  <span style={styles.featurePill}>{icon}{text}</span>
);

const styles = {
  page: { minHeight: '100vh', background: 'linear-gradient(180deg, #f8fafc 0%, #ecfeff 38%, #eff6ff 100%)', padding: 24, fontFamily: '"Segoe UI", sans-serif' },
  hero: { maxWidth: 1240, margin: '0 auto 24px', background: 'linear-gradient(135deg, #082f49, #0f766e 60%, #14b8a6)', color: '#fff', borderRadius: 32, padding: 28, display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 24 },
  kicker: { margin: 0, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 800, opacity: 0.9 },
  title: { margin: '10px 0', fontSize: 42, lineHeight: 1.05, maxWidth: 760 },
  subtitle: { margin: 0, fontSize: 16, lineHeight: 1.7, color: 'rgba(255,255,255,0.9)', maxWidth: 720 },
  heroStack: { display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' },
  featurePill: { display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(255,255,255,0.14)', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 999, padding: '12px 16px', fontWeight: 700 },
  searchBar: { maxWidth: 1240, margin: '0 auto 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, background: '#fff', border: '1px solid #dbeafe', borderRadius: 24, padding: 18, boxShadow: '0 18px 40px rgba(14,116,144,0.08)' },
  searchField: { display: 'flex', flexDirection: 'column', gap: 8 },
  label: { fontWeight: 800, color: '#0f172a', fontSize: 13 },
  input: { width: '100%', boxSizing: 'border-box', border: '1px solid #cbd5e1', borderRadius: 16, padding: '14px 16px', fontSize: 14, outline: 'none', background: '#fff' },
  loader: { maxWidth: 1240, margin: '0 auto 20px', display: 'flex', gap: 8, alignItems: 'center', color: '#0f766e' },
  message: { maxWidth: 1240, margin: '12px auto', background: '#ecfeff', color: '#0f766e', borderRadius: 16, padding: 14, border: '1px solid #a5f3fc' },
  grid: { maxWidth: 1240, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 },
  card: { background: '#fff', border: '1px solid #dbeafe', borderRadius: 28, overflow: 'hidden', boxShadow: '0 20px 40px rgba(15,23,42,0.06)' },
  imageShell: { height: 220, background: '#e2e8f0', position: 'relative' },
  image: { width: '100%', height: '100%', objectFit: 'cover' },
  imageFallback: { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569' },
  priceTag: { position: 'absolute', top: 14, left: 14, background: 'rgba(8,47,73,0.85)', color: '#fff', padding: '8px 12px', borderRadius: 999, fontWeight: 800 },
  body: { padding: 20, display: 'flex', flexDirection: 'column', gap: 14 },
  roomHead: { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' },
  roomName: { margin: 0, fontSize: 24, color: '#0f172a' },
  roomMeta: { margin: '6px 0 0', color: '#64748b', fontSize: 13 },
  available: { background: '#dcfce7', color: '#166534', borderRadius: 999, padding: '6px 10px', fontSize: 12, fontWeight: 800 },
  unavailable: { background: '#e2e8f0', color: '#475569', borderRadius: 999, padding: '6px 10px', fontSize: 12, fontWeight: 800 },
  description: { margin: 0, color: '#475569', lineHeight: 1.6, minHeight: 48 },
  fallbackNote: { background: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa', borderRadius: 12, padding: '8px 10px', fontSize: 12, fontWeight: 700 },
  amenities: { display: 'flex', flexWrap: 'wrap', gap: 8 },
  amenity: { background: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4', borderRadius: 999, padding: '5px 10px', fontSize: 12, fontWeight: 700 },
  detailGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  detailBox: { background: '#f8fafc', borderRadius: 16, padding: 12, display: 'flex', flexDirection: 'column', gap: 5, color: '#334155' },
  reserveBtn: { border: 'none', background: '#0f766e', color: '#fff', borderRadius: 18, padding: '14px 18px', fontWeight: 800, display: 'inline-flex', gap: 8, alignItems: 'center', justifyContent: 'center', cursor: 'pointer' },
  overlay: { position: 'fixed', inset: 0, background: 'rgba(2,6,23,0.62)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 50 },
  modal: { width: 'min(860px, 100%)', background: '#fff', borderRadius: 30, padding: 24, display: 'flex', flexDirection: 'column', gap: 18, maxHeight: '92vh', overflowY: 'auto' },
  modalHead: { display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'start' },
  closeBtn: { border: '1px solid #cbd5e1', background: '#fff', borderRadius: 12, padding: '10px 14px', cursor: 'pointer', fontWeight: 700 },
  modalInfo: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  depositCard: { background: '#0f172a', color: '#fff', borderRadius: 20, padding: 18, display: 'flex', flexDirection: 'column', gap: 8 },
  formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  payBtn: { border: 'none', background: '#082f49', color: '#fff', borderRadius: 18, padding: '15px 18px', fontWeight: 800, display: 'inline-flex', gap: 8, alignItems: 'center', justifyContent: 'center', cursor: 'pointer' },
  singleImgBox: { width: '100%', height: '100%' },
  multiImgGrid: { display: 'grid', gridTemplateColumns: '2fr 1fr', gridTemplateRows: '1fr 1fr', gap: 2, height: '100%', width: '100%' },
  navBtnLeft: { position: 'absolute', left: 20, backgroundColor: 'rgba(255,255,255,0.8)', border: 'none', borderRadius: '50%', width: 50, height: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 10 },
  navBtnRight: { position: 'absolute', right: 20, backgroundColor: 'rgba(255,255,255,0.8)', border: 'none', borderRadius: '50%', width: 50, height: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 10 },
};

export default CustomerDashboard;
