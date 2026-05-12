import React, { useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';
import {
  Shield, TrendingUp, Hotel, Printer,
  RefreshCw, Calendar, CheckCircle
} from 'lucide-react';
import { API_BASE_URL } from '../apiConfig';

const REPORT_TABS = [
  { id: 'police', label: 'Police Report', icon: <Shield size={16} />, color: '#ef4444' },
  { id: 'xreport', label: 'X-Report', icon: <TrendingUp size={16} />, color: '#38bdf8' },
  { id: 'zreport', label: 'Z-Report', icon: <CheckCircle size={16} />, color: '#bef264' },
  { id: 'occupancy', label: 'Occupancy & Revenue', icon: <Hotel size={16} />, color: '#a78bfa' },
];

const today = new Date().toISOString().split('T')[0];

export default function ReportsCenter() {
  const [activeTab, setActiveTab] = useState('police');
  const [reportDate, setReportDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [zClosed, setZClosed] = useState(false);
  const printRef = useRef();

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
      }
      setData(res.data);
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
    <div className="print-container" style={{ padding: '20px', backgroundColor: '#020617', minHeight: '100vh', color: '#fff' }}>
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
              padding: '10px 18px', borderRadius: 12, border: 'none', cursor: 'pointer',
              fontWeight: 700, fontSize: 13,
              backgroundColor: activeTab === tab.id ? tab.color : '#0f172a',
              color: activeTab === tab.id ? '#000' : '#94a3b8',
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, padding: '10px 14px' }}>
            <Calendar size={16} color="#64748b" />
            <input
              type="date"
              value={reportDate}
              onChange={e => setReportDate(e.target.value)}
              style={{ background: 'none', border: 'none', color: '#fff', outline: 'none', fontSize: 13 }}
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
          {activeTab === 'police' && <PoliceReportView data={data} />}
          {activeTab === 'xreport' && <XZReportView data={data} />}
          {activeTab === 'zreport' && <XZReportView data={data} />}
          {activeTab === 'occupancy' && <OccupancyView data={data} />}
        </motion.div>
      )}

      {/* Hidden print area */}
      <div ref={printRef} id="print-report">
        {data && activeTab === 'police' && <PrintablePoliceReport data={data} />}
        {data && (activeTab === 'xreport' || activeTab === 'zreport') && <PrintableXZReport data={data} />}
        {data && activeTab === 'occupancy' && <PrintableOccupancy data={data} />}
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
            <tr style={{ borderBottom: '1px solid #1e293b', backgroundColor: 'rgba(30,41,59,0.4)' }}>
              {['#', 'Guest Name', 'Nationality', 'ID Type', 'ID Number', 'Phone', 'Room', 'Check-In', 'Check-Out'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.guests.map((g, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
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
  const methods = [
    { label: 'Cash', value: data.restaurant?.cash, color: '#86efac' },
    { label: 'Chapa', value: data.restaurant?.chapa, color: '#38bdf8' },
    { label: 'Telebirr', value: data.restaurant?.telebirr, color: '#bef264' },
    { label: 'Card', value: data.restaurant?.card, color: '#a78bfa' },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
      <div style={reportCard}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 15 }}>
          <div><h3 style={{ margin: 0 }}>X-Report</h3><small style={{ color: '#94a3b8' }}>{data.date} — Live Snapshot</small></div>
          <div style={{ textAlign: 'right' }}><small style={{ color: '#94a3b8', fontSize: 10 }}>GRAND TOTAL</small><h2 style={{ margin: 0, color: '#bef264' }}>ETB {Number(data.grand_total).toLocaleString()}</h2></div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
          {methods.map(m => (
            <div key={m.label} style={{ backgroundColor: '#111827', padding: 12, borderRadius: 12, border: '1px solid #1f2937' }}>
              <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>{m.label.toUpperCase()}</small>
              <p style={{ margin: '4px 0 0', fontWeight: 800, color: m.color }}>ETB {Number(m.value || 0).toLocaleString()}</p>
            </div>
          ))}
          <div style={{ backgroundColor: '#111827', padding: 12, borderRadius: 12, border: '1px solid #1f2937' }}>
            <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>CARD</small>
            <p style={{ margin: '4px 0 0', fontWeight: 800, color: '#a78bfa' }}>ETB {Number(data.restaurant?.card || 0).toLocaleString()}</p>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div style={{ backgroundColor: '#111827', padding: 16, borderRadius: 12, border: '1px solid #1f2937' }}>
            <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>RESTAURANT REVENUE</small>
            <h3 style={{ margin: '4px 0 0', color: '#fff' }}>ETB {Number(data.restaurant?.total).toLocaleString()}</h3>
            <small style={{ color: '#64748b' }}>{data.restaurant?.order_count} orders paid</small>
          </div>
          <div style={{ backgroundColor: '#111827', padding: 16, borderRadius: 12, border: '1px solid #1f2937' }}>
            <small style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700 }}>ROOM REVENUE</small>
            <h3 style={{ margin: '4px 0 0', color: '#fff' }}>ETB {Number(data.rooms?.revenue).toLocaleString()}</h3>
            <small style={{ color: '#64748b' }}>{data.rooms?.checkout_count} checkouts</small>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Occupancy & Revenue ─────────────────────────────────────────────────────
function OccupancyView({ data }) {
  const roomStats = [
    { label: 'Available', value: data.available, color: '#38bdf8' },
    { label: 'Occupied', value: data.occupied, color: '#86efac' },
    { label: 'Dirty', value: data.dirty, color: '#fca5a5' },
    { label: 'Maintenance', value: data.maintenance, color: '#94a3b8' },
  ];
  return (
    <div style={reportCard}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h3 style={{ margin: 0 }}>Occupancy & Revenue Report</h3>
          <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: 13 }}>Live snapshot — Last 30 days revenue analysis</p>
        </div>
        <Hotel size={24} color="#a78bfa" />
      </div>

      {/* Occupancy meter */}
      <div style={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 20, padding: 24, marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 14, color: '#94a3b8', fontWeight: 700 }}>OCCUPANCY RATE</span>
          <span style={{ fontSize: 32, fontWeight: 900, color: data.occupancy_percent > 70 ? '#86efac' : data.occupancy_percent > 40 ? '#fcd34d' : '#fca5a5' }}>
            {data.occupancy_percent}%
          </span>
        </div>
        <div style={{ height: 16, backgroundColor: '#1e293b', borderRadius: 999, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${data.occupancy_percent}%`, borderRadius: 999, background: 'linear-gradient(90deg, #38bdf8, #818cf8)', transition: 'width 1s ease' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: '#64748b' }}>
          <span>{data.occupied} occupied of {data.total_rooms} total rooms</span>
        </div>
      </div>

      {/* Room breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 22 }}>
        {roomStats.map(s => (
          <div key={s.label} style={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 14, padding: 16, textAlign: 'center' }}>
            <p style={{ margin: '0 0 6px', fontSize: 10, fontWeight: 700, color: '#64748b' }}>{s.label.toUpperCase()}</p>
            <p style={{ margin: 0, fontSize: 26, fontWeight: 800, color: s.color }}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        {[
          { label: 'Total Revenue (30d)', value: `ETB ${Number(data.total_revenue_30d).toLocaleString()}`, color: '#bef264' },
          { label: 'Avg Daily Rate (ADR)', value: `ETB ${data.adr}`, color: '#38bdf8' },
          { label: 'RevPAR', value: `ETB ${data.revpar}`, color: '#a78bfa' },
          { label: 'Checkouts (30d)', value: data.checkout_count_30d, color: '#fdba74' },
        ].map(k => (
          <div key={k.label} style={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 16, padding: 20 }}>
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
          <span>TOTAL</span>
          <span>{formatAmount(data.grand_total)}</span>
        </div>
        <div className="item-row bold">
          <span>TOTAL IN SAFE</span>
          <span>{formatAmount(data.restaurant?.cash)}</span>
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

// Styles
const heroCard = { background: 'linear-gradient(135deg,rgba(15,23,42,0.95) 0%,rgba(30,41,59,0.95) 50%,rgba(88,28,135,0.7) 100%)', border: '1px solid rgba(167,139,250,0.25)', borderRadius: 24, padding: 24, marginBottom: 22, display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20 };
const eyebrow = { margin: 0, color: '#c4b5fd', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700 };
const pill = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 999, backgroundColor: 'rgba(15,23,42,0.45)', border: '1px solid rgba(167,139,250,0.25)', color: '#e9d5ff', fontSize: 12, fontWeight: 600 };
const runBtn = { backgroundColor: '#3f5d45', color: '#fff', border: 'none', padding: '11px 22px', borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 };
const printBtn = { backgroundColor: 'rgba(167,139,250,0.15)', color: '#c4b5fd', border: '1px solid rgba(167,139,250,0.3)', padding: '11px 22px', borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 };
const reportCard = { backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 20, padding: 24 };
const tableWrap = { backgroundColor: '#111827', borderRadius: 14, border: '1px solid #1f2937', overflow: 'auto', marginTop: 16 };
const th = { padding: '12px 14px', fontSize: 10, fontWeight: 700, color: '#64748b', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' };
const td = { padding: '10px 14px', fontSize: 12, color: '#cbd5e1', whiteSpace: 'nowrap' };
