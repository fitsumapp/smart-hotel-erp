import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';
import {
  Shield, TrendingUp, Hotel, Printer,
  RefreshCw, Calendar, CheckCircle, BookMarked, Layers, Activity
} from 'lucide-react';
import { API_BASE_URL } from '../apiConfig';

const REPORT_TABS = [
  { id: 'police',    label: 'Police Report',      icon: <Shield      size={16} />, color: '#ef4444' },
  { id: 'xreport',  label: 'X-Report (Daily)',    icon: <Activity    size={16} />, color: '#38bdf8' },
  { id: 'zreport',  label: 'Z-Report (Close Day)',icon: <CheckCircle size={16} />, color: '#bef264' },
  { id: 'occupancy',label: 'Occupancy & Revenue', icon: <Hotel       size={16} />, color: '#a78bfa' },
  { id: 'bookings', label: 'Bookings Report',     icon: <BookMarked  size={16} />, color: '#fb923c' },
  { id: 'inventory',label: 'Inventory Report',    icon: <Layers      size={16} />, color: '#fbbf24' },
];

const today = new Date().toISOString().split('T')[0];

export default function ReportsCenter({ initialTab }) {
  const [activeTab, setActiveTab] = useState(initialTab || 'police');
  const [reportDate, setReportDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [zClosed, setZClosed] = useState(false);
  const printRef = useRef();

  // When navigated from sidebar with a different initialTab, switch automatically
  useEffect(() => {
    if (initialTab && initialTab !== activeTab) {
      setActiveTab(initialTab);
      setData(null);
      setError('');
      setZClosed(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTab]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError('');
    setData(null);
    try {
      let res;
      if (activeTab === 'police') {
        res = await axios.get(`${API_BASE_URL}/users/reports/police/?date=${reportDate}`);
      } else if (activeTab === 'xreport') {
        res = await axios.get(`${API_BASE_URL}/users/reports/x-report/?date=${reportDate}`);
      } else if (activeTab === 'zreport') {
        res = await axios.post(`${API_BASE_URL}/users/reports/z-report/`, { date: reportDate });
        setZClosed(true);
      } else if (activeTab === 'occupancy') {
        res = await axios.get(`${API_BASE_URL}/users/reports/occupancy/`);
      } else if (activeTab === 'bookings') {
        res = await axios.get(`${API_BASE_URL}/users/reservations/?date_from=${reportDate}`);
      } else if (activeTab === 'inventory') {
        res = await axios.get(`${API_BASE_URL}/users/inventory/items/`);
      }
      setData(res?.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load report.');
    } finally {
      setLoading(false);
    }
  }, [activeTab, reportDate]);

  const handlePrint = () => {
    if (!printRef.current) return;
    const printContent = printRef.current.innerHTML;
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    const paperSize = data?.printer_paper_size || '80mm';
    
    // Determine if it's a thermal report or A4
    const isThermal = ['xreport', 'zreport'].includes(activeTab);
    const containerWidth = isThermal ? paperSize : '100%';
    const font = isThermal ? "'Courier New', Courier, monospace" : "Arial, sans-serif";

    printWindow.document.write(`
      <html>
        <head>
          <title>Print Report</title>
          <style>
            @page { size: auto; margin: 0; }
            body { 
              margin: 0; 
              padding: 0; 
              background: #fff; 
              color: #000; 
              font-family: ${font}; 
              -webkit-print-color-adjust: exact;
            }
            * { font-family: inherit; }
            .print-wrapper {
              width: ${containerWidth};
              margin: 0;
              padding: ${isThermal ? '2mm' : '20mm'};
              ${isThermal ? 'text-transform: uppercase;' : ''}
              line-height: 1.2;
            }
            .dashed-divider {
              border-top: 1px dashed #000 !important;
              margin: 5px 0 !important;
              width: 100% !important;
            }
            .item-row {
              display: flex !important;
              justify-content: space-between !important;
              margin: 2px 0 !important;
            }
            .centered {
              text-align: center !important;
            }
            .bold {
              font-weight: bold !important;
            }
            table { width: 100% !important; border-collapse: collapse !important; margin-top: 10px; }
            th { text-align: left !important; border-bottom: 1px dashed #000 !important; padding: 5px 0 !important; font-size: 11px; }
            td { padding: 5px 0 !important; font-size: 11px; border-bottom: 0.5px solid #eee; }
            .thermal-receipt td { border-bottom: none; padding: 2px 0; }
          </style>
        </head>
        <body>
          <div class="print-wrapper ${isThermal ? 'thermal-receipt' : ''}">
            ${printContent}
          </div>
          <script>
            window.onload = function() {
              window.focus();
              window.print();
              setTimeout(() => { window.close(); }, 500);
            };
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div className="print-container" style={{ padding: '20px 0', color: '#0f172a' }}>
      <style>{`
        @media screen {
          #print-report { display: none; }
        }
      `}</style>

      {/* Hero */}
      <div style={heroCard} className="no-print">
        <div>
          <p style={eyebrow}>Night Audit</p>
          <h2 style={{ margin: '8px 0', fontSize: '28px' }}>Reports Center</h2>
          <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.6 }}>
            Police Report, X/Z-Report, and Occupancy analysis with PDF-ready print output.
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignContent: 'start', justifyContent: 'flex-end' }}>
          <span style={pill}><Shield size={14} /> Police Report</span>
          <span style={pill}><TrendingUp size={14} /> X/Z Report</span>
          <span style={pill}><Hotel size={14} /> Occupancy</span>
        </div>
      </div>

      {/* Report Tabs */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 22, flexWrap: 'wrap' }} className="no-print">
        {REPORT_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); setData(null); setError(''); setZClosed(false); }}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 18px', borderRadius: 12, border: activeTab === tab.id ? 'none' : '1px solid #cbd5e1', cursor: 'pointer',
              fontWeight: 800, fontSize: 13,
              backgroundColor: activeTab === tab.id ? tab.color : '#fff',
              color: activeTab === tab.id ? '#0f172a' : '#64748b',
              boxShadow: activeTab === tab.id ? '0 4px 12px rgba(0,0,0,0.08)' : 'none',
              transition: 'all 0.2s',
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 22, alignItems: 'center', flexWrap: 'wrap' }} className="no-print">
        {activeTab !== 'occupancy' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, backgroundColor: '#fff', border: '1px solid #cbd5e1', borderRadius: 10, padding: '10px 14px' }}>
            <Calendar size={16} color="#64748b" />
            <input
              type="date"
              value={reportDate}
              onChange={e => setReportDate(e.target.value)}
              style={{ background: 'none', border: 'none', color: '#0f172a', outline: 'none', fontSize: 13, cursor: 'pointer', fontWeight: 600 }}
            />
          </div>
        )}
        <button onClick={fetchReport} disabled={loading} style={runBtn}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Loading...' : activeTab === 'zreport' ? 'Run Z-Report (Close Day)' : 'Generate Report'}
        </button>
        {data && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button onClick={handlePrint} style={printBtn}>
              <Printer size={16} /> Download / Print PDF
            </button>
            <div style={{ padding: '8px 12px', backgroundColor: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8 }}>
              <p style={{ margin: 0, fontSize: '11px', color: '#fcd34d', lineHeight: 1.4 }}>
                <strong>PRO TIP:</strong> For professional results, set <strong>Scale: 100%</strong> and <strong>Margins: None</strong> in your browser's print settings.
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div style={{ backgroundColor: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 12, padding: 16, color: '#fca5a5', marginBottom: 20 }} className="no-print">
          {error}
        </div>
      )}

      {zClosed && data && (
        <div style={{ backgroundColor: 'rgba(190,242,100,0.1)', border: '1px solid rgba(190,242,100,0.3)', borderRadius: 12, padding: 12, marginBottom: 16, color: '#bef264', fontWeight: 700, fontSize: 13 }} className="no-print">
          ✓ Z-Report closed for {data.date} by {data.closed_by}
        </div>
      )}

      {/* Report Content (Screen view) */}
      {data && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="no-print">
          {activeTab === 'police'    && <PoliceReportView data={data} />}
          {activeTab === 'xreport'  && <XZReportView data={data} />}
          {activeTab === 'zreport'  && <XZReportView data={data} />}
          {activeTab === 'occupancy'&& <OccupancyView data={data} />}
          {activeTab === 'bookings' && <BookingsReportView data={data} />}
          {activeTab === 'inventory'&& <InventoryReportView data={data} />}
        </motion.div>
      )}

      {/* Hidden print area */}
      <div ref={printRef} id="print-report">
        {data && activeTab === 'police'  && <PrintablePoliceReport data={data} />}
        {data && (activeTab === 'xreport' || activeTab === 'zreport') && <PrintableXZReport data={data} />}
        {data && activeTab === 'occupancy' && <PrintableOccupancy data={data} />}
        {data && activeTab === 'bookings' && <PrintableBookingsReport data={data} />}
        {data && activeTab === 'inventory' && <PrintableInventoryReport data={data} />}
      </div>
    </div>
  );
}

// ── Police Report ──────────────────────────────────────────────────────────
function PoliceReportView({ data }) {
  return (
    <div style={reportCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div>
          <h3 style={{ margin: 0 }}>Police Report</h3>
          <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: 13 }}>Date: {data.date} — Total guests: {data.total}</p>
        </div>
        <Shield size={24} color="#ef4444" />
      </div>
      <div style={tableWrap}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
              {['#', 'Guest Name', 'Nationality', 'ID Type', 'ID Number', 'Phone', 'Room', 'Check-In', 'Check-Out'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.guests.map((g, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #e2e8f0' }}>
                <td style={td}>{i + 1}</td>
                <td style={{ ...td, fontWeight: 600 }}>{g.guest_name}</td>
                <td style={td}>{g.nationality || '—'}</td>
                <td style={td}>{g.id_type?.replace('_', ' ')}</td>
                <td style={td}>{g.id_number || '—'}</td>
                <td style={td}>{g.phone || '—'}</td>
                <td style={td}>#{g.room_number} ({g.room_type})</td>
                <td style={td}>{g.check_in_date}</td>
                <td style={td}>{g.check_out_date}</td>
              </tr>
            ))}
            {!data.guests.length && (
              <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: '#475569' }}>No arrivals for this date.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── X/Z Report ────────────────────────────────────────────────────────────
function XZReportView({ data }) {
  const restMethods = [
    { label: 'Cash', value: data.restaurant?.cash, color: '#16a34a' },
    { label: 'Chapa', value: data.restaurant?.chapa, color: '#0284c7' },
    { label: 'Telebirr', value: data.restaurant?.telebirr, color: '#4d7c0f' },
    { label: 'Card', value: data.restaurant?.card, color: '#7c3aed' },
  ];
  const roomMethods = [
    { label: 'Cash', value: data.rooms?.cash, color: '#16a34a' },
    { label: 'Digital', value: data.rooms?.digital, color: '#0284c7' },
    { label: 'Bank Transfer', value: data.rooms?.bank_transfer, color: '#7c3aed' },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
      {/* Restaurant revenue card */}
      <div style={reportCard}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 15 }}>
          <div><h3 style={{ margin: 0, color: '#0f172a' }}>{data.report_type?.includes('X') ? 'X-Report' : 'Z-Report'}</h3><small style={{ color: '#94a3b8' }}>{data.date} — Live Snapshot</small></div>
          <div style={{ textAlign: 'right' }}><small style={{ color: '#94a3b8', fontSize: 10 }}>GRAND TOTAL</small><h2 style={{ margin: 0, color: '#0f766e' }}>ETB {Number(data.grand_total).toLocaleString()}</h2></div>
        </div>
        <p style={{ margin: '0 0 10px', fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Restaurant Revenue</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 18 }}>
          {restMethods.map(m => (
            <div key={m.label} style={{ backgroundColor: '#f8fafc', padding: 12, borderRadius: 12, border: '1px solid #e2e8f0' }}>
              <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>{m.label.toUpperCase()}</small>
              <p style={{ margin: '4px 0 0', fontWeight: 800, color: m.color }}>ETB {Number(m.value || 0).toLocaleString()}</p>
            </div>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, borderTop: '1px solid #f1f5f9', paddingTop: 14 }}>
          <div style={{ backgroundColor: '#f8fafc', padding: 14, borderRadius: 12, border: '1px solid #e2e8f0' }}>
            <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>RESTAURANT TOTAL</small>
            <h3 style={{ margin: '4px 0 0', color: '#0f172a' }}>ETB {Number(data.restaurant?.total).toLocaleString()}</h3>
            <small style={{ color: '#64748b' }}>{data.restaurant?.order_count} orders paid</small>
          </div>
          <div style={{ backgroundColor: '#f8fafc', padding: 14, borderRadius: 12, border: '1px solid #e2e8f0' }}>
            <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>ROOM TOTAL</small>
            <h3 style={{ margin: '4px 0 0', color: '#0f172a' }}>ETB {Number(data.rooms?.revenue).toLocaleString()}</h3>
            <small style={{ color: '#64748b' }}>{data.rooms?.checkouts} checkouts</small>
          </div>
        </div>
      </div>

      {/* Room revenue breakdown card */}
      <div style={reportCard}>
        <p style={{ margin: '0 0 14px', fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Room Revenue by Payment Method</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {roomMethods.map(m => (
            <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8fafc', padding: '12px 16px', borderRadius: 12, border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#475569' }}>{m.label}</span>
              <span style={{ fontSize: 16, fontWeight: 800, color: m.color }}>ETB {Number(m.value || 0).toLocaleString()}</span>
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f0fdf4', padding: '14px 16px', borderRadius: 12, border: '1px solid #86efac', marginTop: 4 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#166534' }}>ROOM TOTAL</span>
            <span style={{ fontSize: 18, fontWeight: 900, color: '#15803d' }}>ETB {Number(data.rooms?.revenue || 0).toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Occupancy & Revenue ─────────────────────────────────────────────────────
function OccupancyView({ data }) {
  const roomStats = [
    { label: 'Available', value: data.available, color: '#0284c7' },
    { label: 'Occupied', value: data.occupied, color: '#16a34a' },
    { label: 'Dirty', value: data.dirty, color: '#dc2626' },
    { label: 'Maintenance', value: data.maintenance, color: '#475569' },
  ];
  return (
    <div style={reportCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h3 style={{ margin: 0, color: '#0f172a' }}>Occupancy & Revenue Report</h3>
          <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: 13 }}>Live snapshot — Last 30 days revenue analysis</p>
        </div>
        <Hotel size={24} color="#0f766e" />
      </div>

      {/* Occupancy meter */}
      <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 20, padding: 24, marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 14, color: '#94a3b8', fontWeight: 700 }}>OCCUPANCY RATE</span>
          <span style={{ fontSize: 32, fontWeight: 900, color: data.occupancy_percent > 70 ? '#16a34a' : data.occupancy_percent > 40 ? '#d97706' : '#dc2626' }}>
            {data.occupancy_percent}%
          </span>
        </div>
        <div style={{ height: 16, backgroundColor: '#e2e8f0', borderRadius: 999, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${data.occupancy_percent}%`, borderRadius: 999, background: 'linear-gradient(90deg, #0284c7, #0f766e)', transition: 'width 1s ease' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: '#64748b' }}>
          <span>{data.occupied} occupied of {data.total_rooms} total rooms</span>
        </div>
      </div>

      {/* Room breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 22 }}>
        {roomStats.map(s => (
          <div key={s.label} style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 14, padding: 16, textAlign: 'center' }}>
            <p style={{ margin: '0 0 6px', fontSize: 10, fontWeight: 700, color: '#64748b' }}>{s.label.toUpperCase()}</p>
            <p style={{ margin: 0, fontSize: 26, fontWeight: 800, color: s.color }}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        {[
          { label: 'Total Revenue (30d)', value: `ETB ${Number(data.total_revenue_30d).toLocaleString()}`, color: '#4d7c0f' },
          { label: 'Avg Daily Rate (ADR)', value: `ETB ${data.adr}`, color: '#0284c7' },
          { label: 'RevPAR', value: `ETB ${data.revpar}`, color: '#7c3aed' },
          { label: 'Checkouts (30d)', value: data.checkout_count_30d, color: '#d97706' },
        ].map(k => (
          <div key={k.label} style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 16, padding: 20 }}>
            <p style={{ margin: '0 0 6px', fontSize: 11, fontWeight: 700, color: '#64748b' }}>{k.label.toUpperCase()}</p>
            <p style={{ margin: 0, fontSize: 22, fontWeight: 800, color: k.color }}>{k.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Printable versions ────────────────────────────────────────────────────
function PrintablePoliceReport({ data }) {
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', color: '#000' }}>
      <h2 style={{ textAlign: 'center' }}>POLICE REPORT — {data.date}</h2>
      <p style={{ textAlign: 'center' }}>Total Guests: {data.total}</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 20 }}>
        <thead>
          <tr style={{ backgroundColor: '#f1f5f9' }}>
            {['#', 'Guest Name', 'Nationality', 'ID Type', 'ID Number', 'Phone', 'Room', 'Check-In', 'Check-Out'].map(h => (
              <th key={h} style={{ border: '1px solid #ccc', padding: 8, fontSize: 11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.guests.map((g, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{i + 1}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.guest_name}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.nationality || '—'}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.id_type}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.id_number || '—'}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.phone || '—'}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>#{g.room_number}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.check_in_date}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{g.check_out_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrintableXZReport({ data }) {
  const formatAmount = (val) => `*${Number(val || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  
  return (
    <div style={{ color: '#000' }}>
      <div className="centered">
        <h2 style={{ margin: '0', fontSize: '16px' }}>{data.hotel_name || 'ATLAS INTERNATIONAL'}</h2>
        <p style={{ fontSize: '10px', margin: '2px 0' }}>TEL-0116187432 / 0911760145</p>
        <div className="dashed-divider" />
        <p style={{ fontSize: '11px', margin: '2px 0' }}>*** NON-FISCAL ***</p>
        <div className="dashed-divider" />
        <h3 style={{ margin: '10px 0', fontSize: '18px', fontWeight: 'bold' }}>REPORT &lt;{data.report_type?.includes('X') ? 'X' : 'Z'}&gt;</h3>
        <p style={{ fontSize: '11px', margin: '2px 0' }}>*** NON-FISCAL ***</p>
        <div className="dashed-divider" />
      </div>

      <div style={{ fontSize: '12px', marginTop: '10px' }}>
        <div className="item-row">
          <span>SALES NET</span>
          <span>{formatAmount(data.grand_total)}</span>
        </div>
        <div className="item-row">
          <span>SURCHARGES</span>
          <span>{formatAmount(data.restaurant?.service_charge || 0)}</span>
        </div>
        
        <div className="centered" style={{ margin: '10px 0' }}>
          <p style={{ fontSize: '10px' }}>*** NON-FISCAL ***</p>
        </div>

        <div className="item-row">
          <span>CASH</span>
          <span>{formatAmount(data.restaurant?.cash)}</span>
        </div>
        <div className="item-row">
          <span>CHAPA (DIGITAL)</span>
          <span>{formatAmount(data.restaurant?.chapa)}</span>
        </div>
        <div className="item-row">
          <span>TELEBIRR</span>
          <span>{formatAmount(data.restaurant?.telebirr)}</span>
        </div>
        <div className="item-row">
          <span>CARD</span>
          <span>{formatAmount(data.restaurant?.card)}</span>
        </div>

        <div className="dashed-divider" />
        <div className="item-row bold">
          <span>RESTAURANT TOTAL</span>
          <span>{formatAmount(data.restaurant?.total)}</span>
        </div>
        <div className="dashed-divider" />

        <div className="centered" style={{ margin: '8px 0 4px' }}>
          <p style={{ fontSize: '10px', margin: 0 }}>--- ROOM REVENUE ---</p>
        </div>
        <div className="item-row">
          <span>ROOM CASH</span>
          <span>{formatAmount(data.rooms?.cash)}</span>
        </div>
        <div className="item-row">
          <span>ROOM DIGITAL</span>
          <span>{formatAmount(data.rooms?.digital)}</span>
        </div>
        <div className="item-row">
          <span>ROOM BANK TRANSFER</span>
          <span>{formatAmount(data.rooms?.bank_transfer)}</span>
        </div>
        <div className="dashed-divider" />
        <div className="item-row bold">
          <span>ROOM TOTAL</span>
          <span>{formatAmount(data.rooms?.revenue)}</span>
        </div>

        <div className="dashed-divider" />
        <div className="item-row bold">
          <span>TOTAL</span>
          <span>{formatAmount(data.grand_total)}</span>
        </div>
        <div className="item-row bold">
          <span>TOTAL IN SAFE</span>
          <span>{formatAmount((data.restaurant?.cash || 0) + (data.rooms?.cash || 0))}</span>
        </div>
        <div className="dashed-divider" />

        <div className="centered" style={{ margin: '10px 0' }}>
          <p style={{ fontSize: '10px' }}>*** NON-FISCAL ***</p>
        </div>

        <div className="item-row">
          <span>TXBL1 (VAT 15%)</span>
          <span>{formatAmount(data.grand_total / 1.15)}</span>
        </div>
        <div className="item-row">
          <span>TAX1 15%</span>
          <span>{formatAmount(data.restaurant?.vat || (data.grand_total - (data.grand_total / 1.15)))}</span>
        </div>

        <div className="dashed-divider" />
        <div className="item-row">
          <span>SALES TL</span>
          <span>{formatAmount(data.grand_total)}</span>
        </div>
        <div className="item-row">
          <span>TAX TL</span>
          <span>{formatAmount(data.restaurant?.vat || 0)}</span>
        </div>
        <div className="dashed-divider" />
      </div>

      <div className="centered" style={{ marginTop: '20px', fontSize: '10px' }}>
        <p style={{ margin: '2px 0' }}>DATE: {data.date}</p>
        <p style={{ margin: '2px 0' }}>GENERATED BY: {data.closed_by || 'ADMIN'}</p>
        <p style={{ margin: '10px 0', fontSize: '12px' }}>*** END OF REPORT ***</p>
      </div>
    </div>
  );
}

function PrintableOccupancy({ data }) {
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', color: '#000' }}>
      <h2 style={{ textAlign: 'center' }}>Occupancy & Revenue Report</h2>
      <table style={{ width: '100%', margin: '20px auto', borderCollapse: 'collapse' }}>
        <tbody>
          {[
            ['Total Rooms', data.total_rooms], ['Occupied', data.occupied],
            ['Occupancy %', `${data.occupancy_percent}%`], ['ADR', `ETB ${data.adr}`],
            ['RevPAR', `ETB ${data.revpar}`], ['Revenue (30d)', `ETB ${Number(data.total_revenue_30d).toLocaleString()}`],
            ['Checkouts (30d)', data.checkout_count_30d],
          ].map(([label, value]) => (
            <tr key={label} style={{ borderBottom: '1px solid #ccc' }}>
              <td style={{ padding: '8px 12px' }}>{label}</td>
              <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700 }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Bookings Report ──────────────────────────────────────────────────────────
function BookingsReportView({ data }) {
  const reservations = Array.isArray(data) ? data : (data?.reservations || []);

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'checked_in': return { bg: '#e0f2fe', text: '#0369a1' };
      case 'checked_out': return { bg: '#f0fdf4', text: '#166534' };
      case 'confirmed': return { bg: '#fef3c7', text: '#d97706' };
      case 'cancelled': return { bg: '#fef2f2', text: '#991b1b' };
      default: return { bg: '#f1f5f9', text: '#475569' };
    }
  };

  return (
    <div style={reportCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div>
          <h3 style={{ margin: 0 }}>Bookings Report</h3>
          <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: 13 }}>Total bookings found: {reservations.length}</p>
        </div>
        <BookMarked size={24} color="#fb923c" />
      </div>
      <div style={tableWrap}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
              {['#', 'Guest Name', 'Room', 'Check-In', 'Check-Out', 'Status', 'Deposit', 'Total Amount'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reservations.map((r, i) => {
              const colors = getStatusColor(r.status);
              return (
                <tr key={r.id || i} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={td}>{i + 1}</td>
                  <td style={{ ...td, fontWeight: 600 }}>{r.guest_name}</td>
                  <td style={td}>#{r.room_number || (r.room && r.room.room_number) || '—'}</td>
                  <td style={td}>{r.check_in_date}</td>
                  <td style={td}>{r.check_out_date}</td>
                  <td style={td}>
                    <span style={{
                      backgroundColor: colors.bg,
                      color: colors.text,
                      padding: '4px 8px',
                      borderRadius: 20,
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase'
                    }}>
                      {r.status?.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={td}>ETB {Number(r.deposit_amount || 0).toLocaleString()}</td>
                  <td style={{ ...td, fontWeight: 700 }}>ETB {Number(r.total_amount || 0).toLocaleString()}</td>
                </tr>
              );
            })}
            {!reservations.length && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: '#475569' }}>No reservations found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Inventory Report ─────────────────────────────────────────────────────────
function InventoryReportView({ data }) {
  const items = Array.isArray(data) ? data : (data?.items || []);

  const getStockStatus = (item) => {
    const current = Number(item.current_stock || 0);
    const minLevel = Number(item.min_reorder_level || 5);
    if (current <= 0) return { label: 'Out of Stock', bg: '#fef2f2', text: '#991b1b' };
    if (current <= minLevel) return { label: 'Low Stock', bg: '#fffbeb', text: '#b45309' };
    return { label: 'In Stock', bg: '#f0fdf4', text: '#166534' };
  };

  return (
    <div style={reportCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div>
          <h3 style={{ margin: 0 }}>Inventory Stock Report</h3>
          <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: 13 }}>Total unique items: {items.length}</p>
        </div>
        <Layers size={24} color="#fbbf24" />
      </div>
      <div style={tableWrap}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
              {['#', 'Item Code', 'Name', 'Category', 'Current Stock', 'Min Reorder', 'Status', 'Unit Cost', 'Total Value'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => {
              const status = getStockStatus(item);
              const totalVal = Number(item.current_stock || 0) * Number(item.unit_cost || 0);
              return (
                <tr key={item.id || i} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={td}>{i + 1}</td>
                  <td style={{ ...td, fontWeight: 600 }}>{item.item_code}</td>
                  <td style={td}>{item.name}</td>
                  <td style={td}>{item.category_name || (item.category && item.category.name) || '—'}</td>
                  <td style={{ ...td, fontWeight: 700 }}>{item.current_stock}</td>
                  <td style={td}>{item.min_reorder_level}</td>
                  <td style={td}>
                    <span style={{
                      backgroundColor: status.bg,
                      color: status.text,
                      padding: '4px 8px',
                      borderRadius: 20,
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase'
                    }}>
                      {status.label}
                    </span>
                  </td>
                  <td style={td}>ETB {Number(item.unit_cost || 0).toLocaleString()}</td>
                  <td style={{ ...td, fontWeight: 700 }}>ETB {Number(totalVal || 0).toLocaleString()}</td>
                </tr>
              );
            })}
            {!items.length && (
              <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: '#475569' }}>No inventory items found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Printable Bookings Report ────────────────────────────────────────────────
function PrintableBookingsReport({ data }) {
  const reservations = Array.isArray(data) ? data : (data?.reservations || []);
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', color: '#000' }}>
      <h2 style={{ textAlign: 'center' }}>BOOKINGS REPORT</h2>
      <p style={{ textAlign: 'center' }}>Total reservations: {reservations.length}</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 20 }}>
        <thead>
          <tr style={{ backgroundColor: '#f1f5f9' }}>
            {['#', 'Guest Name', 'Room', 'Check-In', 'Check-Out', 'Status', 'Deposit', 'Total Amount'].map(h => (
              <th key={h} style={{ border: '1px solid #ccc', padding: 8, fontSize: 11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reservations.map((r, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{i + 1}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{r.guest_name}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>#{r.room_number || (r.room && r.room.room_number) || '—'}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{r.check_in_date}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{r.check_out_date}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{r.status}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>ETB {Number(r.deposit_amount || 0).toLocaleString()}</td>
              <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11, fontWeight: 700 }}>ETB {Number(r.total_amount || 0).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Printable Inventory Report ───────────────────────────────────────────────
function PrintableInventoryReport({ data }) {
  const items = Array.isArray(data) ? data : (data?.items || []);
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', color: '#000' }}>
      <h2 style={{ textAlign: 'center' }}>INVENTORY STOCK REPORT</h2>
      <p style={{ textAlign: 'center' }}>Total items: {items.length}</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 20 }}>
        <thead>
          <tr style={{ backgroundColor: '#f1f5f9' }}>
            {['#', 'Item Code', 'Name', 'Category', 'Stock', 'Min Level', 'Unit Cost', 'Total Value'].map(h => (
              <th key={h} style={{ border: '1px solid #ccc', padding: 8, fontSize: 11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const totalVal = Number(item.current_stock || 0) * Number(item.unit_cost || 0);
            return (
              <tr key={i}>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{i + 1}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{item.item_code}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{item.name}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{item.category_name || (item.category && item.category.name) || '—'}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11, fontWeight: 700 }}>{item.current_stock}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>{item.min_reorder_level}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11 }}>ETB {Number(item.unit_cost || 0).toLocaleString()}</td>
                <td style={{ border: '1px solid #ccc', padding: 7, fontSize: 11, fontWeight: 700 }}>ETB {Number(totalVal || 0).toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Styles
const heroCard = { background: 'linear-gradient(135deg, #0f766e 0%, #0d9488 100%)', border: 'none', borderRadius: 24, padding: 24, marginBottom: 22, display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20, boxShadow: '0 12px 28px rgba(15,118,110,0.15)', color: '#fff' };
const eyebrow = { margin: 0, color: '#ccfbf1', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700 };
const pill = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.15)', border: 'none', color: '#fff', fontSize: 12, fontWeight: 600 };
const runBtn = { backgroundColor: '#0f766e', color: '#fff', border: 'none', padding: '11px 22px', borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };
const printBtn = { backgroundColor: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '11px 22px', borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 };
const reportCard = { backgroundColor: '#fff', border: '1px solid rgba(148,163,184,0.16)', borderRadius: 20, padding: 24, boxShadow: '0 12px 28px rgba(15,23,42,0.04)' };
const tableWrap = { backgroundColor: '#fff', borderRadius: 14, border: '1px solid #cbd5e1', overflow: 'auto', marginTop: 16 };
const th = { padding: '12px 14px', fontSize: 10, fontWeight: 700, color: '#64748b', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' };
const td = { padding: '10px 14px', fontSize: 12, color: '#0f172a', whiteSpace: 'nowrap', borderBottom: '1px solid #f1f5f9' };

