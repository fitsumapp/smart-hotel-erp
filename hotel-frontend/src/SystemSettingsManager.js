import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Save, Building2, Receipt, Cpu, ToggleLeft, ToggleRight,
  ChevronDown, ChevronUp, Settings2, MapPin, Phone, Printer
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from './apiConfig';

const SystemSettingsManager = () => {
    const [settings, setSettings] = useState({
        hotel_name: '',
        tin_number: '',
        address: '',
        phone_number: '',
        vat_enabled: true,
        vat_percentage: 15,
        service_charge_enabled: true,
        service_charge_percentage: 10,
        fiscal_machine_no: '',
        reading_number: '',
        printer_paper_size: '80mm'
    });

    const [openSection, setOpenSection] = useState('receipt'); // Set 'receipt' as default open

    useEffect(() => {
        const API_URL = `${API_BASE_URL}/users/settings/`;
        const token = localStorage.getItem('access_token');
        axios.get(API_URL, { headers: { Authorization: `Bearer ${token}` } })
        .then(res => {
            const data = Array.isArray(res.data) ? res.data[0] : res.data;
            if (data) setSettings(data);
        })
        .catch(err => console.error("Failed to load settings:", err));
    }, []);

    const API_URL = `${API_BASE_URL}/users/settings/`;

    const handleSave = () => {
        const token = localStorage.getItem('access_token');
        axios.post(API_URL, settings, { headers: { Authorization: `Bearer ${token}` } })
        .then(() => alert("Settings updated successfully!"))
        .catch(err => alert("Error: " + (err.response?.data ? JSON.stringify(err.response.data) : "Save failed")));
    };

    const toggleSection = (section) => {
        setOpenSection(openSection === section ? null : section);
    };

    return (
        <div style={{ padding: '30px', color: '#0f172a', maxWidth: '900px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>
            {/* Header Section */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
                <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '12px', fontSize: '28px', fontWeight: '800', color: '#0f172a' }}>
                    <Settings2 color="#0f766e" size={32} /> System Configuration
                </h2>
                <button onClick={handleSave} style={saveBtn}><Save size={20} /> Save Changes</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>

                {/* 1. COMPREHENSIVE RECEIPT CONFIGURATION */}
                <AccordionSection
                    title="Receipt & Business Identity"
                    icon={<Receipt size={20} />}
                    isOpen={openSection === 'receipt'}
                    onToggle={() => toggleSection('receipt')}
                >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                        {/* Basic Info Row */}
                        <div style={gridStyle}>
                            <div>
                                <label style={labelStyle}>Hotel Name (Header)</label>
                                <div style={inputWrapper}><Building2 size={16} style={inputIcon}/><input style={inputWithIconStyle} value={settings.hotel_name || ''} onChange={e => setSettings({...settings, hotel_name: e.target.value})} placeholder="e.g. Grand Addis Hotel" /></div>
                            </div>
                            <div>
                                <label style={labelStyle}>TIN Number</label>
                                <input style={inputStyle} value={settings.tin_number || ''} onChange={e => setSettings({...settings, tin_number: e.target.value})} placeholder="0012345678" />
                            </div>
                        </div>

                        {/* Location and Contact Row */}
                        <div style={gridStyle}>
                            <div>
                                <label style={labelStyle}>Business Address</label>
                                <div style={inputWrapper}><MapPin size={16} style={inputIcon}/><input style={inputWithIconStyle} value={settings.address || ''} onChange={e => setSettings({...settings, address: e.target.value})} placeholder="Bole, Addis Ababa" /></div>
                            </div>
                            <div>
                                <label style={labelStyle}>Phone Number</label>
                                <div style={inputWrapper}><Phone size={16} style={inputIcon}/><input style={inputWithIconStyle} value={settings.phone_number || ''} onChange={e => setSettings({...settings, phone_number: e.target.value})} placeholder="+251 9..." /></div>
                            </div>
                        </div>

                        <hr style={{ border: '0.5px solid #e2e8f0', margin: '10px 0' }} />

                        {/* Financial Rates in the same section */}
                        <div style={gridStyle}>
                            <div style={innerCard}>
                                <div style={rowStyle}>
                                    <span style={{fontWeight: '600', fontSize: '14px', color: '#0f172a'}}>Enable VAT</span>
                                    <button onClick={() => setSettings({...settings, vat_enabled: !settings.vat_enabled})} style={btnIcon}>
                                        {settings.vat_enabled ? <ToggleRight color="#10b981" size={35} /> : <ToggleLeft color="#64748b" size={35} />}
                                    </button>
                                </div>
                                <label style={labelStyle}>VAT Rate (%)</label>
                                <input type="number" style={inputStyle} disabled={!settings.vat_enabled} value={settings.vat_percentage} onChange={e => setSettings({...settings, vat_percentage: parseFloat(e.target.value)})} />
                            </div>

                            <div style={innerCard}>
                                <div style={rowStyle}>
                                    <span style={{fontWeight: '600', fontSize: '14px', color: '#0f172a'}}>Enable Service Charge</span>
                                    <button onClick={() => setSettings({...settings, service_charge_enabled: !settings.service_charge_enabled})} style={btnIcon}>
                                        {settings.service_charge_enabled ? <ToggleRight color="#10b981" size={35} /> : <ToggleLeft color="#64748b" size={35} />}
                                    </button>
                                </div>
                                <label style={labelStyle}>Service Rate (%)</label>
                                <input type="number" style={inputStyle} disabled={!settings.service_charge_enabled} value={settings.service_charge_percentage} onChange={e => setSettings({...settings, service_charge_percentage: parseFloat(e.target.value)})} />
                            </div>
                        </div>

                        <hr style={{ border: '0.5px solid #e2e8f0', margin: '10px 0' }} />

                        {/* Fiscal Hardware settings under Receipt section */}
                        <div style={gridStyle}>
                            <div>
                                <label style={labelStyle}>Fiscal Machine Serial</label>
                                <div style={inputWrapper}><Cpu size={16} style={inputIcon}/><input style={inputWithIconStyle} value={settings.fiscal_machine_no || ''} onChange={e => setSettings({...settings, fiscal_machine_no: e.target.value})} placeholder="FG1000..." /></div>
                            </div>
                            <div>
                                <label style={labelStyle}>Last Reading No.</label>
                                <input style={inputStyle} value={settings.reading_number || ''} onChange={e => setSettings({...settings, reading_number: e.target.value})} />
                            </div>
                        </div>
                    </div>
                </AccordionSection>

                {/* 2. PRINTER SETTINGS CONFIGURATION */}
                <AccordionSection
                    title="Printer Settings"
                    icon={<Printer size={20} />}
                    isOpen={openSection === 'printer'}
                    onToggle={() => toggleSection('printer')}
                >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        <div>
                            <label style={labelStyle}>Receipt Paper Size</label>
                            <select 
                                style={inputStyle} 
                                value={settings.printer_paper_size || '80mm'} 
                                onChange={e => setSettings({...settings, printer_paper_size: e.target.value})}
                            >
                                <option value="80mm">80mm (Detailed Receipt)</option>
                                <option value="58mm">58mm (Concise Receipt)</option>
                            </select>
                            <p style={{ color: '#64748b', fontSize: '12px', marginTop: '10px' }}>
                                This will adjust the layout, font size, and layout format for all printed POS receipts, Guest Folios, and End of Day (Z/X) reports.
                            </p>
                        </div>
                    </div>
                </AccordionSection>

                {/* FUTURE SECTIONS PLACEHOLDER */}
                <AccordionSection
                    title="User & Security Settings"
                    icon={<Settings2 size={20} />}
                    isOpen={openSection === 'security'}
                    onToggle={() => toggleSection('security')}
                >
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Advanced security settings will appear here in future updates.</p>
                </AccordionSection>

            </div>
        </div>
    );
};

// --- Reusable Accordion Component ---
const AccordionSection = ({ title, icon, isOpen, onToggle, children }) => {
    return (
        <div style={{ backgroundColor: '#fff', borderRadius: '15px', border: '1px solid rgba(148,163,184,0.16)', overflow: 'hidden', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' }}>
            <div
                onClick={onToggle}
                style={{ padding: '20px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: isOpen ? '#f8fafc' : 'transparent', transition: '0.3s' }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <div style={{ color: isOpen ? '#0f766e' : '#64748b' }}>{icon}</div>
                    <span style={{ fontSize: '16px', fontWeight: '700', color: isOpen ? '#0f172a' : '#475569' }}>{title}</span>
                </div>
                {isOpen ? <ChevronUp size={20} color="#64748b" /> : <ChevronDown size={20} color="#64748b" />}
            </div>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        style={{ overflow: 'hidden' }}
                    >
                        <div style={{ padding: '25px', borderTop: '1px solid #f1f5f9', backgroundColor: '#fff' }}>
                            {children}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// --- Updated Styles ---
const gridStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' };
const innerCard = { backgroundColor: '#f8fafc', padding: '15px', borderRadius: '12px', border: '1px solid #cbd5e1' };
const labelStyle = { display: 'block', fontSize: '11px', marginBottom: '8px', color: '#64748b', textTransform: 'uppercase', fontWeight: '700' };
const inputWrapper = { position: 'relative', display: 'flex', alignItems: 'center' };
const inputIcon = { position: 'absolute', left: '12px', color: '#64748b' };
const inputStyle = { width: '100%', padding: '12px', backgroundColor: '#f1f5f9', border: '1px solid rgba(148,163,184,0.12)', borderRadius: '8px', color: '#0f172a', outline: 'none' };
const inputWithIconStyle = { ...inputStyle, paddingLeft: '40px' };
const rowStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' };
const btnIcon = { background: 'none', border: 'none', cursor: 'pointer', padding: 0 };
const saveBtn = { padding: '12px 25px', backgroundColor: '#0f766e', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: '900', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' };

export default SystemSettingsManager;