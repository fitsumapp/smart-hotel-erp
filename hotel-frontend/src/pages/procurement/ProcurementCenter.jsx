import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  ShoppingCart, FileText, Globe, Award, Truck, Scale, DollarSign
} from 'lucide-react';
import { API_BASE_URL } from '../../apiConfig';

import RequisitionDesk from './RequisitionDesk';
import RfqDesk from './RfqDesk';
import QuotationDesk from './QuotationDesk';
import AwardMatrixDesk from './AwardMatrixDesk';
import GrnDesk from './GrnDesk';
import InvoiceMatchingDesk from './InvoiceMatchingDesk';

const API_V1 = `${API_BASE_URL}/v1`;

export default function ProcurementCenter({ userData, initialSection = 'requisitions' }) {
  const [activeTab, setActiveTab] = useState(initialSection);
  const [stats, setStats] = useState({
    pendingRequisitions: 0,
    openRfqs: 0,
    activeQuotations: 0,
    openPos: 0,
    pendingInvoices: 0
  });

  // Cross-desk navigation states
  const [navTargetRfq, setNavTargetRfq] = useState(null);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchKpis = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [reqRes, rfqRes, quoteRes, poRes, invRes] = await Promise.all([
        axios.get(`${API_V1}/procurement/requisitions/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_V1}/procurement/rfqs/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_V1}/procurement/quotations/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_V1}/procurement/orders/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_V1}/procurement/invoices/`, { headers }).catch(() => ({ data: [] }))
      ]);

      const reqs = Array.isArray(reqRes.data) ? reqRes.data : (reqRes.data?.results || []);
      const rfqs = Array.isArray(rfqRes.data) ? rfqRes.data : (rfqRes.data?.results || []);
      const quotes = Array.isArray(quoteRes.data) ? quoteRes.data : (quoteRes.data?.results || []);
      const pos = Array.isArray(poRes.data) ? poRes.data : (poRes.data?.results || []);
      const invs = Array.isArray(invRes.data) ? invRes.data : (invRes.data?.results || []);

      setStats({
        pendingRequisitions: reqs.filter(r => r.status === 'draft' || r.status === 'pending_approval').length,
        openRfqs: rfqs.filter(r => r.status === 'published').length,
        activeQuotations: quotes.filter(q => q.status === 'submitted' || q.status === 'under_evaluation').length,
        openPos: pos.filter(p => p.status === 'issued' || p.status === 'partially_received').length,
        pendingInvoices: invs.filter(i => i.status === 'matched').length
      });
    } catch (err) {
      console.error('Failed to load procurement KPIs:', err);
    }
  }, [getHeaders]);

  useEffect(() => {
    fetchKpis();
  }, [fetchKpis]);

  useEffect(() => {
    if (initialSection) {
      setActiveTab(initialSection);
    }
  }, [initialSection]);

  const tabs = [
    { id: 'requisitions', title: 'Requisitions', icon: <FileText size={16} />, badge: stats.pendingRequisitions },
    { id: 'rfqs', title: 'RFQs & Bidding', icon: <Globe size={16} />, badge: stats.openRfqs },
    { id: 'quotations', title: 'Supplier Bids', icon: <DollarSign size={16} />, badge: stats.activeQuotations },
    { id: 'awards', title: 'Split-Award Matrix', icon: <Award size={16} /> },
    { id: 'receiving', title: 'Goods Receiving (GRN)', icon: <Truck size={16} />, badge: stats.openPos },
    { id: 'invoices', title: '3-Way Match & AP', icon: <Scale size={16} />, badge: stats.pendingInvoices },
  ];

  return (
    <div style={containerStyle}>
      {/* Header Banner */}
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={logoIconBg}>
            <ShoppingCart size={24} color="#ffffff" />
          </div>
          <div>
            <h1 style={titleStyle}>Enterprise Procurement & Sourcing Center</h1>
            <p style={subtitleStyle}>
              End-to-end supply chain governance: Purchase Requisitions, Competitive RFQs, Landed Cost Evaluation, GRN Intake, and 3-Way Matching.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div style={statsGridStyle}>
        <div style={statCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={statLabelStyle}>Pending Requisitions</span>
              <h2 style={{ ...statValueStyle, color: stats.pendingRequisitions > 0 ? '#b45309' : '#0f172a' }}>
                {stats.pendingRequisitions}
              </h2>
            </div>
            <div style={{ ...statIconBg, backgroundColor: 'rgba(217,119,6,0.1)' }}>
              <FileText size={20} color="#b45309" />
            </div>
          </div>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={statLabelStyle}>Active RFQs</span>
              <h2 style={{ ...statValueStyle, color: '#0369a1' }}>{stats.openRfqs}</h2>
            </div>
            <div style={{ ...statIconBg, backgroundColor: 'rgba(2,132,199,0.1)' }}>
              <Globe size={20} color="#0284c7" />
            </div>
          </div>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={statLabelStyle}>Bids Under Review</span>
              <h2 style={{ ...statValueStyle, color: '#7c3aed' }}>{stats.activeQuotations}</h2>
            </div>
            <div style={{ ...statIconBg, backgroundColor: 'rgba(124,58,237,0.1)' }}>
              <DollarSign size={20} color="#7c3aed" />
            </div>
          </div>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={statLabelStyle}>POs Pending Delivery</span>
              <h2 style={{ ...statValueStyle, color: stats.openPos > 0 ? '#0f766e' : '#64748b' }}>
                {stats.openPos}
              </h2>
            </div>
            <div style={{ ...statIconBg, backgroundColor: 'rgba(15,118,110,0.1)' }}>
              <Truck size={20} color="#0f766e" />
            </div>
          </div>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={statLabelStyle}>Invoices Awaiting Sign-off</span>
              <h2 style={{ ...statValueStyle, color: stats.pendingInvoices > 0 ? '#dc2626' : '#64748b' }}>
                {stats.pendingInvoices}
              </h2>
            </div>
            <div style={{ ...statIconBg, backgroundColor: 'rgba(220,38,38,0.1)' }}>
              <Scale size={20} color="#dc2626" />
            </div>
          </div>
        </div>
      </div>

      {/* Desk Tab Navigation */}
      <div style={tabBarStyle} className="no-print">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                fetchKpis();
              }}
              style={{
                ...tabBtnStyle,
                borderBottom: isActive ? '3px solid #0f766e' : '3px solid transparent',
                color: isActive ? '#0f766e' : '#64748b',
                fontWeight: isActive ? '800' : '600'
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {tab.icon}
                {tab.title}
                {tab.badge > 0 && (
                  <span style={{
                    backgroundColor: '#ef4444',
                    color: '#ffffff',
                    fontSize: '10px',
                    fontWeight: '800',
                    padding: '2px 7px',
                    borderRadius: '12px'
                  }}>
                    {tab.badge}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* Main Tab Content */}
      <main style={bodyContainerStyle}>
        {activeTab === 'requisitions' && (
          <RequisitionDesk
            userData={userData}
            onNavigateToRfq={(req) => {
              setNavTargetRfq(null);
              setActiveTab('rfqs');
            }}
          />
        )}

        {activeTab === 'rfqs' && (
          <RfqDesk
            userData={userData}
            onNavigateToQuotations={(rfq) => {
              setNavTargetRfq(rfq);
              setActiveTab('quotations');
            }}
            onNavigateToAward={(rfq) => {
              setNavTargetRfq(rfq);
              setActiveTab('awards');
            }}
          />
        )}

        {activeTab === 'quotations' && (
          <QuotationDesk
            userData={userData}
            initialRfq={navTargetRfq}
            onNavigateToAward={(rfq) => {
              setNavTargetRfq(rfq);
              setActiveTab('awards');
            }}
          />
        )}

        {activeTab === 'awards' && (
          <AwardMatrixDesk
            userData={userData}
            initialRfq={navTargetRfq}
            onNavigateToGrn={() => setActiveTab('receiving')}
          />
        )}

        {activeTab === 'receiving' && (
          <GrnDesk
            userData={userData}
            onNavigateToInvoice={() => setActiveTab('invoices')}
          />
        )}

        {activeTab === 'invoices' && (
          <InvoiceMatchingDesk userData={userData} />
        )}
      </main>
    </div>
  );
}

// Styling definitions
const containerStyle = { minHeight: '100vh', backgroundColor: '#f8fafc', paddingBottom: '60px', fontFamily: "'Plus Jakarta Sans', sans-serif" };
const headerStyle = {
  background: 'linear-gradient(135deg, #072f2d 0%, #0c4a45 100%)',
  padding: '24px 36px',
  boxShadow: '0 4px 20px rgba(0,0,0,0.06)'
};
const logoIconBg = { backgroundColor: '#0f766e', padding: '10px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const titleStyle = { color: '#ffffff', margin: 0, fontSize: '18px', fontWeight: '900', letterSpacing: '0.4px' };
const subtitleStyle = { color: '#99f6e4', margin: '4px 0 0', fontSize: '12px', fontWeight: '500' };

const statsGridStyle = { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '14px', padding: '18px 36px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' };
const statCardStyle = { backgroundColor: '#f8fafc', padding: '14px 18px', borderRadius: '14px', border: '1px solid #e2e8f0' };
const statLabelStyle = { fontSize: '10px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' };
const statValueStyle = { margin: '4px 0 0', fontSize: '20px', fontWeight: '900' };
const statIconBg = { padding: '8px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' };

const tabBarStyle = { display: 'flex', gap: '10px', padding: '0 36px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', overflowX: 'auto' };
const tabBtnStyle = { padding: '14px 14px', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '13px', transition: 'all 0.15s', whiteSpace: 'nowrap' };

const bodyContainerStyle = { padding: '24px 36px' };
