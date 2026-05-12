import React, { useEffect, useMemo, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import {
  PlusCircle, X, Trash2, Edit3, ImageIcon,
  LayoutGrid, List, CheckCircle, User, RefreshCw, Wrench,
  Globe, CalendarCheck2, ClipboardList, ScanLine,
  Receipt
} from 'lucide-react';
import { API_BASE_URL, getTenantSchemaHint } from './apiConfig';

const API_BASE = `${API_BASE_URL}/users/rooms/`;
const RESERVE_API_BASE = `${API_BASE_URL}/users/rooms`;
const RESERVATIONS_API = `${API_BASE_URL}/users/reservations/`;
const QR_CHECKIN_API = `${API_BASE_URL}/users/reservations/qr-checkin/`;
const PUBLIC_SITE_INFO_API = `${API_BASE_URL}/users/public-site/`;

const allAmenities = ['WiFi', 'TV', 'Shower', 'Breakfast', 'Mini Bar', 'AC', 'Balcony'];
const optionalEmptyFields = new Set([
  'weekend_price',
  'holiday_price',
  'description',
  'cancellation_policy',
  'video_url',
  'view_360_url',
]);

const sectionContent = {
  rooms: {
    title: 'Rooms',
    subtitle: 'Manage room inventory, pricing, availability, and publishing without changing the current room workflow.',
  },
  reservation_booking: {
    title: 'Reservation and Booking',
    subtitle: 'Prepare rooms for public booking, validate online availability, and launch Chapa reservation deposits.',
  },
  checkin_checkout: {
    title: 'Check In / Check Out',
    subtitle: 'Move guests from reservation to occupied, then to cleaning, directly from the front office screen.',
  },
  night_audit: {
    title: 'Night Audit',
    subtitle: 'Review online reservations, occupied rooms, and cleaning status before you close the day.',
  },
};

const initialFormState = {
  name: '',
  room_number: '',
  room_type: 'Single',
  floor_number: 1,
  description: '',
  base_price: '',
  weekend_price: '',
  holiday_price: '',
  discount_percent: 0,
  extra_bed_price: 0,
  max_adults: 2,
  max_children: 1,
  bed_type: 'King',
  num_beds: 1,
  amenities: [],
  common_amenities: [],
  status: 'Available',
  min_stay: 1,
  check_in_time: '14:00',
  check_out_time: '11:00',
  cancellation_policy: '',
  video_url: '',
  view_360_url: '',
  is_available_online: false,
  online_deposit_type: 'Fixed',
  advance_payment_amount: 0,
  booking_source: 'front_desk',
};

const RoomManager = ({ activeSection = 'rooms' }) => {
  const tenantSchema = getTenantSchemaHint();
  const [rooms, setRooms] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isReservationModalOpen, setIsReservationModalOpen] = useState(false);
  
  // PMS Modals
  const [isDigitalCheckInOpen, setIsDigitalCheckInOpen] = useState(false);
  const [isFolioOpen, setIsFolioOpen] = useState(false);
  const [isFinalBillOpen, setIsFinalBillOpen] = useState(false);
  
  const [viewMode, setViewMode] = useState('grid');
  const [activeTab, setActiveTab] = useState('basic');
  const [loading, setLoading] = useState(false);
  const [mainImage, setMainImage] = useState(null);
  const [image2, setImage2] = useState(null);
  const [image3, setImage3] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState(initialFormState);
  const [reservationDraft, setReservationDraft] = useState({});
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [qrScanToken, setQrScanToken] = useState('');
  const [publicSiteUrl, setPublicSiteUrl] = useState('');
  const [actionLoading, setActionLoading] = useState({});
  const [scanSuccessData, setScanSuccessData] = useState(null);

  // PMS States
  const [maintenanceLogs, setMaintenanceLogs] = useState([]);
  const [newLog, setNewLog] = useState({ issue_title: '', notes: '' });
  const [roomHistory, setRoomHistory] = useState([]);
  const [digitalRegForm, setDigitalRegForm] = useState({
    full_name: '', phone: '', nationality: '', id_type: 'national_id', id_number: ''
  });
  const [folioCharges, setFolioCharges] = useState([]);
  const [newCharge, setNewCharge] = useState({ description: '', amount: '' });
  const [finalBillData, setFinalBillData] = useState(null);
  const [activeReservationForFolio, setActiveReservationForFolio] = useState(null);

  useEffect(() => { fetchRooms(); fetchReservations(); fetchPublicSiteInfo(); }, []);

  const fetchRooms = async () => {
    try {
      const res = await axios.get(API_BASE);
      setRooms(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchReservations = async () => {
    try {
      const res = await axios.get(RESERVATIONS_API);
      setReservations(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchPublicSiteInfo = async () => {
    try {
      const res = await axios.get(PUBLIC_SITE_INFO_API);
      setPublicSiteUrl(res.data?.public_site_url || '');
    } catch (err) { console.error(err); }
  };

  const fetchMaintenanceLogs = async (roomId) => {
    try {
      const res = await axios.get(`${RESERVE_API_BASE}/${roomId}/maintenance/`);
      setMaintenanceLogs(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchRoomHistory = async (roomId) => {
    try {
      const res = await axios.get(`${RESERVE_API_BASE}/${roomId}/history/`);
      setRoomHistory(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchFolioCharges = async (reservationId) => {
    try {
      const res = await axios.get(`${RESERVATIONS_API}${reservationId}/folio/`);
      setFolioCharges(res.data);
    } catch (err) { console.error(err); }
  };

  const getCounts = (status) => rooms.filter((room) => room.status === status).length;
  const bookedOnlineCount = useMemo(
    () => rooms.filter((room) => room.status === 'Reserved' && room.booking_source === 'online').length,
    [rooms]
  );
  const isRoomsSection = activeSection === 'rooms';
  const isReservationSection = activeSection === 'reservation_booking';
  const isCheckInSection = activeSection === 'checkin_checkout';
  const isNightAuditSection = activeSection === 'night_audit';
  const visibleRooms = useMemo(() => {
    if (isCheckInSection) return rooms.filter((room) => ['Reserved', 'Occupied', 'Cleaning'].includes(room.status));
    if (isReservationSection) return rooms.filter((room) => room.is_available_online || room.booking_source === 'online' || room.status === 'Reserved');
    return rooms;
  }, [rooms, isCheckInSection, isReservationSection]);
  const visibleReservations = useMemo(() => {
    if (isCheckInSection) return reservations.filter((item) => ['confirmed', 'pending', 'checked_in'].includes(item.status));
    if (isNightAuditSection) return reservations.filter((item) => ['confirmed', 'checked_in', 'checked_out'].includes(item.status));
    return reservations;
  }, [reservations, isCheckInSection, isNightAuditSection]);

  const parseArrayField = (value) => {
    if (Array.isArray(value)) return value;
    if (!value) return [];
    try {
      const parsed = typeof value === 'string' ? JSON.parse(value) : value;
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) { return []; }
  };

  const startEdit = (room) => {
    setEditingId(room.id);
    setFormData({
      ...initialFormState,
      ...room,
      amenities: parseArrayField(room.amenities),
      common_amenities: parseArrayField(room.common_amenities),
      is_available_online: Boolean(room.is_available_online),
      online_deposit_type: room.online_deposit_type || 'Fixed',
      advance_payment_amount: room.advance_payment_amount ?? 0,
      booking_source: room.booking_source || 'front_desk',
    });
    setMainImage(null);
    setImage2(null);
    setImage3(null);
    setIsModalOpen(true);
    setActiveTab('basic');
    fetchMaintenanceLogs(room.id);
    fetchRoomHistory(room.id);
  };

  const openCreateModal = () => {
    setEditingId(null);
    setFormData(initialFormState);
    setMainImage(null);
    setImage2(null);
    setImage3(null);
    setIsModalOpen(true);
    setActiveTab('basic');
    setMaintenanceLogs([]);
    setRoomHistory([]);
  };

  const handlePublish = async (e) => {
    e.preventDefault();
    setLoading(true);
    const data = new FormData();

    Object.keys(formData).forEach((key) => {
      if (['amenities', 'common_amenities'].includes(key)) {
        data.append(key, JSON.stringify(formData[key]));
      } else if (optionalEmptyFields.has(key) && formData[key] === '') {
        return;
      } else if (typeof formData[key] === 'boolean') {
        data.append(key, String(formData[key]));
      } else if (formData[key] !== null && formData[key] !== undefined) {
        data.append(key, formData[key]);
      }
    });

    if (mainImage) { data.append('main_image', mainImage); }
    if (image2) { data.append('image_2', image2); }
    if (image3) { data.append('image_3', image3); }

    try {
      const config = { headers: { 'Content-Type': 'multipart/form-data' } };
      if (editingId) {
        await axios.patch(`${API_BASE}${editingId}/`, data, config);
      } else {
        await axios.post(API_BASE, data, config);
      }
      setIsModalOpen(false);
      fetchRooms();
      alert('Room saved successfully.');
    } catch (err) {
      console.error(err);
      alert('Unable to save room.');
    } finally { setLoading(false); }
  };

  // --- Maintenance Actions ---
  const handleAddMaintenanceLog = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${RESERVE_API_BASE}/${editingId}/maintenance/`, newLog);
      setNewLog({ issue_title: '', notes: '' });
      fetchMaintenanceLogs(editingId);
    } catch (err) { alert('Failed to add maintenance log.'); }
  };

  const handleResolveMaintenance = async (logId) => {
    try {
      await axios.patch(`${API_BASE_URL}/users/maintenance/${logId}/`, { status: 'resolved' });
      fetchMaintenanceLogs(editingId);
    } catch (err) { alert('Failed to resolve log.'); }
  };

  // --- Digital Check-In ---
  const openDigitalCheckIn = (room) => {
    const res = reservations.find(r => r.room === room.id && ['confirmed', 'pending'].includes(r.status));
    setSelectedRoom(room);
    setDigitalRegForm({
      full_name: res?.guest_name || '',
      phone: res?.guest_phone || '',
      nationality: '',
      id_type: 'national_id',
      id_number: ''
    });
    setIsDigitalCheckInOpen(true);
  };

  const handleDigitalCheckIn = async (e) => {
    e.preventDefault();
    setActionLoading(prev => ({ ...prev, [selectedRoom.id]: 'checkin' }));
    try {
      await axios.post(`${RESERVE_API_BASE}/${selectedRoom.id}/digital-checkin/`, {
        guest_profile: digitalRegForm
      });
      setIsDigitalCheckInOpen(false);
      fetchRooms();
      fetchReservations();
      alert('Guest checked in and registered successfully.');
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to check in.');
    } finally {
      setActionLoading(prev => ({ ...prev, [selectedRoom.id]: null }));
    }
  };

  // --- Folio / Billing ---
  const openFolio = (room) => {
    const res = reservations.find(r => r.room === room.id && r.status === 'checked_in');
    if (!res) { alert('No active reservation found for this room.'); return; }
    setSelectedRoom(room);
    setActiveReservationForFolio(res);
    fetchFolioCharges(res.id);
    setIsFolioOpen(true);
  };

  const handleAddFolioCharge = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${RESERVATIONS_API}${activeReservationForFolio.id}/folio/`, newCharge);
      setNewCharge({ description: '', amount: '' });
      fetchFolioCharges(activeReservationForFolio.id);
    } catch (err) { alert('Failed to add charge.'); }
  };

  const handleDeleteFolioCharge = async (chargeId) => {
    try {
      await axios.delete(`${API_BASE_URL}/users/folio/${chargeId}/`);
      fetchFolioCharges(activeReservationForFolio.id);
    } catch (err) { alert('Failed to delete charge.'); }
  };

  // --- Final Checkout Bill ---
  const openFinalBill = async (room) => {
    const res = reservations.find(r => r.room === room.id && r.status === 'checked_in');
    if (!res) { alert('No active reservation to check out.'); return; }
    setSelectedRoom(room);
    setActiveReservationForFolio(res);
    setActionLoading(prev => ({ ...prev, [room.id]: 'checkout' }));
    try {
      const response = await axios.get(`${RESERVATIONS_API}${res.id}/final-bill/`);
      setFinalBillData(response.data);
      setIsFinalBillOpen(true);
    } catch (err) {
      alert('Failed to generate final bill.');
    } finally {
      setActionLoading(prev => ({ ...prev, [room.id]: null }));
    }
  };

  const printRef = useRef();

  const handlePrintBill = () => {
    if (!printRef.current) return;
    const printContent = printRef.current.innerHTML;
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    const paperSize = finalBillData?.printer_paper_size || '80mm';
    
    printWindow.document.write(`
      <html>
        <head>
          <title>Guest Bill</title>
          <style>
            @page { size: auto; margin: 0; }
            body { 
              margin: 0; 
              padding: 0; 
              background: #fff; 
              color: #000; 
              font-family: 'Courier New', Courier, monospace; 
              -webkit-print-color-adjust: exact;
            }
            * { font-family: inherit; }
            .thermal-receipt {
              width: ${paperSize};
              margin: 0;
              padding: 2mm;
              text-transform: uppercase;
              line-height: 1.2;
              font-size: 12px;
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
            table { width: 100% !important; border-collapse: collapse !important; }
            th { text-align: left !important; border-bottom: 1px dashed #000 !important; padding: 2px 0 !important; }
            td { padding: 2px 0 !important; }
          </style>
        </head>
        <body>
          <div class="thermal-receipt">
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

  const handleEnhancedCheckout = async () => {
    setActionLoading(prev => ({ ...prev, checkout_btn: true }));
    try {
      const res = await axios.post(`${RESERVATIONS_API}${activeReservationForFolio.id}/enhanced-checkout/`);
      setFinalBillData(res.data.final_bill); // Update with final processed bill
      
      // We need to wait for the state update and render before printing
      setTimeout(() => { 
        handlePrintBill();
        setIsFinalBillOpen(false);
        fetchRooms();
        fetchReservations();
      }, 500);
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to checkout.');
    } finally {
      setActionLoading(prev => ({ ...prev, checkout_btn: false }));
    }
  };

  // --- Normal reservation logic ---
  const openReservationModal = (room) => {
    if (room.status === 'Maintenance') { alert('Room is out of order.'); return; }
    const draft = reservationDraft[room.id] || {};
    setSelectedRoom(room);
    setReservationDraft((prev) => ({
      ...prev,
      [room.id]: {
        guest_name: draft.guest_name || '', guest_email: draft.guest_email || '',
        guest_phone: draft.guest_phone || '', check_in_date: draft.check_in_date || '',
        check_out_date: draft.check_out_date || '', adults: draft.adults || 1,
        children: draft.children || 0, notes: draft.notes || '', pay_now: draft.pay_now ?? false,
      },
    }));
    setIsReservationModalOpen(true);
  };

  const updateRoomActionLoading = (roomId, value) => {
    setActionLoading((prev) => ({ ...prev, [roomId]: value }));
  };

  const handleReserveNow = async (room) => {
    const draft = reservationDraft[room.id] || {};
    updateRoomActionLoading(room.id, 'reserve');
    try {
      const res = await axios.post(`${RESERVE_API_BASE}/${room.id}/reserve-now/`, {
        source: 'reception',
        pay_now: Boolean(draft.pay_now),
        guest_name: draft.guest_name || `${room.name} Guest`,
        guest_email: draft.guest_email || '',
        guest_phone: draft.guest_phone || '',
        check_in_date: draft.check_in_date,
        check_out_date: draft.check_out_date,
        adults: draft.adults || 1,
        children: draft.children || 0,
        notes: draft.notes || '',
      });
      await fetchRooms();
      await fetchReservations();
      setIsReservationModalOpen(false);
      if (res.data?.checkout_url) { window.open(res.data.checkout_url, '_blank', 'noopener,noreferrer'); } 
      else { alert(res.data?.message || 'Reservation created successfully.'); }
    } catch (err) { alert(err.response?.data?.error || 'Unable to start reservation.'); }
    finally { updateRoomActionLoading(room.id, null); }
  };

  const handleQrCheckIn = async () => {
    if (!qrScanToken) return;
    try {
      const res = await axios.post(QR_CHECKIN_API, { qr_token: qrScanToken });
      setQrScanToken('');
      await fetchRooms();
      await fetchReservations();
      if (res.data.reservation) { setScanSuccessData(res.data.reservation); } 
      else { alert('Guest checked in successfully.'); }
    } catch (err) { alert(err.response?.data?.error || 'Unable to process QR check-in.'); }
  };

  const handleDelete = async (roomId) => {
    if (!window.confirm('Delete this room?')) return;
    try { await axios.delete(`${API_BASE}${roomId}/`); fetchRooms(); } 
    catch (err) { alert('Unable to delete room.'); }
  };

  const info = sectionContent[activeSection] || sectionContent.rooms;

  return (
    <div className="print-container" style={{ padding: '20px', backgroundColor: '#020617', minHeight: '100vh', color: '#fff' }}>
      <style>{`
        @media print {
          @page { size: auto; margin: 5mm; }
          body { background: white !important; -webkit-print-color-adjust: exact; margin: 0; }
          .print-container { background: white !important; padding: 0 !important; color: black !important; min-height: auto !important; }
          .print-container > *:not(.print-allow):not(style) { display: none !important; }
          .print-allow { display: block !important; position: static !important; width: 100% !important; height: auto !important; }
          
          .print-modal-overlay { background: white !important; padding: 0 !important; }
          .print-modal-content { max-width: 100% !important; border: none !important; box-shadow: none !important; padding: 0 !important; background: white !important; transform: none !important; }
          
          #print-bill, #print-bill * { color: black !important; visibility: visible !important; }
          #print-bill { display: block !important; width: 100% !important; padding: 20px !important; }
        }
      `}</style>
      
      <div style={heroCard}>
        <div>
          <p style={heroEyebrow}>Front Office</p>
          <h2 style={heroTitle}>{info.title}</h2>
          <p style={heroSubtitle}>{info.subtitle}</p>
        </div>
        <div style={heroBadges}>
          <span style={heroPill}><Globe size={14} /> Public Booking Engine</span>
          <span style={heroPill}><CalendarCheck2 size={14} /> Reservation Validation</span>
          <span style={heroPill}><ClipboardList size={14} /> Chapa Ready</span>
        </div>
      </div>

      <div style={statsGrid}>
        <div style={statCard}>
          <div style={{ ...iconBox, backgroundColor: '#f0fdf4' }}><CheckCircle size={18} color="#22c55e" /></div>
          <div><p style={statLabel}>AVAILABLE</p><h3 style={statCount}>{getCounts('Available')}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{ ...iconBox, backgroundColor: '#eff6ff' }}><Globe size={18} color="#2563eb" /></div>
          <div><p style={statLabel}>BOOKED ONLINE</p><h3 style={statCount}>{bookedOnlineCount}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{ ...iconBox, backgroundColor: '#fef2f2' }}><User size={18} color="#ef4444" /></div>
          <div><p style={statLabel}>OCCUPIED</p><h3 style={statCount}>{getCounts('Occupied')}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{ ...iconBox, backgroundColor: '#fffbeb' }}><RefreshCw size={18} color="#f59e0b" /></div>
          <div><p style={statLabel}>CLEANING</p><h3 style={statCount}>{getCounts('Cleaning')}</h3></div>
        </div>
        <div style={statCard}>
          <div style={{ ...iconBox, backgroundColor: '#f8fafc' }}><Wrench size={18} color="#64748b" /></div>
          <div><p style={statLabel}>MAINTENANCE</p><h3 style={statCount}>{getCounts('Maintenance')}</h3></div>
        </div>
      </div>

      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
          {!isNightAuditSection && (
            <div style={switcherContainer}>
              <button onClick={() => setViewMode('grid')} style={{ ...switchBtn, backgroundColor: viewMode === 'grid' ? '#3f5d45' : 'transparent', color: viewMode === 'grid' ? '#fff' : '#94a3b8' }}><LayoutGrid size={16} /> Grid</button>
              <button onClick={() => setViewMode('list')} style={{ ...switchBtn, backgroundColor: viewMode === 'list' ? '#3f5d45' : 'transparent', color: viewMode === 'list' ? '#fff' : '#94a3b8' }}><List size={16} /> List</button>
            </div>
          )}
          {isRoomsSection && <button onClick={openCreateModal} style={addNewBtn}><PlusCircle size={18} /> Add New Room</button>}
          {isReservationSection && <button onClick={() => window.open(publicSiteUrl || `/customer-dashboard${tenantSchema ? `?tenant=${tenantSchema}` : ''}`, '_blank', 'noopener,noreferrer')} style={addNewBtn}><Globe size={18} /> Open Public Site</button>}
        </div>
      </div>

      {(isReservationSection || isCheckInSection || isNightAuditSection) && <div style={opsGrid}>
        <div style={opsCard}>
          <div style={opsTitleRow}><ScanLine size={18} color="#60a5fa" /><strong>QR Check-in Scan</strong></div>
          <p style={opsText}>Paste or scan the guest QR token here to complete reception check-in instantly.</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '10px', marginTop: '14px' }}>
            <input value={qrScanToken} onChange={(e) => setQrScanToken(e.target.value)} placeholder="Paste QR token" style={miniInput} />
            <button type="button" onClick={handleQrCheckIn} style={{ ...actionBtn, ...checkInBtn }}>Scan</button>
          </div>
        </div>
        <div style={opsCard}>
          <div style={opsTitleRow}><ClipboardList size={18} color="#f59e0b" /><strong>{isNightAuditSection ? 'Night Audit Queue' : 'Recent Reservations'}</strong></div>
          <div style={{ display: 'grid', gap: '10px' }}>
            {visibleReservations.slice(0, 6).map((reservation) => (
              <div key={reservation.id} style={reservationRow}>
                <div>
                  <strong>{reservation.guest_name}</strong>
                  <p style={reservationMeta}>Room {reservation.room_number} • {reservation.check_in_date} to {reservation.check_out_date}</p>
                </div>
                <span style={reservationStatusPill(reservation.status)}>{reservation.status}</span>
              </div>
            ))}
            {!visibleReservations.length && <p style={{ margin: 0, color: '#94a3b8', fontSize: '13px' }}>No reservations yet.</p>}
          </div>
        </div>
      </div>}

      {isNightAuditSection ? (
        <div style={auditBoard}>
          <div style={auditCard}>
            <h3 style={{ marginTop: 0 }}>Night Audit Snapshot</h3>
            <p style={opsText}>Review arrivals, in-house guests, and cleaning tasks before closing the shift.</p>
            <div style={auditStatsGrid}>
              <div style={auditMiniCard}><strong>{visibleReservations.filter((item) => item.status === 'confirmed').length}</strong><span>Confirmed arrivals</span></div>
              <div style={auditMiniCard}><strong>{visibleReservations.filter((item) => item.status === 'checked_in').length}</strong><span>In-house guests</span></div>
              <div style={auditMiniCard}><strong>{rooms.filter((room) => room.status === 'Cleaning').length}</strong><span>Cleaning queue</span></div>
              <div style={auditMiniCard}><strong>{bookedOnlineCount}</strong><span>Booked online</span></div>
            </div>
          </div>
        </div>
      ) : viewMode === 'grid' ? (
        <div style={roomsGrid}>
          {visibleRooms.map((room) => {
            const reservedOnline = room.status === 'Reserved' && room.booking_source === 'online';
            const draft = reservationDraft[room.id] || {};
            const busyAction = actionLoading[room.id];
            const isMaintenance = room.status === 'Maintenance';
            return (
              <motion.div layout key={room.id} style={{ ...roomCard, ...(reservedOnline ? reservedRoomCard : {}) }}>
                <div style={cardImgWrapper}>
                  {room.main_image ? <img src={room.main_image} style={imgStyle} alt="room" /> : <div style={noImg}><ImageIcon size={20} /></div>}
                  <div style={priceTagSmall}>{room.base_price} ETB</div>
                  {reservedOnline && <div style={reservedBadge}>Reserved</div>}
                </div>
                <div style={{ padding: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                    <div>
                      <h4 style={{ margin: 0, fontSize: '14px' }}>{room.name}</h4>
                      <p style={{ fontSize: '11px', color: '#94a3b8' }}>#{room.room_number} • {room.room_type}</p>
                    </div>
                    <span style={roomStatusPill(room.status, reservedOnline)}>{room.status}</span>
                  </div>

                  {!isCheckInSection && (
                    <div style={bookingPanel}>
                      <input style={miniInput} type="date" value={draft.check_in_date || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [room.id]: { ...draft, check_in_date: e.target.value } }))} />
                      <input style={miniInput} type="date" value={draft.check_out_date || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [room.id]: { ...draft, check_out_date: e.target.value } }))} />
                      <button type="button" onClick={() => openReservationModal(room)} disabled={busyAction === 'reserve' || isMaintenance} style={{ ...actionBtn, ...reserveBtn, opacity: isMaintenance ? 0.5 : 1 }} title={isMaintenance ? 'Out of Order' : ''}>
                        {busyAction === 'reserve' ? 'Wait...' : 'Reserve'}
                      </button>
                    </div>
                  )}

                  {isCheckInSection && (
                    <div style={frontDeskActions}>
                      <button type="button" onClick={() => openDigitalCheckIn(room)} disabled={busyAction === 'checkin' || isMaintenance || room.status === 'Occupied'} style={{ ...actionBtn, ...checkInBtn, opacity: (isMaintenance || room.status === 'Occupied') ? 0.5 : 1 }}>
                        {busyAction === 'checkin' ? 'Wait...' : 'Check-in'}
                      </button>
                      <button type="button" onClick={() => openFinalBill(room)} disabled={busyAction === 'checkout' || room.status !== 'Occupied'} style={{ ...actionBtn, ...checkOutBtn, opacity: room.status !== 'Occupied' ? 0.5 : 1 }}>
                        {busyAction === 'checkout' ? 'Wait...' : 'Check-out'}
                      </button>
                    </div>
                  )}
                  
                  {room.status === 'Occupied' && (
                    <div style={{ marginTop: 10 }}>
                      <button onClick={() => openFolio(room)} style={{ ...saveBtn, padding: 8, fontSize: 12, marginTop: 0, backgroundColor: 'rgba(167,139,250,0.2)', color: '#c4b5fd', border: '1px solid rgba(167,139,250,0.3)' }}>
                        <Receipt size={14}/> View Folio
                      </button>
                    </div>
                  )}

                  <div style={cardActionsSmall}>
                    <span style={{ fontSize: '10px', color: reservedOnline ? '#bfdbfe' : '#bef264' }}>
                      {reservedOnline ? 'Online reservation locked' : `Source: ${room.booking_source || 'front_desk'}`}
                    </span>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <Edit3 size={14} style={{ cursor: 'pointer', color: '#60a5fa' }} onClick={() => startEdit(room)} />
                      <Trash2 size={14} style={{ cursor: 'pointer', color: '#ef4444' }} onClick={() => handleDelete(room.id)} />
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      ) : (
        <div style={listContainer}>
          <table style={tableStyle}>
            <thead>
              <tr style={theadTr}>
                <th style={thStyle}>Room</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Price</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Online</th>
                <th style={thStyle}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleRooms.map((room) => {
                const reservedOnline = room.status === 'Reserved' && room.booking_source === 'online';
                return (
                  <tr key={room.id} style={{ ...trStyle, ...(reservedOnline ? listReservedRow : {}) }}>
                    <td style={tdStyle}>{room.name} (#{room.room_number})</td>
                    <td style={tdStyle}>{room.room_type}</td>
                    <td style={tdStyle}>{room.base_price} ETB</td>
                    <td style={tdStyle}><span style={roomStatusPill(room.status, reservedOnline)}>{room.status}</span></td>
                    <td style={tdStyle}>{room.is_available_online ? 'Enabled' : 'Offline'}</td>
                    <td style={tdStyle}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <Edit3 size={16} color="#60a5fa" style={{ cursor: 'pointer' }} onClick={() => startEdit(room)} />
                        <Trash2 size={16} color="#ef4444" style={{ cursor: 'pointer' }} onClick={() => handleDelete(room.id)} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <AnimatePresence>
        {/* ROOM EDIT MODAL */}
        {isModalOpen && (
          <div style={modalOverlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={modalContent}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px', gap: '16px' }}>
                <div>
                  <h3 style={{ margin: 0 }}>{editingId ? 'Edit Room' : 'Add Room'}</h3>
                  <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '13px' }}>Expanded for front office, online booking, and public room publishing.</p>
                </div>
                <X style={{ cursor: 'pointer', flexShrink: 0 }} onClick={() => setIsModalOpen(false)} />
              </div>

              <div style={tabsWrapperSmall}>
                {['basic', 'pricing', 'capacity', 'amenities', 'media', 'status', 'maintenance', 'history'].map((tab) => {
                  if (!editingId && ['maintenance', 'history'].includes(tab)) return null;
                  return (
                    <button key={tab} type="button" onClick={() => setActiveTab(tab)} style={activeTab === tab ? activeTabStyleSmall : tabBtnStyleSmall}>
                      {tab.toUpperCase()}
                    </button>
                  );
                })}
              </div>

              <form onSubmit={handlePublish} style={{ maxHeight: '72vh', overflowY: 'auto', paddingRight: '10px' }}>
                {activeTab === 'basic' && (
                  <div style={grid2}>
                    <input style={styledInput} placeholder="Room Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                    <input style={styledInput} placeholder="Room Number" value={formData.room_number} onChange={(e) => setFormData({ ...formData, room_number: e.target.value })} required />
                    <select style={styledInput} value={formData.room_type} onChange={(e) => setFormData({ ...formData, room_type: e.target.value })}>
                      <option value="Single">Single</option>
                      <option value="Double">Double</option>
                      <option value="Suite">Suite</option>
                    </select>
                    <input type="number" style={styledInput} placeholder="Floor" value={formData.floor_number} onChange={(e) => setFormData({ ...formData, floor_number: e.target.value })} />
                    <textarea style={{ ...styledInput, gridColumn: 'span 2' }} placeholder="Description" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
                  </div>
                )}
                {activeTab === 'pricing' && (
                  <div style={grid2}>
                    <input type="number" style={styledInput} placeholder="Base Price" value={formData.base_price} onChange={(e) => setFormData({ ...formData, base_price: e.target.value })} required />
                    <input type="number" style={styledInput} placeholder="Weekend Price" value={formData.weekend_price} onChange={(e) => setFormData({ ...formData, weekend_price: e.target.value })} />
                    <label style={checkboxField}>
                      <input type="checkbox" checked={formData.is_available_online} onChange={(e) => setFormData({ ...formData, is_available_online: e.target.checked })} />
                      Available on public website
                    </label>
                  </div>
                )}
                {activeTab === 'capacity' && (
                  <div style={grid2}>
                    <input type="number" style={styledInput} placeholder="Max Adults" value={formData.max_adults} onChange={(e) => setFormData({ ...formData, max_adults: e.target.value })} />
                    <input type="number" style={styledInput} placeholder="Max Children" value={formData.max_children} onChange={(e) => setFormData({ ...formData, max_children: e.target.value })} />
                  </div>
                )}
                {activeTab === 'amenities' && (
                  <div style={{ display: 'grid', gap: '18px' }}>
                    <div>
                      <p style={sectionLabel}>In-room amenities</p>
                      <div style={amenitiesGrid}>
                        {allAmenities.map((item) => (
                          <label key={item} style={checkboxLabel}>
                            <input type="checkbox" checked={formData.amenities.includes(item)} onChange={() => {
                              const updated = formData.amenities.includes(item) ? formData.amenities.filter((a) => a !== item) : [...formData.amenities, item];
                              setFormData({ ...formData, amenities: updated });
                            }} /> {item}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                {activeTab === 'media' && (
                  <div style={{ display: 'grid', gap: '15px' }}>
                    <div style={uploadZone}>
                      <p style={{ margin: '0 0 10px', fontSize: 13, color: '#94a3b8' }}>Main Photo</p>
                      <input type="file" onChange={(e) => setMainImage(e.target.files[0])} />
                    </div>
                    <div style={uploadZone}>
                      <p style={{ margin: '0 0 10px', fontSize: 13, color: '#94a3b8' }}>Photo 2</p>
                      <input type="file" onChange={(e) => setImage2(e.target.files[0])} />
                    </div>
                    <div style={uploadZone}>
                      <p style={{ margin: '0 0 10px', fontSize: 13, color: '#94a3b8' }}>Photo 3</p>
                      <input type="file" onChange={(e) => setImage3(e.target.files[0])} />
                    </div>
                  </div>
                )}
                {activeTab === 'status' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <select style={styledInput} value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                      <option value="Available">Available</option>
                      <option value="Occupied">Occupied</option>
                      <option value="Cleaning">Cleaning</option>
                      <option value="Maintenance">Maintenance</option>
                      <option value="Reserved">Reserved</option>
                    </select>
                  </div>
                )}

                {/* Maintenance Tab */}
                {activeTab === 'maintenance' && editingId && (
                  <div>
                    <div style={{ display: 'grid', gap: 10, marginBottom: 20 }}>
                      {maintenanceLogs.map(log => (
                        <div key={log.id} style={{ backgroundColor: '#111827', padding: 12, borderRadius: 10, border: '1px solid #1f2937' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <strong style={{ color: log.status === 'resolved' ? '#86efac' : '#fca5a5' }}>{log.issue_title}</strong>
                            <span style={{ fontSize: 10, color: '#64748b' }}>{new Date(log.reported_at).toLocaleDateString()}</span>
                          </div>
                          <p style={{ margin: 0, fontSize: 12, color: '#cbd5e1' }}>{log.notes}</p>
                          {log.status !== 'resolved' && (
                            <button type="button" onClick={() => handleResolveMaintenance(log.id)} style={{ ...saveBtn, marginTop: 10, padding: 6, fontSize: 11, backgroundColor: '#22c55e', color: '#fff' }}>
                              Mark Resolved
                            </button>
                          )}
                        </div>
                      ))}
                      {!maintenanceLogs.length && <p style={{ color: '#64748b', fontSize: 13 }}>No maintenance logs.</p>}
                    </div>
                    <div style={{ borderTop: '1px solid #1e293b', paddingTop: 16 }}>
                      <p style={sectionLabel}>Report New Issue</p>
                      <input style={styledInput} required placeholder="Issue Title" value={newLog.issue_title} onChange={e => setNewLog({...newLog, issue_title: e.target.value})} />
                      <textarea style={{...styledInput, minHeight: 60}} placeholder="Notes" value={newLog.notes} onChange={e => setNewLog({...newLog, notes: e.target.value})} />
                      <button type="button" onClick={handleAddMaintenanceLog} style={{ ...saveBtn, backgroundColor: '#fca5a5', marginTop: 10 }} disabled={!newLog.issue_title}>
                        <Wrench size={16}/> Report Issue
                      </button>
                    </div>
                  </div>
                )}

                {/* History Tab */}
                {activeTab === 'history' && editingId && (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead><tr style={theadTr}>
                      <th style={{padding: 8, textAlign: 'left'}}>Date</th>
                      <th style={{padding: 8, textAlign: 'left'}}>Event</th>
                      <th style={{padding: 8, textAlign: 'left'}}>Guest</th>
                      <th style={{padding: 8, textAlign: 'right'}}>Revenue</th>
                    </tr></thead>
                    <tbody>
                      {roomHistory.map(h => (
                        <tr key={h.id} style={trStyle}>
                          <td style={{padding: 8}}>{new Date(h.created_at).toLocaleDateString()}</td>
                          <td style={{padding: 8}}>{h.event_type}</td>
                          <td style={{padding: 8}}>{h.guest_name || '—'}</td>
                          <td style={{padding: 8, textAlign: 'right', color: '#bef264'}}>ETB {h.revenue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {!['maintenance', 'history'].includes(activeTab) && (
                  <button type="submit" disabled={loading} style={saveBtn}>{loading ? 'Processing...' : 'Save Room'}</button>
                )}
              </form>
            </motion.div>
          </div>
        )}

        {/* RESERVATION MODAL */}
        {isReservationModalOpen && selectedRoom && (
          <div style={modalOverlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={reservationModalContent}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px' }}>
                <div>
                  <p style={heroEyebrow}>Reception Reserve Now</p>
                  <h3 style={{ margin: '6px 0 0' }}>{selectedRoom.name}</h3>
                </div>
                <X style={{ cursor: 'pointer' }} onClick={() => setIsReservationModalOpen(false)} />
              </div>

              <div style={reservationFormGrid}>
                <input style={styledInput} placeholder="Guest full name" value={reservationDraft[selectedRoom.id]?.guest_name || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [selectedRoom.id]: { ...prev[selectedRoom.id], guest_name: e.target.value } }))} />
                <input style={styledInput} placeholder="Phone number" value={reservationDraft[selectedRoom.id]?.guest_phone || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [selectedRoom.id]: { ...prev[selectedRoom.id], guest_phone: e.target.value } }))} />
                <input type="date" style={styledInput} value={reservationDraft[selectedRoom.id]?.check_in_date || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [selectedRoom.id]: { ...prev[selectedRoom.id], check_in_date: e.target.value } }))} />
                <input type="date" style={styledInput} value={reservationDraft[selectedRoom.id]?.check_out_date || ''} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [selectedRoom.id]: { ...prev[selectedRoom.id], check_out_date: e.target.value } }))} />
                <label style={{...checkboxField, gridColumn: 'span 2'}}>
                  <input type="checkbox" checked={Boolean(reservationDraft[selectedRoom.id]?.pay_now)} onChange={(e) => setReservationDraft((prev) => ({ ...prev, [selectedRoom.id]: { ...prev[selectedRoom.id], pay_now: e.target.checked } }))} />
                  Pay now with Chapa
                </label>
              </div>

              <button type="button" style={saveBtn} onClick={() => handleReserveNow(selectedRoom)} disabled={actionLoading[selectedRoom.id] === 'reserve'}>
                {actionLoading[selectedRoom.id] === 'reserve' ? 'Processing...' : 'Confirm Reservation'}
              </button>
            </motion.div>
          </div>
        )}

        {/* DIGITAL CHECK-IN MODAL */}
        {isDigitalCheckInOpen && selectedRoom && (
          <div style={modalOverlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={reservationModalContent}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px' }}>
                <div>
                  <p style={heroEyebrow}>Digital Registration Card</p>
                  <h3 style={{ margin: '6px 0 0' }}>{selectedRoom.name}</h3>
                </div>
                <X style={{ cursor: 'pointer' }} onClick={() => setIsDigitalCheckInOpen(false)} />
              </div>
              <form onSubmit={handleDigitalCheckIn} style={reservationFormGrid}>
                <input style={{...styledInput, gridColumn: 'span 2'}} required placeholder="Full Name *" value={digitalRegForm.full_name} onChange={e => setDigitalRegForm({...digitalRegForm, full_name: e.target.value})} />
                <input style={styledInput} placeholder="Phone" value={digitalRegForm.phone} onChange={e => setDigitalRegForm({...digitalRegForm, phone: e.target.value})} />
                <input style={styledInput} placeholder="Nationality" value={digitalRegForm.nationality} onChange={e => setDigitalRegForm({...digitalRegForm, nationality: e.target.value})} />
                <select style={styledInput} value={digitalRegForm.id_type} onChange={e => setDigitalRegForm({...digitalRegForm, id_type: e.target.value})}>
                  <option value="national_id">National ID</option>
                  <option value="passport">Passport</option>
                  <option value="driving_license">Driving License</option>
                </select>
                <input style={styledInput} placeholder="ID Number" required value={digitalRegForm.id_number} onChange={e => setDigitalRegForm({...digitalRegForm, id_number: e.target.value})} />
                <button type="submit" disabled={actionLoading[selectedRoom.id] === 'checkin'} style={{...saveBtn, gridColumn: 'span 2'}}>
                  {actionLoading[selectedRoom.id] === 'checkin' ? 'Checking in...' : 'Register & Check-In'}
                </button>
              </form>
            </motion.div>
          </div>
        )}

        {/* FOLIO MODAL */}
        {isFolioOpen && activeReservationForFolio && (
          <div style={modalOverlay}>
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={{ ...modalContent, width: 'min(600px, 100%)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', marginBottom: 20 }}>
                <div>
                  <h3 style={{ margin: 0 }}>Guest Folio</h3>
                  <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '13px' }}>{activeReservationForFolio.guest_name} — {selectedRoom.name}</p>
                </div>
                <X style={{ cursor: 'pointer' }} onClick={() => setIsFolioOpen(false)} />
              </div>

              <div style={{ maxHeight: '50vh', overflowY: 'auto', marginBottom: 20 }}>
                {folioCharges.map(charge => (
                  <div key={charge.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', borderBottom: '1px solid #1e293b' }}>
                    <div>
                      <strong style={{ display: 'block', fontSize: 13 }}>{charge.description}</strong>
                      <small style={{ color: '#64748b', fontSize: 10 }}>{new Date(charge.added_at).toLocaleString()}</small>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontWeight: 700, color: '#fcd34d' }}>ETB {charge.amount}</span>
                      <Trash2 size={14} color="#ef4444" style={{ cursor: 'pointer' }} onClick={() => handleDeleteFolioCharge(charge.id)} />
                    </div>
                  </div>
                ))}
                {!folioCharges.length && <p style={{ color: '#64748b', fontSize: 13, textAlign: 'center', padding: 20 }}>No extra charges yet.</p>}
              </div>

              <form onSubmit={handleAddFolioCharge} style={{ display: 'flex', gap: 10, borderTop: '1px solid #1e293b', paddingTop: 16 }}>
                <input style={{ ...styledInput, marginTop: 0, flex: 2 }} required placeholder="Charge Description (e.g. Laundry)" value={newCharge.description} onChange={e => setNewCharge({...newCharge, description: e.target.value})} />
                <input style={{ ...styledInput, marginTop: 0, flex: 1 }} type="number" required placeholder="Amount" value={newCharge.amount} onChange={e => setNewCharge({...newCharge, amount: e.target.value})} />
                <button type="submit" style={{ ...saveBtn, marginTop: 0, width: 'auto', padding: '0 20px' }}>Add</button>
              </form>
            </motion.div>
          </div>
        )}

        {/* FINAL BILL MODAL */}
        {isFinalBillOpen && finalBillData && (
          <div style={modalOverlay} className="print-modal-overlay print-allow">
            <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} style={{ ...modalContent, width: 'min(600px, 100%)' }} className="print-modal-content">
              <div ref={printRef} id="print-bill" className={`thermal-receipt print-paper-${finalBillData?.printer_paper_size || '80mm'}`}>
                <div className="centered">
                  <h2 style={{ margin: 0, fontSize: '18px' }}>{finalBillData.hotel_name}</h2>
                  <p style={{ margin: '4px 0 0', fontSize: 10 }}>{finalBillData.hotel_address}</p>
                  <p style={{ margin: '2px 0 0', fontSize: 10 }}>TEL: {finalBillData.hotel_phone}</p>
                  <p style={{ margin: '2px 0 0', fontSize: 10 }}>TIN: {finalBillData.tin_number}</p>
                  <div className="dashed-divider" />
                  <h3 style={{ margin: '5px 0', fontSize: '14px' }}>FINAL GUEST BILL</h3>
                  <div className="dashed-divider" />
                </div>
                
                <div style={{ fontSize: 10, marginBottom: 15 }}>
                  <div className="item-row"><span>GUEST:</span><span>{finalBillData.guest_name}</span></div>
                  <div className="item-row"><span>CONF#:</span><span>{finalBillData.confirmation_code}</span></div>
                  <div className="item-row"><span>ROOM:</span><span>{finalBillData.room_name} (#{finalBillData.room_number})</span></div>
                  <div className="item-row"><span>NIGHTS:</span><span>{finalBillData.nights}</span></div>
                  <div className="item-row"><span>IN:</span><span>{finalBillData.check_in_date}</span></div>
                  <div className="item-row"><span>OUT:</span><span>{finalBillData.check_out_date}</span></div>
                </div>

                <div className="dashed-divider" />
                <table style={{ width: '100%', fontSize: 10 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>DESCRIPTION</th>
                      <th style={{ textAlign: 'right' }}>AMOUNT</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ padding: '2px 0' }}>ROOM ACC ({finalBillData.nights} NTS)</td>
                      <td style={{ textAlign: 'right', padding: '2px 0' }}>{finalBillData.room_total.toFixed(2)}</td>
                    </tr>
                    {finalBillData.folio_charges.map(c => (
                      <tr key={c.id}>
                        <td style={{ padding: '2px 0' }}>{c.description}</td>
                        <td style={{ textAlign: 'right', padding: '2px 0' }}>{Number(c.amount).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="dashed-divider" />
                <div className="item-row bold" style={{ fontSize: '14px' }}>
                  <span>GRAND TOTAL</span>
                  <span>ETB {finalBillData.grand_total.toFixed(2)}</span>
                </div>
                <div className="dashed-divider" />

                <div className="centered" style={{ fontSize: 10, marginTop: 20 }}>
                  <p>THANK YOU FOR STAYING WITH US!</p>
                  <p>*** SMART HOTEL ERP ***</p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }} className="no-print">
                <div style={{ display: 'flex', gap: 10 }}>
                  <button type="button" onClick={() => setIsFinalBillOpen(false)} style={{ ...saveBtn, marginTop: 0, backgroundColor: 'transparent', color: '#fff', border: '1px solid #334155' }}>Cancel</button>
                  <button type="button" disabled={actionLoading.checkout_btn} onClick={handleEnhancedCheckout} style={{ ...saveBtn, marginTop: 0, backgroundColor: '#f59e0b', color: '#111827' }}>
                    {actionLoading.checkout_btn ? 'Processing...' : 'Confirm Check-Out & Print'}
                  </button>
                </div>
                <div style={{ padding: '8px 12px', backgroundColor: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8 }}>
                  <p style={{ margin: 0, fontSize: '11px', color: '#fcd34d', lineHeight: 1.4 }}>
                    💡 <strong>TIP:</strong> For the best result, set <strong>Scale: 100%</strong> and <strong>Margins: None</strong> in the print dialog.
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {/* QR SCAN SUCCESS MODAL */}
        {scanSuccessData && (
          <div style={modalOverlay}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} style={{...reservationModalContent, width: 'min(400px, 100%)', textAlign: 'center'}}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div style={badgeStyle}><CheckCircle size={16} /> Check-In Successful</div>
                <X style={{ cursor: 'pointer' }} onClick={() => setScanSuccessData(null)} />
              </div>
              <div style={{ textAlign: 'center', padding: '10px 0' }}>
                <div style={guestIconLarge}><User size={32} color="#fff" /></div>
                <h2 style={{ margin: '14px 0 6px' }}>{scanSuccessData.guest_name}</h2>
                <span style={heroPill}>STATUS: CHECKED IN</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', textAlign: 'left' }}>
                <div style={miniDetailBox}>
                  <small style={detailSmallLabel}>ROOM</small>
                  <strong>{scanSuccessData.room_name} ({scanSuccessData.room_number})</strong>
                </div>
                <div style={miniDetailBox}>
                  <small style={detailSmallLabel}>DATES</small>
                  <strong>{scanSuccessData.check_in_date} - {scanSuccessData.check_out_date}</strong>
                </div>
                <div style={miniDetailBox}>
                  <small style={detailSmallLabel}>PAYMENT</small>
                  <strong>ETB {scanSuccessData.total_amount}</strong>
                </div>
                <div style={miniDetailBox}>
                  <small style={detailSmallLabel}>CONFIRMATION</small>
                  <strong>{scanSuccessData.confirmation_code}</strong>
                </div>
              </div>
              <button type="button" style={saveBtn} onClick={() => setScanSuccessData(null)}>
                Close & Continue
              </button>
            </motion.div>
          </div>
        )}

      </AnimatePresence>
    </div>
  );
};

// --- Styles ---
const roomStatusPill = (status, reservedOnline) => ({
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  padding: '5px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: 700,
  backgroundColor: reservedOnline ? 'rgba(59,130,246,0.18)' : status === 'Maintenance' ? 'rgba(100,116,139,0.18)' : 'rgba(190,242,100,0.12)',
  color: reservedOnline ? '#93c5fd' : status === 'Maintenance' ? '#cbd5e1' : (status === 'Occupied' ? '#fca5a5' : '#bef264'),
  border: reservedOnline ? '1px solid rgba(96,165,250,0.45)' : '1px solid rgba(190,242,100,0.18)',
});

const reservationStatusPill = (status) => ({
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  padding: '5px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: 700,
  backgroundColor: status === 'confirmed' ? 'rgba(37,99,235,0.18)' : status === 'checked_in' ? 'rgba(22,163,74,0.18)' : 'rgba(245,158,11,0.16)',
  color: status === 'confirmed' ? '#93c5fd' : status === 'checked_in' ? '#86efac' : '#fcd34d',
});

const heroCard = { background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.95) 50%, rgba(14,116,144,0.85) 100%)', border: '1px solid rgba(56,189,248,0.18)', borderRadius: '24px', padding: '24px', marginBottom: '22px', display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '20px' };
const heroEyebrow = { margin: 0, color: '#7dd3fc', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700 };
const heroTitle = { margin: '8px 0', fontSize: '28px' };
const heroSubtitle = { margin: 0, color: '#cbd5e1', maxWidth: '760px', lineHeight: 1.6 };
const heroBadges = { display: 'flex', flexWrap: 'wrap', gap: '10px', alignContent: 'start', justifyContent: 'flex-end' };
const heroPill = { display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: '999px', backgroundColor: 'rgba(15,23,42,0.45)', border: '1px solid rgba(125,211,252,0.22)', color: '#e0f2fe', fontSize: '12px', fontWeight: 600 };
const statsGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '15px', marginBottom: '25px' };
const statCard = { backgroundColor: '#fff', padding: '15px', borderRadius: '15px', display: 'flex', alignItems: 'center', gap: '12px' };
const iconBox = { width: '40px', height: '40px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const statLabel = { margin: 0, fontSize: '10px', fontWeight: 'bold', color: '#94a3b8' };
const statCount = { margin: 0, fontSize: '20px', color: '#0f172a' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', marginBottom: '18px', gap: '12px', flexWrap: 'wrap' };
const switcherContainer = { display: 'flex', backgroundColor: '#fff', padding: '4px', borderRadius: '30px', border: '1px solid #e2e8f0' };
const switchBtn = { border: 'none', padding: '8px 18px', borderRadius: '25px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '600' };
const addNewBtn = { backgroundColor: '#3f5d45', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: '30px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' };
const opsGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '24px' };
const opsCard = { backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '18px', padding: '18px' };
const opsTitleRow = { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' };
const opsText = { margin: 0, color: '#94a3b8', fontSize: '13px', lineHeight: 1.6 };
const roomsGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' };
const roomCard = { backgroundColor: '#0f172a', borderRadius: '16px', border: '1px solid #1e293b', overflow: 'hidden' };
const reservedRoomCard = { border: '1px solid rgba(96,165,250,0.9)', boxShadow: '0 0 0 1px rgba(59,130,246,0.15), 0 12px 30px rgba(37,99,235,0.18)' };
const cardImgWrapper = { height: '150px', position: 'relative', backgroundColor: '#1e293b' };
const imgStyle = { width: '100%', height: '100%', objectFit: 'cover' };
const noImg = { height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4b5563' };
const priceTagSmall = { position: 'absolute', top: '10px', left: '10px', backgroundColor: 'rgba(0,0,0,0.7)', color: '#bef264', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 'bold' };
const reservedBadge = { position: 'absolute', top: '10px', right: '10px', backgroundColor: '#2563eb', color: '#fff', padding: '4px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: 700 };
const bookingPanel = { display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px', marginTop: '14px' };
const miniInput = { backgroundColor: '#111827', border: '1px solid #334155', color: '#fff', padding: '10px', borderRadius: '10px', width: '100%', boxSizing: 'border-box' };
const frontDeskActions = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '10px' };
const actionBtn = { border: 'none', padding: '10px 12px', borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '12px' };
const reserveBtn = { backgroundColor: '#2563eb', color: '#fff' };
const checkInBtn = { backgroundColor: '#16a34a', color: '#fff' };
const checkOutBtn = { backgroundColor: '#f59e0b', color: '#111827' };
const cardActionsSmall = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #1e293b' };
const listContainer = { backgroundColor: '#0f172a', borderRadius: '15px', border: '1px solid #1e293b', overflow: 'hidden' };
const tableStyle = { width: '100%', borderCollapse: 'collapse', textAlign: 'left' };
const theadTr = { borderBottom: '1px solid #1e293b', backgroundColor: '#1e293b66' };
const thStyle = { padding: '15px', fontSize: '13px', color: '#94a3b8' };
const trStyle = { borderBottom: '1px solid #1e293b' };
const listReservedRow = { backgroundColor: 'rgba(37,99,235,0.08)' };
const tdStyle = { padding: '12px 15px', fontSize: '14px' };
const modalOverlay = { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '20px' };
const modalContent = { backgroundColor: '#0f172a', padding: '25px', borderRadius: '24px', width: 'min(1100px, 100%)', border: '1px solid #334155', maxHeight: '92vh', overflow: 'hidden' };
const reservationModalContent = { backgroundColor: '#0f172a', padding: '25px', borderRadius: '24px', width: 'min(760px, 100%)', border: '1px solid #334155', maxHeight: '92vh', overflowY: 'auto', display: 'grid', gap: '18px' };
const reservationFormGrid = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' };
const auditBoard = { display: 'grid', gap: '18px' };
const auditCard = { backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '20px', padding: '20px' };
const auditStatsGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginTop: '18px' };
const auditMiniCard = { backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '16px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px', color: '#cbd5e1' };
const tabsWrapperSmall = { display: 'flex', gap: '10px', overflowX: 'auto', marginBottom: '20px', paddingBottom: '8px', borderBottom: '1px solid #1e293b' };
const tabBtnStyleSmall = { background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '11px', fontWeight: '600', whiteSpace: 'nowrap' };
const activeTabStyleSmall = { ...tabBtnStyleSmall, color: '#bef264', borderBottom: '2px solid #bef264' };
const styledInput = { backgroundColor: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '12px', borderRadius: '10px', width: '100%', boxSizing: 'border-box', marginTop: '5px' };
const grid2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' };
const saveBtn = { width: '100%', backgroundColor: '#bef264', color: '#000', border: 'none', padding: '14px', borderRadius: '12px', fontWeight: 'bold', marginTop: '20px', cursor: 'pointer' };
const amenitiesGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' };
const checkboxLabel = { display: 'flex', gap: '8px', fontSize: '13px', color: '#94a3b8', alignItems: 'center' };
const checkboxField = { ...checkboxLabel, backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '12px' };
const sectionLabel = { margin: '0 0 10px', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: '#7dd3fc', letterSpacing: '0.08em' };
const uploadZone = { border: '2px dashed #334155', padding: '15px', textAlign: 'center', borderRadius: '12px' };
const reservationRow = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '14px', padding: '12px' };
const reservationMeta = { margin: '4px 0 0', color: '#94a3b8', fontSize: '12px' };
const badgeStyle = { display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#10b981', fontSize: '12px', fontWeight: 'bold', backgroundColor: 'rgba(16,185,129,0.1)', padding: '6px 12px', borderRadius: '20px' };
const guestIconLarge = { width: '64px', height: '64px', backgroundColor: '#38bdf8', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto' };
const miniDetailBox = { backgroundColor: '#111827', padding: '15px', borderRadius: '15px', border: '1px solid #1f2937', color: '#fff' };
const detailSmallLabel = { display: 'block', fontSize: '9px', fontWeight: '800', color: '#64748b', marginBottom: '4px', textTransform: 'uppercase' };

export default RoomManager;
