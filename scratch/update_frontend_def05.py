with open('hotel-frontend/src/SystemSettingsManager.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update lucide-react import
target_import = """import {
  Save, Building2, Receipt, Cpu, ToggleLeft, ToggleRight,
  ChevronDown, ChevronUp, Settings2, MapPin, Phone, Printer, Clock
} from 'lucide-react';"""

replacement_import = """import {
  Save, Building2, Receipt, Cpu, ToggleLeft, ToggleRight,
  ChevronDown, ChevronUp, Settings2, MapPin, Phone, Printer, Clock, AlertTriangle
} from 'lucide-react';"""

assert target_import in text, "target_import not found"
text = text.replace(target_import, replacement_import, 1)

# 2. Update state and handleSave
target_state = """        kds_prep_target_minutes: 15,
        kds_delay_warning_minutes: 20,
        bar_fulfillment_target_minutes: 5,
        bar_delay_warning_minutes: 10
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
    };"""

replacement_state = """        kds_prep_target_minutes: 15,
        kds_delay_warning_minutes: 20,
        bar_fulfillment_target_minutes: 5,
        bar_delay_warning_minutes: 10,
        near_expiry_warning_days: 30
    });

    const [validationError, setValidationError] = useState('');
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
        const warningDays = parseInt(settings.near_expiry_warning_days, 10);
        if (isNaN(warningDays) || warningDays < 1 || warningDays > 365) {
            setValidationError("Near-expiry warning window must be a positive integer between 1 and 365 days.");
            alert("Validation Error: Near-expiry warning window must be a positive integer between 1 and 365 days.");
            return;
        }
        setValidationError('');
        const token = localStorage.getItem('access_token');
        const payload = {
            ...settings,
            near_expiry_warning_days: warningDays
        };
        axios.post(API_URL, payload, { headers: { Authorization: `Bearer ${token}` } })
        .then(() => alert("Settings updated successfully!"))
        .catch(err => alert("Error: " + (err.response?.data ? JSON.stringify(err.response.data) : "Save failed")));
    };"""

assert target_state in text, "target_state not found"
text = text.replace(target_state, replacement_state, 1)

# 3. Add AccordionSection for Inventory
target_accordion = """                {/* FUTURE SECTIONS PLACEHOLDER */}
                <AccordionSection
                    title="User & Security Settings"
                    icon={<Settings2 size={20} />}
                    isOpen={openSection === 'security'}
                    onToggle={() => toggleSection('security')}
                >
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Advanced security settings will appear here in future updates.</p>
                </AccordionSection>"""

replacement_accordion = """                {/* 4. INVENTORY & BATCH SURVEILLANCE */}
                <AccordionSection
                    title="Inventory & Expiry Surveillance"
                    icon={<AlertTriangle size={20} />}
                    isOpen={openSection === 'inventory'}
                    onToggle={() => toggleSection('inventory')}
                >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        <div style={innerCard}>
                            <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', fontWeight: '800', color: '#0f766e', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                📦 Automated Expiry & Batch Surveillance
                            </h4>
                            <div style={{ marginBottom: '10px' }}>
                                <label style={labelStyle}>Near-Expiry Warning Window (Days)</label>
                                <input 
                                    id="input-near-expiry-warning-days"
                                    type="number" 
                                    min="1"
                                    max="365"
                                    style={inputStyle} 
                                    value={settings.near_expiry_warning_days ?? 30} 
                                    onChange={e => setSettings({...settings, near_expiry_warning_days: e.target.value === '' ? '' : parseInt(e.target.value, 10)})} 
                                />
                                <span style={{ fontSize: '12px', color: '#64748b', display: 'block', marginTop: '6px' }}>
                                    Surveillance window in days before batch expiration to trigger automated operational routing and near-expiry warning alerts (Default: 30 days, Allowed: 1-365).
                                </span>
                                {validationError && (
                                    <span style={{ fontSize: '12px', color: '#ef4444', display: 'block', marginTop: '6px', fontWeight: '600' }}>
                                        {validationError}
                                    </span>
                                )}
                            </div>
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
                </AccordionSection>"""

assert target_accordion in text, "target_accordion not found"
text = text.replace(target_accordion, replacement_accordion, 1)

with open('hotel-frontend/src/SystemSettingsManager.js', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print("Updated hotel-frontend/src/SystemSettingsManager.js successfully!")

