import React, { useState } from 'react';
import axios from 'axios';
import { 
  QrCode, Search, User, Calendar, Bed, CheckCircle, 
  ArrowRight, Loader2, X, Phone, Mail, Clock, Wallet
} from 'lucide-react';
import { API_BASE_URL } from '../apiConfig';

const ReceptionDashboard = ({ userData, handleLogout }) => {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [reservation, setReservation] = useState(null);
  const [error, setError] = useState('');

  const handleCheckIn = async (e) => {
    if (e) e.preventDefault();
    if (!code) return;

    setLoading(true);
    setError('');
    setReservation(null);
    console.log("Checking in with code:", code);

    try {
      const res = await axios.post(`${API_BASE_URL}/users/reservations/qr-checkin/`, {
        qr_token: code
      });
      console.log("Reservation Found:", res.data.reservation);
      setReservation(res.data.reservation);
      setCode('');
    } catch (err) {
      console.error("Check-in Error:", err);
      setError(err.response?.data?.error || 'Invalid code or reservation not found.');
    } finally {
      setLoading(false);
    }
  };

  const closeOverlay = () => {
    setReservation(null);
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Reception Dashboard</h1>
          <p style={styles.subtitle}>Unified Front Desk & QR Check-In</p>
        </div>
        <div style={styles.userSection}>
          <div style={styles.userInfo}>
            <p style={styles.userName}>{userData?.username || 'Receptionist'}</p>
            <p style={styles.userRole}>Front Desk</p>
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
        </div>
      </header>

      <main style={styles.main}>
        <div style={styles.searchCard}>
          <div style={styles.cardIcon}>
            <QrCode size={32} color="#22d3ee" />
          </div>
          <h2 style={styles.cardTitle}>Guest Check-In</h2>
          <p style={styles.cardSub}>Enter confirmation code or scan guest QR</p>
          
          <form onSubmit={handleCheckIn} style={styles.form}>
            <div style={styles.inputWrapper}>
              <Search style={styles.searchIcon} size={20} />
              <input 
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="TOKEN OR CODE"
                style={styles.input}
              />
            </div>
            <button disabled={loading} style={styles.submitBtn}>
              {loading ? 'Validating...' : 'Verify & Check-In'}
              <ArrowRight size={20} />
            </button>
          </form>

          {error && <div style={styles.error}>{error}</div>}
        </div>
      </main>

      {/* Manual Modal Implementation */}
      {reservation && (
        <div style={styles.overlay} onClick={closeOverlay}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div style={styles.badge}>
                <CheckCircle size={16} /> SUCCESSFUL CHECK-IN
              </div>
              <button onClick={closeOverlay} style={styles.closeBtn}><X size={24}/></button>
            </div>

            <div style={styles.modalHero}>
              <div style={styles.guestIcon}><User size={40} color="#fff" /></div>
              <h2 style={styles.guestName}>{reservation.guest_name}</h2>
              <div style={styles.statusPill}>CHECKED IN</div>
            </div>

            <div style={styles.detailsGrid}>
              <DetailBox icon={<Bed size={18}/>} label="Room" value={reservation.room_name} sub={`Room ${reservation.room_number}`} />
              <DetailBox icon={<Calendar size={18}/>} label="Stay" value={`${reservation.check_in_date}`} sub={`to ${reservation.check_out_date}`} />
              <DetailBox icon={<Wallet size={18}/>} label="Payment" value={`ETB ${reservation.total_amount}`} sub={reservation.payment_status?.toUpperCase()} />
              <DetailBox icon={<Clock size={18}/>} label="Registry" value={new Date().toLocaleTimeString()} sub="Live Check-in" />
            </div>

            <div style={styles.contactRow}>
              {reservation.guest_phone && (
                <div style={styles.contactItem}><Phone size={14} /> {reservation.guest_phone}</div>
              )}
              {reservation.guest_email && (
                <div style={styles.contactItem}><Mail size={14} /> {reservation.guest_email}</div>
              )}
            </div>

            <div style={styles.modalFooter}>
              <p style={styles.footerNote}>Code: {reservation.confirmation_code}</p>
              <button onClick={closeOverlay} style={styles.doneBtn}>Done</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const DetailBox = ({ icon, label, value, sub }) => (
  <div style={styles.detailBox}>
    <div style={styles.detailIcon}>{icon}</div>
    <div style={{ textAlign: 'left' }}>
      <small style={styles.detailLabel}>{label}</small>
      <p style={styles.detailValue}>{value}</p>
      {sub && <small style={styles.detailSub}>{sub}</small>}
    </div>
  </div>
);

const styles = {
  container: { minHeight: '100vh', backgroundColor: '#020617', color: '#fff', fontFamily: 'sans-serif' },
  header: { height: '70px', borderBottom: '1px solid #1e293b', padding: '0 30px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#0f172a' },
  title: { margin: 0, fontSize: '18px', fontWeight: 'bold' },
  subtitle: { margin: 0, fontSize: '11px', color: '#64748b' },
  userSection: { display: 'flex', alignItems: 'center', gap: '15px' },
  userInfo: { textAlign: 'right' },
  userName: { margin: 0, fontSize: '13px', fontWeight: '600' },
  userRole: { margin: 0, fontSize: '10px', color: '#22d3ee' },
  logoutBtn: { backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', padding: '5px 10px', borderRadius: '5px', cursor: 'pointer' },
  main: { padding: '60px 20px', display: 'flex', justifyContent: 'center' },
  searchCard: { width: '100%', maxWidth: '450px', backgroundColor: '#0f172a', borderRadius: '24px', padding: '35px', border: '1px solid #1e293b', textAlign: 'center' },
  cardIcon: { width: '60px', height: '60px', backgroundColor: 'rgba(34, 211, 238, 0.1)', borderRadius: '15px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' },
  cardTitle: { fontSize: '24px', fontWeight: 'bold', margin: '0 0 10px' },
  cardSub: { color: '#94a3b8', fontSize: '13px', marginBottom: '30px' },
  form: { display: 'flex', flexDirection: 'column', gap: '15px' },
  inputWrapper: { position: 'relative' },
  searchIcon: { position: 'absolute', left: '15px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' },
  input: { width: '100%', boxSizing: 'border-box', backgroundColor: '#020617', border: '1px solid #334155', borderRadius: '12px', padding: '15px 15px 15px 45px', color: '#fff', fontSize: '16px', outline: 'none' },
  submitBtn: { width: '100%', backgroundColor: '#22d3ee', color: '#020617', border: 'none', borderRadius: '12px', padding: '15px', fontSize: '15px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' },
  error: { marginTop: '15px', color: '#ef4444', fontSize: '13px', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '10px', borderRadius: '8px' },
  overlay: { position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
  modal: { width: '90%', maxWidth: '550px', backgroundColor: '#0f172a', borderRadius: '24px', border: '1px solid #1e293b', overflow: 'hidden' },
  modalHeader: { padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b' },
  badge: { display: 'flex', alignItems: 'center', gap: '5px', color: '#10b981', fontSize: '12px', fontWeight: 'bold' },
  closeBtn: { backgroundColor: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' },
  modalHero: { textAlign: 'center', padding: '30px 20px' },
  guestIcon: { width: '70px', height: '70px', backgroundColor: '#22d3ee', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 15px' },
  guestName: { fontSize: '28px', margin: '0 0 10px' },
  statusPill: { display: 'inline-block', backgroundColor: '#10b981', color: '#fff', padding: '3px 12px', borderRadius: '5px', fontSize: '10px', fontWeight: 'bold' },
  detailsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', backgroundColor: '#1e293b' },
  detailBox: { padding: '20px', backgroundColor: '#0f172a', display: 'flex', gap: '12px' },
  detailIcon: { color: '#94a3b8' },
  detailLabel: { display: 'block', color: '#64748b', fontSize: '10px', textTransform: 'uppercase' },
  detailValue: { margin: 0, fontSize: '14px', fontWeight: 'bold' },
  detailSub: { fontSize: '11px', color: '#22d3ee' },
  contactRow: { display: 'flex', justifyContent: 'center', gap: '20px', padding: '20px', color: '#94a3b8', fontSize: '12px' },
  contactItem: { display: 'flex', alignItems: 'center', gap: '5px' },
  modalFooter: { padding: '20px', backgroundColor: '#020617', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  footerNote: { margin: 0, fontSize: '12px', color: '#64748b' },
  doneBtn: { backgroundColor: '#fff', color: '#020617', border: 'none', borderRadius: '8px', padding: '10px 25px', fontWeight: 'bold', cursor: 'pointer' },
};

export default ReceptionDashboard;
