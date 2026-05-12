import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ExternalLink, LoaderCircle } from 'lucide-react';
import { useParams, useSearchParams } from 'react-router-dom';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const CustomerPaymentPage = () => {
  const { token } = useParams();
  const [searchParams] = useSearchParams();
  const [paymentInfo, setPaymentInfo] = useState(null);
  const [tipAmount, setTipAmount] = useState('0');
  const [customer, setCustomer] = useState({ first_name: 'Guest', last_name: 'Customer', email: '' });
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchPaymentInfo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, searchParams]);

  const fetchPaymentInfo = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}payments/public/${token}/`);
      setPaymentInfo(res.data);
      setTipAmount(String(res.data.tip_amount || 0));
      if (searchParams.get('payment') === 'returned') {
        setMessage('Welcome back. Checking payment status now...');
        await verifyReturnedPayment();
      }
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to load payment information.');
    } finally {
      setLoading(false);
    }
  };

  const finalAmount = useMemo(() => {
    const base = Number(paymentInfo?.grand_total || 0);
    const tip = Number(tipAmount || 0);
    return (base + (tip > 0 ? tip : 0)).toFixed(2);
  }, [paymentInfo, tipAmount]);

  const initiatePayment = async () => {
    setPaying(true);
    setMessage('');
    try {
      const res = await axios.post(`${API_BASE}payments/public/${token}/initiate/`, {
        tip_amount: tipAmount,
        ...customer,
      });
      window.location.href = res.data.checkout_url;
    } catch (err) {
      setMessage(err.response?.data?.error || 'Unable to start Chapa payment.');
      setPaying(false);
    }
  };

  const verifyReturnedPayment = async () => {
    try {
      const txRef = searchParams.get('tx_ref') || searchParams.get('trx_ref');
      const res = await axios.post(`${API_BASE}payments/public/${token}/verify/`, {
        tx_ref: txRef,
      });
      setMessage(res.data?.message || 'Payment verified successfully.');
      const refreshed = await axios.get(`${API_BASE}payments/public/${token}/`);
      setPaymentInfo(refreshed.data);
      setTipAmount(String(refreshed.data.tip_amount || 0));
    } catch (err) {
      if (err.response?.status === 202) {
        setMessage(err.response?.data?.message || 'Payment is still pending.');
      } else {
        setMessage(err.response?.data?.error || 'Unable to verify payment yet.');
      }
    }
  };

  if (loading) {
    return <div style={styles.center}><LoaderCircle size={22} /> Loading payment page...</div>;
  }

  if (!paymentInfo) {
    return <div style={styles.center}>{message || 'Payment page unavailable.'}</div>;
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.header}>
          <small style={styles.kicker}>Digital Checkout</small>
          <h1 style={styles.title}>Table {paymentInfo.table_code}</h1>
          <p style={styles.subtitle}>Grand total is locked. Tip stays separate from hotel taxable revenue.</p>
        </div>

        <div style={styles.summaryBox}>
          <SummaryRow label="Sub-total" value={paymentInfo.sub_total} />
          <SummaryRow label="VAT" value={paymentInfo.vat} />
          <SummaryRow label="Service Charge" value={paymentInfo.service_charge} />
          <SummaryRow label="Grand Total" value={paymentInfo.grand_total} strong />
        </div>

        <div style={styles.formSection}>
          <label style={styles.label}>Add a Tip</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={tipAmount}
            onChange={(e) => setTipAmount(e.target.value)}
            style={styles.input}
          />
        </div>

        <div style={styles.grid}>
          <input
            placeholder="First name"
            value={customer.first_name}
            onChange={(e) => setCustomer({ ...customer, first_name: e.target.value })}
            style={styles.input}
          />
          <input
            placeholder="Last name"
            value={customer.last_name}
            onChange={(e) => setCustomer({ ...customer, last_name: e.target.value })}
            style={styles.input}
          />
        </div>

        <input
          placeholder="Email"
          value={customer.email}
          onChange={(e) => setCustomer({ ...customer, email: e.target.value })}
          style={styles.input}
        />

        <div style={styles.totalBar}>
          <span>Total To Pay</span>
          <strong>ETB {finalAmount}</strong>
        </div>

        <button onClick={initiatePayment} style={styles.payBtn} disabled={paying}>
          <ExternalLink size={16} />
          {paying ? 'Redirecting...' : 'Continue To Chapa'}
        </button>

        {message ? <div style={styles.message}>{message}</div> : null}
      </div>
    </div>
  );
};

const SummaryRow = ({ label, value, strong }) => (
  <div style={{ ...styles.row, fontWeight: strong ? 800 : 600 }}>
    <span>{label}</span>
    <span>ETB {Number(value || 0).toFixed(2)}</span>
  </div>
);

const styles = {
  page: { minHeight: '100vh', background: 'linear-gradient(135deg, #ecfeff, #eff6ff 55%, #f8fafc)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, fontFamily: 'Inter, sans-serif' },
  card: { width: '100%', maxWidth: 540, background: '#fff', borderRadius: 28, border: '1px solid #dbeafe', boxShadow: '0 24px 60px rgba(15,23,42,0.08)', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 },
  header: { display: 'flex', flexDirection: 'column', gap: 6 },
  kicker: { fontWeight: 800, letterSpacing: 1, color: '#0f766e', textTransform: 'uppercase' },
  title: { margin: 0, fontSize: 32 },
  subtitle: { margin: 0, color: '#475569', lineHeight: 1.5 },
  summaryBox: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 18, padding: 16, display: 'flex', flexDirection: 'column', gap: 10 },
  formSection: { display: 'flex', flexDirection: 'column', gap: 8 },
  label: { fontWeight: 700, color: '#334155' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  input: { width: '100%', boxSizing: 'border-box', border: '1px solid #cbd5e1', borderRadius: 14, padding: '14px 16px', fontSize: 14, outline: 'none' },
  totalBar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0f172a', color: '#fff', borderRadius: 18, padding: '16px 18px', fontSize: 18 },
  payBtn: { border: 'none', background: '#0f766e', color: '#fff', borderRadius: 16, padding: '14px 18px', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: 8, justifyContent: 'center', cursor: 'pointer' },
  message: { background: '#eff6ff', color: '#1d4ed8', borderRadius: 14, padding: 12, fontSize: 14 },
  row: { display: 'flex', justifyContent: 'space-between' },
  center: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: 'Inter, sans-serif' },
};

export default CustomerPaymentPage;
