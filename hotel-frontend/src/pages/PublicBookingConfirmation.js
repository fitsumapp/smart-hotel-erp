import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { QRCodeSVG } from 'qrcode.react';
import { CheckCircle2, LoaderCircle, ScanLine } from 'lucide-react';
import { useParams, useSearchParams } from 'react-router-dom';
import { API_BASE_URL, getTenantSchemaHint } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const PublicBookingConfirmation = () => {
  const { token } = useParams();
  const [searchParams] = useSearchParams();
  const tenantSchema = getTenantSchemaHint();
  const [reservation, setReservation] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchReservation();
  }, [token]);

  const fetchReservation = async () => {
    setLoading(true);
    try {
      const detail = await axios.get(`${API_BASE}reservations/public/${token}/`, {
        headers: tenantSchema ? { 'X-Tenant-Schema': tenantSchema } : {},
      });
      setReservation(detail.data);
      if (searchParams.get('payment') === 'returned') {
        await verifyPayment();
      }
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to load reservation.');
    } finally {
      setLoading(false);
    }
  };

  const verifyPayment = async () => {
    try {
      const txRef = searchParams.get('tx_ref') || searchParams.get('trx_ref');
      const res = await axios.post(`${API_BASE}reservations/public/${token}/verify/`, {
        tx_ref: txRef,
        tenant: tenantSchema,
      }, {
        headers: tenantSchema ? { 'X-Tenant-Schema': tenantSchema } : {},
      });
      setReservation(res.data.reservation);
      setMessage(res.data.message || 'Reservation confirmed successfully.');
    } catch (err) {
      if (err.response?.status === 202) {
        setMessage(err.response?.data?.message || 'Payment is still pending.');
      } else {
        setMessage(err.response?.data?.error || 'Unable to verify reservation payment.');
      }
    }
  };

  const simulateQRCheckIn = async () => {
    if (!reservation?.qr_token) return;
    setScanLoading(true);
    try {
      const res = await axios.post(`${API_BASE}reservations/qr-checkin/`, {
        qr_token: reservation.qr_token,
        tenant: tenantSchema,
      }, {
        headers: tenantSchema ? { 'X-Tenant-Schema': tenantSchema } : {},
      });
      setReservation(res.data.reservation);
      setMessage(res.data.message || 'Checked in successfully.');
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to process QR check-in.');
    } finally {
      setScanLoading(false);
    }
  };

  if (loading) {
    return <div style={styles.center}><LoaderCircle size={20} /> Loading reservation...</div>;
  }

  if (!reservation) {
    return <div style={styles.center}>{message || 'Reservation not found.'}</div>;
  }

  const qrValue = `${window.location.origin}/booking/${reservation.public_token}?qr=${reservation.qr_token}`;

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.header}>
          <small style={styles.kicker}>Reservation Confirmation</small>
          <h1 style={styles.title}>Room {reservation.room_number}</h1>
          <p style={styles.subtitle}>Show this QR code at reception for faster check-in. Your confirmation code is also included below.</p>
        </div>

        <div style={styles.banner}>
          <CheckCircle2 size={18} />
          <span>Status: {reservation.status} • Payment: {reservation.payment_status}</span>
        </div>

        <div style={styles.grid}>
          <div style={styles.summary}>
            <Row label="Guest" value={reservation.guest_name} />
            <Row label="Check-in" value={reservation.check_in_date} />
            <Row label="Check-out" value={reservation.check_out_date} />
            <Row label="Deposit paid" value={`ETB ${Number(reservation.deposit_amount || 0).toFixed(2)}`} />
            <Row label="Confirmation code" value={reservation.confirmation_code} strong />
          </div>

          <div style={styles.qrShell}>
            <div style={styles.qrCard}>
              <QRCodeSVG value={qrValue} size={210} />
            </div>
            <small style={{ color: '#475569', textAlign: 'center' }}>Reception can scan this QR to complete check-in instantly.</small>
          </div>
        </div>

        {message ? <div style={styles.message}>{message}</div> : null}

        <button style={styles.scanBtn} onClick={simulateQRCheckIn} disabled={scanLoading}>
          <ScanLine size={16} />
          {scanLoading ? 'Checking in...' : 'Test QR Check-in'}
        </button>
      </div>
    </div>
  );
};

const Row = ({ label, value, strong }) => (
  <div style={{ ...styles.row, fontWeight: strong ? 800 : 600 }}>
    <span>{label}</span>
    <span>{value}</span>
  </div>
);

const styles = {
  page: { minHeight: '100vh', background: 'linear-gradient(135deg, #ecfeff, #eef2ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, fontFamily: '"Segoe UI", sans-serif' },
  card: { width: 'min(920px, 100%)', background: '#fff', borderRadius: 30, border: '1px solid #c7d2fe', boxShadow: '0 24px 60px rgba(15,23,42,0.08)', padding: 24, display: 'flex', flexDirection: 'column', gap: 18 },
  header: { display: 'flex', flexDirection: 'column', gap: 6 },
  kicker: { textTransform: 'uppercase', letterSpacing: '0.12em', color: '#0f766e', fontWeight: 800 },
  title: { margin: 0, fontSize: 34 },
  subtitle: { margin: 0, color: '#475569', lineHeight: 1.6 },
  banner: { display: 'inline-flex', gap: 8, alignItems: 'center', alignSelf: 'start', background: '#dcfce7', color: '#166534', borderRadius: 999, padding: '10px 14px', fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 18 },
  summary: { background: '#f8fafc', borderRadius: 24, padding: 18, display: 'flex', flexDirection: 'column', gap: 12 },
  qrShell: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 },
  qrCard: { background: '#fff', border: '1px solid #dbeafe', borderRadius: 28, padding: 18, boxShadow: '0 14px 30px rgba(14,116,144,0.06)' },
  message: { background: '#eff6ff', color: '#1d4ed8', borderRadius: 16, padding: 12, border: '1px solid #bfdbfe' },
  scanBtn: { border: 'none', background: '#0f172a', color: '#fff', borderRadius: 18, padding: '14px 18px', fontWeight: 800, display: 'inline-flex', gap: 8, alignItems: 'center', justifyContent: 'center', cursor: 'pointer' },
  row: { display: 'flex', justifyContent: 'space-between', gap: 12, color: '#0f172a' },
  center: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: '"Segoe UI", sans-serif' },
};

export default PublicBookingConfirmation;
