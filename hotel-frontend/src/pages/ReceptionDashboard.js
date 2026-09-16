import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  QrCode, Search, User, Calendar, Bed, CheckCircle, 
  ArrowRight, X, Phone, Clock,
  AlertCircle, ShieldAlert, Check, RefreshCcw, LayoutGrid, 
  ListOrdered, Plus, Filter, Trash2, ShieldCheck, 
  UserCheck, LogOut, TrendingUp, Building2, Banknote, Loader2,
  Eye, Wifi, Wind, Tv, Coffee, Dumbbell, Car, Star
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';
import ReportsCenter from './ReportsCenter';

const ROOMS_API = `${API_BASE_URL}/users/rooms/`;
const RESERVATIONS_API = `${API_BASE_URL}/users/reservations/`;

const ReceptionDashboard = ({ userData, handleLogout }) => {
  const [rooms, setRooms] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [activeTab, setActiveTab] = useState('grid'); // 'grid', 'reservations', 'checkin'
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState({ text: '', type: '' }); // type: 'success' | 'error'
  
  // Selection / Modal States
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [bookingRoom, setBookingRoom] = useState(null);
  const [checkinCode, setCheckinCode] = useState('');
  const [verifiedReservation, setVerifiedReservation] = useState(null);
  
  // Folio States
  const [activeReservation, setActiveReservation] = useState(null);
  const [folioCharges, setFolioCharges] = useState([]);
  const [folioLoading, setFolioLoading] = useState(false);
  const [newCharge, setNewCharge] = useState({ description: '', amount: '' });

  // Checkout Modal States
  const [showCheckoutModal, setShowCheckoutModal] = useState(false);
  const [checkoutReservation, setCheckoutReservation] = useState(null);
  const [checkoutRoom, setCheckoutRoom] = useState(null);
  const [checkoutFolio, setCheckoutFolio] = useState([]);
  const [checkoutPaymentMethod, setCheckoutPaymentMethod] = useState('Cash'); // 'Cash' | 'Digital Payment' | 'Bank Transfer'
  const [bankTransferRef, setBankTransferRef] = useState('');
  const [chapaSession, setChapaSession] = useState(null); // { checkout_url, tx_ref, grand_total }
  const [verifyingPayment, setVerifyingPayment] = useState(false);
  const [checkoutSuccess, setCheckoutSuccess] = useState(null); // null | { message, grand_total, method }

  // ── Check-In Payment Modal States ──────────────────────────────────────────
  const [showCheckinPayModal, setShowCheckinPayModal] = useState(false);
  const [checkinPayRoom, setCheckinPayRoom] = useState(null);        // room object
  const [checkinPayReservation, setCheckinPayReservation] = useState(null); // reservation object (may be null for walk-in before creation)
  const [pendingCheckinRoomId, setPendingCheckinRoomId] = useState(null);
  const [pendingCheckinResId, setPendingCheckinResId] = useState(null);
  const [checkinPayMethod, setCheckinPayMethod] = useState('Cash');
  const [checkinBankRef, setCheckinBankRef] = useState('');
  const [checkinChapaSession, setCheckinChapaSession] = useState(null);
  const [verifyingCheckinPay, setVerifyingCheckinPay] = useState(false);
  const [checkinSuccess, setCheckinSuccess] = useState(null); // { method, reference, guest_name, room_number }

  // Room Detail Preview Modal
  const [showRoomDetailModal, setShowRoomDetailModal] = useState(false);
  const [detailRoom, setDetailRoom] = useState(null);
  const [detailImageIndex, setDetailImageIndex] = useState(0);

  // Filters
  const [roomTypeFilter, setRoomTypeFilter] = useState('All');
  const [roomStatusFilter, setRoomStatusFilter] = useState('All');

  // Booking Form State
  const [bookingForm, setBookingForm] = useState({
    guest_name: '',
    guest_email: '',
    guest_phone: '',
    check_in_date: new Date().toISOString().split('T')[0],
    check_out_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
    adults: 1,
    children: 0,
    notes: '',
    check_in_now: true,
    payment_method: 'Cash',
    payment_reference: '',
  });

  // Fetch initial data
  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      const [roomsRes, resRes] = await Promise.all([
        axios.get(ROOMS_API, config),
        axios.get(RESERVATIONS_API, config)
      ]);

      setRooms(Array.isArray(roomsRes.data) ? roomsRes.data : []);
      setReservations(Array.isArray(resRes.data) ? resRes.data : []);
    } catch (err) {
      console.error("Error loading dashboard data:", err);
      showNotification("Failed to retrieve dashboard data. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAutoVerifyRedirectPayment = async (resId, roomNo) => {
    showNotification(`Verifying digital payment for Room ${roomNo}...`, 'success');
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${resId}/verify-checkout-payment/`,
        {},
        config
      );
      
      if (res.data?.status === 'success') {
        const [roomsRes, resRes] = await Promise.all([
          axios.get(ROOMS_API, config),
          axios.get(RESERVATIONS_API, config)
        ]);
        
        const allRooms = Array.isArray(roomsRes.data) ? roomsRes.data : [];
        const allReservations = Array.isArray(resRes.data) ? resRes.data : [];
        setRooms(allRooms);
        setReservations(allReservations);

        const reservation = allReservations.find(r => Number(r.id) === Number(resId));
        const room = allRooms.find(r => reservation && Number(r.id) === Number(reservation.room));

        // Detect whether this was a check-in or checkout payment by tx_ref prefix
        const txRef = reservation?.chapa_tx_ref || '';
        const isCheckin = txRef.startsWith('checkin-');

        if (isCheckin) {
          // Show check-in success modal
          setCheckinPayRoom(room || null);
          setCheckinPayReservation(reservation || null);
          setCheckinChapaSession(null);
          setCheckinSuccess({
            method: 'Digital Payment',
            reference: txRef,
            guest_name: reservation?.guest_name || 'Guest',
            room_number: room?.room_number || roomNo,
          });
          setShowCheckinPayModal(true);
        } else {
          // Checkout flow
          if (reservation && room) {
            setCheckoutRoom(room);
            setCheckoutReservation(reservation);
            try {
              const folioRes = await axios.get(`${API_BASE_URL}/users/reservations/${resId}/folio/`, config);
              setCheckoutFolio(Array.isArray(folioRes.data) ? folioRes.data : []);
            } catch {
              setCheckoutFolio([]);
            }
            setCheckoutSuccess({
              message: 'Digital payment verified!',
              grand_total: res.data.grand_total,
              method: 'Digital Payment',
              reference: txRef,
            });
            setShowCheckoutModal(true);
          } else {
            showNotification(`Payment verified! Room ${roomNo} checkout completed.`, 'success');
          }
        }
      } else {
        showNotification(`Digital payment for Room ${roomNo} is still pending.`, 'error');
      }
    } catch (err) {
      console.error(err);
      showNotification(`Failed to verify payment for Room ${roomNo}.`, 'error');
      fetchData();
    }
  };

  useEffect(() => {
    fetchData();
    
    // Check if redirected back from Chapa checkout payment
    const params = new URLSearchParams(window.location.search);
    if (params.get('payment') === 'returned') {
      const resId = params.get('res_id');
      const roomNo = params.get('room_no');
      if (resId && roomNo) {
        handleAutoVerifyRedirectPayment(resId, roomNo);
      }
      // Clean up the URL query parameters so they don't persist on page reloads
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Refresh stats and data every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Automatic Polling for Checkout Digital Payment completion
  useEffect(() => {
    let intervalId = null;
    
    if (showCheckoutModal && chapaSession && !checkoutSuccess && !verifyingPayment) {
      intervalId = setInterval(async () => {
        try {
          const token = localStorage.getItem('access_token');
          const res = await axios.post(
            `${API_BASE_URL}/users/reservations/${checkoutReservation.id}/verify-checkout-payment/`,
            { tx_ref: chapaSession.tx_ref },
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (res.data?.status === 'success') {
            setCheckoutSuccess({
              message: 'Digital payment verified!',
              grand_total: res.data.grand_total,
              method: 'Digital Payment',
              reference: chapaSession.tx_ref,
            });
            fetchData();
          }
        } catch (err) {
          console.log("Polling checkout verification status...", err);
        }
      }, 4000);
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCheckoutModal, chapaSession, checkoutSuccess, checkoutReservation]);

  // Automatic Polling for Check-In Digital Payment completion
  useEffect(() => {
    let intervalId = null;

    if (showCheckinPayModal && checkinChapaSession && !checkinSuccess && !verifyingCheckinPay) {
      intervalId = setInterval(async () => {
        try {
          const token = localStorage.getItem('access_token');
          const res = await axios.post(
            `${API_BASE_URL}/users/reservations/${pendingCheckinResId}/verify-checkout-payment/`,
            { tx_ref: checkinChapaSession.tx_ref },
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (res.data?.status === 'success') {
            const reservation = checkinPayReservation;
            setCheckinSuccess({
              method: 'Digital Payment',
              reference: checkinChapaSession.tx_ref,
              guest_name: reservation?.guest_name || 'Guest',
              room_number: checkinPayRoom?.room_number || '',
            });
            setVerifiedReservation(null);
            setCheckinCode('');
            fetchData();
          }
        } catch (err) {
          console.log("Polling check-in verification status...", err);
        }
      }, 4000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCheckinPayModal, checkinChapaSession, checkinSuccess, pendingCheckinResId]);

  // Folio Charges Fetching & Management
  useEffect(() => {
    if (selectedRoom && selectedRoom.status === 'Occupied') {
      const activeRes = reservations.find(r => Number(r.room) === Number(selectedRoom.id) && r.status === 'checked_in');
      if (activeRes) {
        setActiveReservation(activeRes);
        fetchFolioDetails(activeRes.id);
      } else {
        setActiveReservation(null);
        setFolioCharges([]);
      }
    } else {
      setActiveReservation(null);
      setFolioCharges([]);
    }
  }, [selectedRoom, reservations]);

  const fetchFolioDetails = async (reservationId) => {
    setFolioLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      const res = await axios.get(`${API_BASE_URL}/users/reservations/${reservationId}/folio/`, config);
      setFolioCharges(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error("Error loading folio charges:", err);
    } finally {
      setFolioLoading(false);
    }
  };

  const handleAddFolioCharge = async (e) => {
    e.preventDefault();
    if (!activeReservation || !newCharge.description || !newCharge.amount) return;

    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      await axios.post(`${API_BASE_URL}/users/reservations/${activeReservation.id}/folio/`, {
        description: newCharge.description,
        amount: Number(newCharge.amount)
      }, config);

      setNewCharge({ description: '', amount: '' });
      showNotification("Extra charge registered successfully.");
      fetchFolioDetails(activeReservation.id);
    } catch (err) {
      console.error(err);
      showNotification("Failed to add charge.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteFolioCharge = async (chargeId) => {
    if (!window.confirm("Remove this charge from the folio?")) return;
    
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      await axios.delete(`${API_BASE_URL}/users/folio/${chargeId}/`, config);
      showNotification("Charge removed.");
      if (activeReservation) {
        fetchFolioDetails(activeReservation.id);
      }
    } catch (err) {
      console.error(err);
      showNotification("Failed to remove charge.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const folioTotal = useMemo(() => {
    const extras = folioCharges.reduce((sum, c) => sum + Number(c.amount || 0), 0);
    if (!activeReservation || !selectedRoom) return { roomCost: 0, nights: 1, extras, grandTotal: extras };
    
    // Calculate nights
    const inDate = new Date(activeReservation.check_in_date);
    const outDate = new Date(activeReservation.check_out_date);
    const nights = Math.max(Math.round((outDate - inDate) / (1000 * 60 * 60 * 24)), 1);
    const roomCost = Number(selectedRoom.base_price || 0) * nights;
    
    return { roomCost, nights, extras, grandTotal: roomCost + extras };
  }, [folioCharges, activeReservation, selectedRoom]);

  const showNotification = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: '', type: '' }), 5000);
  };

  // Group rooms by Floor
  const groupedRooms = useMemo(() => {
    const filtered = rooms.filter(room => {
      const typeMatch = roomTypeFilter === 'All' || room.room_type === roomTypeFilter;
      const statusMatch = roomStatusFilter === 'All' || room.status === roomStatusFilter;
      return typeMatch && statusMatch;
    });

    const groups = {};
    filtered.forEach(room => {
      const floor = room.floor_number || 1;
      if (!groups[floor]) groups[floor] = [];
      groups[floor].push(room);
    });

    // Sort floors keys and rooms by number
    const sortedGroups = {};
    Object.keys(groups).sort().forEach(floor => {
      sortedGroups[floor] = groups[floor].sort((a, b) => a.room_number.localeCompare(b.room_number));
    });
    return sortedGroups;
  }, [rooms, roomTypeFilter, roomStatusFilter]);

  // Extract unique room types
  const roomTypes = useMemo(() => {
    const types = new Set(rooms.map(r => r.room_type));
    return ['All', ...Array.from(types)];
  }, [rooms]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = rooms.length;
    const occupied = rooms.filter(r => r.status === 'Occupied').length;
    const available = rooms.filter(r => r.status === 'Available').length;
    const cleaning = rooms.filter(r => r.status === 'Cleaning').length;
    const maintenance = rooms.filter(r => r.status === 'Maintenance').length;
    const reserved = rooms.filter(r => r.status === 'Reserved').length;
    
    // Today's arrivals / departures
    const todayStr = new Date().toISOString().split('T')[0];
    const arrivals = reservations.filter(r => r.check_in_date === todayStr && r.status === 'confirmed').length;
    const departures = reservations.filter(r => r.check_out_date === todayStr && r.status === 'checked_in').length;

    return { total, occupied, available, cleaning, maintenance, reserved, arrivals, departures };
  }, [rooms, reservations]);

  // Change room status manually
  const handleUpdateRoomStatus = async (roomId, newStatus) => {
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      await axios.patch(`${ROOMS_API}${roomId}/`, {
        status: newStatus
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showNotification(`Room status updated to ${newStatus} successfully.`);
      setSelectedRoom(null);
      fetchData();
    } catch (err) {
      console.error(err);
      showNotification("Failed to update room status.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // Perform check-in by code/token search
  const handleVerifyCheckInCode = async (e) => {
    if (e) e.preventDefault();
    if (!checkinCode) return;

    setSubmitting(true);
    setVerifiedReservation(null);
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.post(`${API_BASE_URL}/users/reservations/qr-checkin/`, {
        qr_token: checkinCode
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setVerifiedReservation(res.data.reservation);
      showNotification("Reservation verified! Details loaded.");
    } catch (err) {
      console.error(err);
      showNotification(err.response?.data?.error || "Invalid code or reservation not found.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // Open check-in payment modal — called from QR tab, drawer, or reservations list
  const handleCheckInVerified = (roomId, reservationId) => {
    const res = reservations.find(r => Number(r.id) === Number(reservationId));
    const room = rooms.find(r => Number(r.id) === Number(roomId));
    setPendingCheckinRoomId(roomId);
    setPendingCheckinResId(reservationId);
    setCheckinPayRoom(room || null);
    setCheckinPayReservation(res || null);
    setCheckinPayMethod('Cash');
    setCheckinBankRef('');
    setCheckinChapaSession(null);
    setCheckinSuccess(null);
    setShowCheckinPayModal(true);
  };

  // Confirm check-in with Cash or Bank Transfer
  const handleConfirmCheckinPayment = async (method, reference = '') => {
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      await axios.patch(`${API_BASE_URL}/users/rooms/${pendingCheckinRoomId}/front-desk-status/`, {
        action: 'checkin',
        reservation_id: pendingCheckinResId,
        payment_method: method,
        payment_reference: reference,
      }, { headers: { Authorization: `Bearer ${token}` } });

      const res = checkinPayReservation;
      setCheckinSuccess({
        method,
        reference,
        guest_name: res?.guest_name || 'Guest',
        room_number: checkinPayRoom?.room_number || pendingCheckinRoomId,
      });
      setVerifiedReservation(null);
      setCheckinCode('');
      fetchData();
    } catch (err) {
      console.error(err);
      showNotification(err.response?.data?.error || 'Check-in failed.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Initiate Chapa digital payment for check-in
  const handleInitiateCheckinDigitalPayment = async () => {
    if (!pendingCheckinResId) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${pendingCheckinResId}/checkout-payment-session/`,
        { payment_type: 'checkin' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setCheckinChapaSession(res.data);
    } catch (err) {
      showNotification(err.response?.data?.error || 'Failed to create Chapa session.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Verify Chapa digital payment for check-in
  const handleVerifyCheckinDigitalPayment = async () => {
    if (!pendingCheckinResId || !checkinChapaSession) return;
    setVerifyingCheckinPay(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${pendingCheckinResId}/verify-checkout-payment/`,
        { tx_ref: checkinChapaSession.tx_ref },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.data?.status === 'success') {
        const reservation = checkinPayReservation;
        setCheckinSuccess({
          method: 'Digital Payment',
          reference: checkinChapaSession.tx_ref,
          guest_name: reservation?.guest_name || 'Guest',
          room_number: checkinPayRoom?.room_number || '',
        });
        setVerifiedReservation(null);
        setCheckinCode('');
        setSelectedRoom(null); // close room drawer so grid refreshes cleanly
        await fetchData();    // refresh rooms & reservations from server
      } else {
        showNotification('Payment not yet confirmed. Ask guest to complete payment.', 'error');
      }
    } catch (err) {
      showNotification(err.response?.data?.error || 'Verification failed.', 'error');
    } finally {
      setVerifyingCheckinPay(false);
    }
  };

  // Open checkout modal - fetch final folio and prepare
  const handleOpenCheckoutModal = async (room, reservation) => {
    setCheckoutRoom(room);
    setCheckoutReservation(reservation);
    setCheckoutPaymentMethod('Cash');
    setBankTransferRef('');
    setChapaSession(null);
    setCheckoutSuccess(null);
    setSubmitting(true);
    // Fetch latest folio
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.get(`${API_BASE_URL}/users/reservations/${reservation.id}/folio/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const folioList = Array.isArray(res.data) ? res.data : [];
      setCheckoutFolio(folioList);
      
      const extras = folioList.reduce((sum, item) => sum + Number(item.amount || 0), 0);
      if (extras === 0) {
        setSubmitting(false);
        if (window.confirm(`Guest has no extra charges. Proceed with direct check-out for Room ${room.room_number}?`)) {
          setSubmitting(true);
          const payload = {
            payment_method: 'None',
            payment_status: 'paid',
            payment_reference: 'No Extras',
          };
          await axios.post(
            `${API_BASE_URL}/users/reservations/${reservation.id}/enhanced-checkout/`,
            payload,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          showNotification(`Direct check-out completed for Room ${room.room_number}.`);
          fetchData();
        }
      } else {
        setShowCheckoutModal(true);
      }
    } catch (err) {
      console.error(err);
      setCheckoutFolio([]);
      showNotification('Failed to retrieve guest folio.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Cash / Bank Transfer checkout via EnhancedCheckoutView
  const handleCompleteCheckout = async (method, reference = '') => {
    if (!checkoutReservation) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const payload = {
        payment_method: method,
        payment_status: 'paid',
        payment_reference: reference,
      };
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${checkoutReservation.id}/enhanced-checkout/`,
        payload,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const bill = res.data?.final_bill || {};
      setCheckoutSuccess({
        message: `Checkout complete!`,
        grand_total: bill.extras_total || 0,
        method,
        reference,
      });
      fetchData();
    } catch (err) {
      showNotification(err.response?.data?.error || 'Checkout failed.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Initiate Chapa Digital Payment session
  const handleInitiateDigitalPayment = async () => {
    if (!checkoutReservation) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${checkoutReservation.id}/checkout-payment-session/`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setChapaSession(res.data);
    } catch (err) {
      showNotification(err.response?.data?.error || 'Failed to create payment session.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Verify Digital Payment
  const handleVerifyDigitalPayment = async () => {
    if (!checkoutReservation || !chapaSession) return;
    setVerifyingPayment(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await axios.post(
        `${API_BASE_URL}/users/reservations/${checkoutReservation.id}/verify-checkout-payment/`,
        { tx_ref: chapaSession.tx_ref },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.data?.status === 'success') {
        setCheckoutSuccess({
          message: 'Digital payment verified!',
          grand_total: res.data.grand_total,
          method: 'Digital Payment',
          reference: chapaSession.tx_ref,
        });
        fetchData();
      } else {
        showNotification('Payment not yet confirmed. Please ask guest to complete payment.', 'error');
      }
    } catch (err) {
      showNotification(err.response?.data?.error || err.response?.data?.message || 'Verification failed.', 'error');
    } finally {
      setVerifyingPayment(false);
    }
  };

  // Compute checkout bill totals
  const checkoutBill = useMemo(() => {
    if (!checkoutReservation || !checkoutRoom) return { nights: 1, roomCost: 0, extras: 0, grandTotal: 0 };
    const inDate = new Date(checkoutReservation.check_in_date);
    const outDate = new Date(checkoutReservation.check_out_date);
    const nights = Math.max(Math.round((outDate - inDate) / 86400000), 1);
    const roomCost = Number(checkoutRoom.base_price || 0) * nights;
    const extras = checkoutFolio.reduce((s, c) => s + Number(c.amount || 0), 0);
    return { nights, roomCost, extras, grandTotal: roomCost + extras };
  }, [checkoutReservation, checkoutRoom, checkoutFolio]);

  // Submit Walk-in Booking
  const handleCreateWalkInBooking = async (e) => {
    e.preventDefault();
    if (!bookingRoom) return;

    // If check_in_now + Digital Payment → open Chapa flow after creating reservation
    if (bookingForm.check_in_now && bookingForm.payment_method === 'Digital Payment') {
      setSubmitting(true);
      try {
        const token = localStorage.getItem('access_token');
        const config = { headers: { Authorization: `Bearer ${token}` } };
        const res = await axios.post(`${API_BASE_URL}/users/rooms/${bookingRoom.id}/reserve-now/`, {
          guest_name: bookingForm.guest_name,
          guest_email: bookingForm.guest_email,
          guest_phone: bookingForm.guest_phone,
          check_in_date: bookingForm.check_in_date,
          check_out_date: bookingForm.check_out_date,
          adults: bookingForm.adults,
          children: bookingForm.children,
          notes: bookingForm.notes,
          source: 'reception',
          pay_now: 'false',
        }, config);
        const reservation = res.data.reservation;
        setShowBookingModal(false);
        setBookingRoom(null);
        resetBookingForm();
        // Open check-in payment modal on the newly created reservation
        setPendingCheckinRoomId(bookingRoom.id);
        setPendingCheckinResId(reservation.id);
        setCheckinPayRoom(bookingRoom);
        setCheckinPayReservation(reservation);
        setCheckinPayMethod('Digital Payment');
        setCheckinBankRef('');
        setCheckinChapaSession(null);
        setCheckinSuccess(null);
        setShowCheckinPayModal(true);
        fetchData();
      } catch (err) {
        console.error(err);
        showNotification(err.response?.data?.error || 'Failed to create booking.', 'error');
      } finally {
        setSubmitting(false);
      }
      return;
    }

    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      // 1. Create Reservation
      const res = await axios.post(`${API_BASE_URL}/users/rooms/${bookingRoom.id}/reserve-now/`, {
        guest_name: bookingForm.guest_name,
        guest_email: bookingForm.guest_email,
        guest_phone: bookingForm.guest_phone,
        check_in_date: bookingForm.check_in_date,
        check_out_date: bookingForm.check_out_date,
        adults: bookingForm.adults,
        children: bookingForm.children,
        notes: bookingForm.notes,
        source: 'reception',
        pay_now: 'false',
      }, config);

      const reservation = res.data.reservation;

      // 2. Perform immediate Check-In if requested (Cash / Bank Transfer)
      if (bookingForm.check_in_now) {
        await axios.patch(`${API_BASE_URL}/users/rooms/${bookingRoom.id}/front-desk-status/`, {
          action: 'checkin',
          reservation_id: reservation.id,
          payment_method: bookingForm.payment_method,
          payment_reference: bookingForm.payment_reference,
        }, config);
        showNotification(`Walk-in check-in complete! Payment: ${bookingForm.payment_method}.`);
      } else {
        showNotification('Walk-in booking created. Room reserved.');
      }

      setShowBookingModal(false);
      setBookingRoom(null);
      resetBookingForm();
      fetchData();
    } catch (err) {
      console.error(err);
      showNotification(err.response?.data?.error || 'Failed to create booking.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const resetBookingForm = () => {
    setBookingForm({
      guest_name: '',
      guest_email: '',
      guest_phone: '',
      check_in_date: new Date().toISOString().split('T')[0],
      check_out_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
      adults: 1,
      children: 0,
      notes: '',
      check_in_now: true,
      payment_method: 'Cash',
      payment_reference: '',
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'Available': return '#10b981'; // Green
      case 'Occupied': return '#ef4444'; // Red
      case 'Reserved': return '#f59e0b'; // Orange
      case 'Cleaning': return '#3b82f6'; // Blue
      case 'Maintenance': return '#6b7280'; // Grey
      default: return '#fff';
    }
  };

  return (
    <div style={styles.container}>
      {/* Top Header */}
      <header style={styles.header} className="reception-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={styles.logoBadge}><Bed size={22} color="#0f766e" /></div>
          <div>
            <h1 style={styles.title}>Front Desk Console</h1>
            <p style={styles.subtitle}>Smart Hotel PMS Reception Dashboard</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={styles.tabGroup} className="reception-tab-group">
          <button 
            style={activeTab === 'grid' ? styles.activeTabBtn : styles.tabBtn} 
            onClick={() => setActiveTab('grid')}
          >
            <LayoutGrid size={16} /> Room Map
          </button>
          <button 
            style={activeTab === 'reservations' ? styles.activeTabBtn : styles.tabBtn} 
            onClick={() => setActiveTab('reservations')}
          >
            <ListOrdered size={16} /> Arrivals & Bookings
          </button>
          <button 
            style={activeTab === 'checkin' ? styles.activeTabBtn : styles.tabBtn} 
            onClick={() => setActiveTab('checkin')}
          >
            <QrCode size={16} /> Verification & QR
          </button>
          <button 
            style={activeTab === 'reports' ? styles.activeTabBtn : styles.tabBtn} 
            onClick={() => setActiveTab('reports')}
          >
            <TrendingUp size={16} /> Reports
          </button>
        </div>

        {/* User profile / Logout */}
        <div style={styles.userSection}>
          <div style={styles.userInfo}>
            <p style={styles.userName}>{userData?.username || 'Receptionist'}</p>
            <p style={styles.userRole}>RECEPTION DESK</p>
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn} title="Log Out"><LogOut size={16} color="#ef4444" /></button>
        </div>
      </header>

      {/* Floating Notifications */}
      <AnimatePresence>
        {message.text && (
          <motion.div 
            initial={{ opacity: 0, y: -50 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0, y: -50 }} 
            style={{
              ...styles.notification, 
              backgroundColor: message.type === 'error' ? 'rgba(239, 68, 68, 0.95)' : 'rgba(16, 185, 129, 0.95)',
              borderColor: message.type === 'error' ? '#ef4444' : '#10b981'
            }}
          >
            {message.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle size={18} />}
            <span>{message.text}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <main style={styles.main} className="reception-main">
        {/* Stats Row */}
        <div style={styles.statsGrid} className="reception-stats-grid">
          <div style={styles.statCard}>
            <div style={{ ...styles.statIconCircle, color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.1)' }}><Bed size={20} /></div>
            <div>
              <small style={styles.statLabel}>ROOM OCCUPANCY</small>
              <h3 style={styles.statValue}>{stats.occupied} <span style={{ fontSize: '14px', fontWeight: '500', color: '#64748b' }}>/ {stats.total} Occupied</span></h3>
              <div style={styles.progressBar}><div style={{ ...styles.progressFill, width: `${(stats.occupied / (stats.total || 1)) * 100}%`, backgroundColor: '#0f766e' }} /></div>
            </div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statIconCircle, color: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)' }}><CheckCircle size={20} /></div>
            <div>
              <small style={styles.statLabel}>AVAILABLE ROOMS</small>
              <h3 style={styles.statValue}>{stats.available} <span style={{ fontSize: '14px', fontWeight: '500', color: '#64748b' }}>Ready</span></h3>
              <div style={styles.progressBar}><div style={{ ...styles.progressFill, width: `${(stats.available / (stats.total || 1)) * 100}%`, backgroundColor: '#10b981' }} /></div>
            </div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statIconCircle, color: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.1)' }}><Calendar size={20} /></div>
            <div>
              <small style={styles.statLabel}>TODAY'S ARRIVALS</small>
              <h3 style={styles.statValue}>{stats.arrivals} <span style={{ fontSize: '14px', fontWeight: '500', color: '#64748b' }}>Stays pending</span></h3>
              <div style={styles.progressBar}><div style={{ ...styles.progressFill, width: `${stats.arrivals > 0 ? 50 : 0}%`, backgroundColor: '#f59e0b' }} /></div>
            </div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statIconCircle, color: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)' }}><Clock size={20} /></div>
            <div>
              <small style={styles.statLabel}>TODAY'S DEPARTURES</small>
              <h3 style={styles.statValue}>{stats.departures} <span style={{ fontSize: '14px', fontWeight: '500', color: '#64748b' }}>Stays pending</span></h3>
              <div style={styles.progressBar}><div style={{ ...styles.progressFill, width: `${stats.departures > 0 ? 50 : 0}%`, backgroundColor: '#3b82f6' }} /></div>
            </div>
          </div>
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          {/* TAB 1: ROOM MAP / GRID */}
          {activeTab === 'grid' && (
            <motion.div 
              key="grid-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              style={styles.contentWrapper}
            >
              {/* Toolbar filters */}
              <div style={styles.toolbar}>
                <div style={{ display: 'flex', gap: '15px' }}>
                  <div style={styles.filterBox}>
                    <Filter size={14} color="#64748b" />
                    <select style={styles.select} value={roomTypeFilter} onChange={e => setRoomTypeFilter(e.target.value)}>
                      {roomTypes.map(t => <option key={t} value={t}>{t} Types</option>)}
                    </select>
                  </div>
                  <div style={styles.filterBox}>
                    <Filter size={14} color="#64748b" />
                    <select style={styles.select} value={roomStatusFilter} onChange={e => setRoomStatusFilter(e.target.value)}>
                      <option value="All">All Statuses</option>
                      <option value="Available">Available</option>
                      <option value="Occupied">Occupied</option>
                      <option value="Reserved">Reserved</option>
                      <option value="Cleaning">Cleaning</option>
                      <option value="Maintenance">Maintenance</option>
                    </select>
                  </div>
                </div>

                <div style={styles.legend}>
                  <span style={styles.legendItem}><span style={{ ...styles.legendDot, backgroundColor: '#10b981' }} /> Available</span>
                  <span style={styles.legendItem}><span style={{ ...styles.legendDot, backgroundColor: '#ef4444' }} /> Occupied</span>
                  <span style={styles.legendItem}><span style={{ ...styles.legendDot, backgroundColor: '#f59e0b' }} /> Reserved</span>
                  <span style={styles.legendItem}><span style={{ ...styles.legendDot, backgroundColor: '#3b82f6' }} /> Cleaning</span>
                  <span style={styles.legendItem}><span style={{ ...styles.legendDot, backgroundColor: '#6b7280' }} /> Maintenance</span>
                </div>
              </div>

              {/* Grid of Floors and Rooms */}
              {loading ? (
                <div style={styles.loaderSection}><RefreshCcw className="animate-spin" size={32} /> Loading room map...</div>
              ) : Object.keys(groupedRooms).length === 0 ? (
                <div style={styles.emptyCard}>No rooms match the selected filters. Please adjust filters or register rooms in settings.</div>
              ) : (
                Object.keys(groupedRooms).map(floor => (
                  <div key={floor} style={styles.floorSection}>
                    <h4 style={styles.floorTitle}>Floor {floor}</h4>
                    <div style={styles.roomsGrid}>
                      {groupedRooms[floor].map(room => (
                        <motion.div 
                          key={room.id}
                          whileHover={{ scale: 1.02 }}
                          style={{
                            ...styles.roomCard, 
                            borderLeft: `5px solid ${getStatusColor(room.status)}`
                          }}
                          onClick={() => setSelectedRoom(room)}
                        >
                          <div style={styles.roomCardHeader}>
                            <h3 style={styles.roomCardNumber}>{room.room_number}</h3>
                            <span style={{
                              ...styles.statusBadge,
                              backgroundColor: `${getStatusColor(room.status)}15`,
                              color: getStatusColor(room.status)
                            }}>{room.status}</span>
                          </div>
                          <p style={styles.roomCardType}>{room.name} ({room.room_type})</p>
                          {room.status === 'Occupied' && (() => {
                            const activeRes = reservations.find(r => Number(r.room) === Number(room.id) && r.status === 'checked_in');
                            const payRef = activeRes?.payment_reference;
                            if (!payRef) return null;
                            const method = payRef.includes('Digital') ? 'Digital' : payRef.includes('Bank') ? 'Bank' : 'Cash';
                            const methodColor = method === 'Digital' ? '#0284c7' : method === 'Bank' ? '#7c3aed' : '#16a34a';
                            return (
                              <div style={{ fontSize: '10px', fontWeight: 700, color: methodColor, backgroundColor: `${methodColor}15`, padding: '2px 7px', borderRadius: 5, display: 'inline-block', marginTop: 2 }}>
                                {method} Payment
                              </div>
                            );
                          })()}
                          <div style={styles.roomCardFooter}>
                            <div style={styles.roomCardCap}><User size={12} /> {room.max_adults} + {room.max_children}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <div style={styles.roomCardPrice}>ETB {Number(room.base_price).toFixed(0)}/night</div>
                              <button
                                title="View Room Details"
                                onClick={e => {
                                  e.stopPropagation();
                                  const imgs = [room.main_image, room.image_2, room.image_3].filter(Boolean);
                                  setDetailImageIndex(0);
                                  setDetailRoom({ ...room, _images: imgs });
                                  setShowRoomDetailModal(true);
                                }}
                                style={{
                                  background: 'rgba(15,118,110,0.1)', border: 'none', borderRadius: '7px',
                                  padding: '4px 6px', cursor: 'pointer', color: '#0f766e',
                                  display: 'flex', alignItems: 'center',
                                }}
                              >
                                <Eye size={14} />
                              </button>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </motion.div>
          )}

          {/* TAB 2: ARRIVALS & RESERVATIONS LIST */}
          {activeTab === 'reservations' && (
            <motion.div 
              key="res-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              style={styles.contentWrapper}
            >
              <div style={styles.tableHeader}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold' }}>All Reservations & Stays Log</h2>
                <p style={styles.subtitle}>Recent stays and check-in history</p>
              </div>

              {loading ? (
                <div style={styles.loaderSection}><RefreshCcw className="animate-spin" size={32} /> Loading bookings...</div>
              ) : reservations.length === 0 ? (
                <div style={styles.emptyCard}>No reservations registered in the database.</div>
              ) : (
                <div style={styles.tableScroll}>
                  <table style={styles.table}>
                    <thead>
                      <tr style={styles.trHead}>
                        <th style={styles.th}>Guest</th>
                        <th style={styles.th}>Room</th>
                        <th style={styles.th}>Stay Duration</th>
                        <th style={styles.th}>Payment</th>
                        <th style={styles.th}>Method / Reference</th>
                        <th style={styles.th}>Reservation Status</th>
                        <th style={styles.th}>Confirmation Code</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reservations.map(res => (
                        <tr key={res.id} style={styles.trRow}>
                          <td style={styles.td}>
                            <div>
                              <strong style={styles.tableName}>{res.guest_name}</strong>
                              <div style={styles.tableMeta}><Phone size={10} /> {res.guest_phone || 'N/A'}</div>
                            </div>
                          </td>
                          <td style={styles.td}>
                            <div>
                              <strong>{res.room_name}</strong>
                              <div style={styles.tableMeta}>Room {res.room_number}</div>
                            </div>
                          </td>
                          <td style={styles.td}>
                            <div>
                              <span>{res.check_in_date}</span>
                              <div style={{ color: '#64748b', fontSize: '10px' }}>to {res.check_out_date}</div>
                            </div>
                          </td>
                          <td style={styles.td}>
                            <span style={{
                              ...styles.tablePill,
                              color: res.payment_status === 'paid' ? '#10b981' : '#f59e0b',
                              backgroundColor: res.payment_status === 'paid' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)'
                            }}>{res.payment_status?.toUpperCase()}</span>
                          </td>
                          <td style={styles.td}>
                            {res.payment_reference ? (
                              <div>
                                <span style={{
                                  ...styles.tablePill,
                                  color: res.payment_reference.includes('Digital') ? '#0284c7' : res.payment_reference.includes('Bank') ? '#7c3aed' : '#16a34a',
                                  backgroundColor: res.payment_reference.includes('Digital') ? 'rgba(2,132,199,0.1)' : res.payment_reference.includes('Bank') ? 'rgba(124,58,237,0.1)' : 'rgba(22,163,74,0.1)',
                                }}>
                                  {res.payment_reference.includes('Digital') ? '📱 Digital' : res.payment_reference.includes('Bank') ? '🏦 Bank' : '💵 Cash'}
                                </span>
                                {res.payment_reference.includes('-') && (
                                  <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: 3, fontFamily: 'monospace' }}>
                                    {res.payment_reference.split(' - ')[1] || ''}
                                  </div>
                                )}
                              </div>
                            ) : <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>}
                          </td>
                          <td style={styles.td}>
                            <span style={{
                              ...styles.tablePill,
                              color: res.status === 'checked_in' ? '#10b981' : res.status === 'checked_out' ? '#6b7280' : '#f59e0b',
                              backgroundColor: res.status === 'checked_in' ? 'rgba(16, 185, 129, 0.1)' : res.status === 'checked_out' ? 'rgba(107, 114, 128, 0.1)' : 'rgba(245, 158, 11, 0.1)'
                            }}>{res.status?.replace('_', ' ')?.toUpperCase()}</span>
                          </td>
                          <td style={styles.td}><code style={styles.code}>{res.confirmation_code}</code></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </motion.div>
          )}

          {/* TAB 3: QR CHECK-IN & VALIDATION */}
          {activeTab === 'checkin' && (
            <motion.div 
              key="checkin-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              style={styles.checkinCenter}
            >
              <div style={styles.searchCard}>
                <div style={styles.cardIcon}><QrCode size={32} color="#0f766e" /></div>
                <h2 style={styles.cardTitle}>Verify & Check-In Guest</h2>
                <p style={styles.cardSub}>Search by confirmation code or scan guest QR token</p>
                
                <form onSubmit={handleVerifyCheckInCode} style={styles.form}>
                  <div style={styles.inputWrapper}>
                    <Search style={styles.searchIcon} size={20} />
                    <input 
                      value={checkinCode}
                      onChange={(e) => setCheckinCode(e.target.value.toUpperCase())}
                      placeholder="ENTER TOKEN OR CONFIRMATION CODE"
                      style={styles.input}
                    />
                  </div>
                  <button disabled={submitting} style={styles.submitBtn}>
                    {submitting ? <RefreshCcw className="animate-spin" size={18} /> : <QrCode size={18} />}
                    Verify Booking
                  </button>
                </form>
              </div>

              {/* Verified reservation info card */}
              <AnimatePresence>
                {verifiedReservation && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    style={styles.verifiedCard}
                  >
                    <div style={styles.verifiedCardHeader}>
                      <div style={styles.badge}><CheckCircle size={14} /> BOOKING RECORD VERIFIED</div>
                      <code style={styles.code}>{verifiedReservation.confirmation_code}</code>
                    </div>

                    <div style={styles.verifiedHero}>
                      <div style={styles.guestIcon}><User size={30} color="#fff" /></div>
                      <div>
                        <h2 style={styles.guestName}>{verifiedReservation.guest_name}</h2>
                        <span style={verifiedReservation.payment_status === 'paid' ? styles.paidBadge : styles.pendingBadge}>
                          Payment: {verifiedReservation.payment_status?.toUpperCase()} (ETB {verifiedReservation.total_amount})
                        </span>
                      </div>
                    </div>

                    <div style={styles.detailsGrid}>
                      <DetailBox icon={<Bed size={16}/>} label="Room" value={verifiedReservation.room_name} sub={`Room ${verifiedReservation.room_number}`} />
                      <DetailBox icon={<Calendar size={16}/>} label="Stay Duration" value={`${verifiedReservation.check_in_date}`} sub={`to ${verifiedReservation.check_out_date}`} />
                      <DetailBox icon={<Clock size={16}/>} label="Check-in Source" value={verifiedReservation.source === 'public' ? 'Online Engine' : 'Front Desk'} sub="Registry Origin" />
                      <DetailBox icon={<UserCheck size={16}/>} label="Registry Status" value={verifiedReservation.status?.toUpperCase()?.replace('_', ' ')} sub="Stays log" />
                    </div>

                    <div style={styles.modalFooter}>
                      <button onClick={() => setVerifiedReservation(null)} style={styles.cancelLink}>Clear</button>
                      
                      {verifiedReservation.status === 'confirmed' || verifiedReservation.status === 'pending' ? (
                        <button 
                          onClick={() => handleCheckInVerified(verifiedReservation.room_id || verifiedReservation.room, verifiedReservation.id)} 
                          style={styles.doneBtn}
                          disabled={submitting}
                        >
                          {submitting ? 'Opening Payment...' : 'Proceed to Payment & Check-In'}
                        </button>
                      ) : (
                        <div style={styles.checkedInMessage}><Check size={16} /> Guest is already checked in.</div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* TAB 4: REPORTS CENTER */}
          {activeTab === 'reports' && (
            <motion.div 
              key="reports-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              style={styles.contentWrapper}
            >
              <ReportsCenter />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* MODAL 1: ROOM DETAILS & QUICK ACTIONS DRAWER */}
      <AnimatePresence>
        {selectedRoom && (
          <div style={styles.overlay} onClick={() => setSelectedRoom(null)}>
            <motion.div 
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25 }}
              style={styles.drawer} 
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div style={styles.drawerHeader}>
                <div>
                  <span style={styles.drawerKicker}>Room map drawer</span>
                  <h2 style={styles.drawerTitle}>Room {selectedRoom.room_number}</h2>
                </div>
                <button onClick={() => setSelectedRoom(null)} style={styles.drawerClose}><X size={20} /></button>
              </div>

              {/* Content */}
              <div style={styles.drawerContent}>
                {/* Visual Status Indicator */}
                <div style={{
                  ...styles.statusHero,
                  backgroundColor: `${getStatusColor(selectedRoom.status)}10`,
                  borderLeft: `4px solid ${getStatusColor(selectedRoom.status)}`
                }}>
                  <div style={styles.statusHeroLabel}>Current Room Status</div>
                  <div style={{ ...styles.statusHeroValue, color: getStatusColor(selectedRoom.status) }}>{selectedRoom.status}</div>
                </div>

                {/* Room specifications */}
                <div style={styles.infoSection}>
                  <h4 style={styles.infoSectionTitle}>ROOM DETAILS</h4>
                  <div style={styles.infoGrid}>
                    <div style={styles.infoBox}><small>Room Name</small><strong>{selectedRoom.name}</strong></div>
                    <div style={styles.infoBox}><small>Room Type</small><strong>{selectedRoom.room_type}</strong></div>
                    <div style={styles.infoBox}><small>Bed Configuration</small><strong>{selectedRoom.num_beds} x {selectedRoom.bed_type} Beds</strong></div>
                    <div style={styles.infoBox}><small>Nightly Price</small><strong>ETB {selectedRoom.base_price}</strong></div>
                    <div style={styles.infoBox}><small>Capacity Limit</small><strong>Max {selectedRoom.max_adults} Adults / {selectedRoom.max_children} Kids</strong></div>
                    <div style={styles.infoBox}><small>Floor Level</small><strong>Floor {selectedRoom.floor_number}</strong></div>
                  </div>
                </div>

                {/* Dynamic Actions Based on Status */}
                <div style={styles.infoSection}>
                  <h4 style={styles.infoSectionTitle}>PMS ACTIONS & STATE CONTROLS</h4>
                  <div style={styles.actionsStack}>
                    {/* AVAILABLE ROOM ACTIONS */}
                    {selectedRoom.status === 'Available' && (
                      <>
                        <button 
                          style={styles.primaryActionBtn} 
                          onClick={() => {
                            setBookingRoom(selectedRoom);
                            setShowBookingModal(true);
                            setSelectedRoom(null);
                          }}
                        >
                          <Plus size={16} /> Create Walk-In Booking
                        </button>
                        <button 
                          style={styles.secondaryActionBtn} 
                          onClick={() => handleUpdateRoomStatus(selectedRoom.id, 'Cleaning')}
                        >
                          <RefreshCcw size={16} /> Mark for Cleaning / Service
                        </button>
                        <button 
                          style={{ ...styles.secondaryActionBtn, color: '#ef4444' }} 
                          onClick={() => handleUpdateRoomStatus(selectedRoom.id, 'Maintenance')}
                        >
                          <ShieldAlert size={16} /> Place in Maintenance
                        </button>
                      </>
                    )}

                    {/* OCCUPIED ROOM ACTIONS */}
                    {selectedRoom.status === 'Occupied' && (
                      <>
                        <button 
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#dc2626', color: '#fff', boxShadow: '0 4px 14px rgba(220,38,38,0.3)' }} 
                          onClick={() => {
                            const activeRes = reservations.find(r => Number(r.room) === Number(selectedRoom.id) && r.status === 'checked_in');
                            if (activeRes) {
                              handleOpenCheckoutModal(selectedRoom, activeRes);
                            } else {
                              handleUpdateRoomStatus(selectedRoom.id, 'Cleaning');
                            }
                          }}
                        >
                          <LogOut size={16} /> Guest Check-Out (Bill & Pay)
                        </button>
                      </>
                    )}

                    {/* RESERVED ROOM ACTIONS */}
                    {selectedRoom.status === 'Reserved' && (
                      <>
                        <button 
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#10b981', color: '#fff' }} 
                          onClick={() => {
                            const activeRes = reservations.find(r => Number(r.room) === Number(selectedRoom.id) && r.status === 'confirmed');
                            if (activeRes) {
                              setSelectedRoom(null);
                              handleCheckInVerified(selectedRoom.id, activeRes.id);
                            } else {
                              handleUpdateRoomStatus(selectedRoom.id, 'Occupied');
                            }
                          }}
                        >
                          <UserCheck size={16} /> Complete Guest Check-In
                        </button>
                        <button 
                          style={{ ...styles.secondaryActionBtn, color: '#ef4444' }} 
                          onClick={() => handleUpdateRoomStatus(selectedRoom.id, 'Available')}
                        >
                          <X size={16} /> Cancel Reservation
                        </button>
                      </>
                    )}

                    {/* CLEANING / MAINTENANCE ACTIONS */}
                    {(selectedRoom.status === 'Cleaning' || selectedRoom.status === 'Maintenance') && (
                      <>
                        <button 
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#10b981', color: '#fff' }} 
                          onClick={() => handleUpdateRoomStatus(selectedRoom.id, 'Available')}
                        >
                          <Check size={16} /> Complete Service (Mark Available)
                        </button>
                        {selectedRoom.status === 'Cleaning' && (
                          <button 
                            style={{ ...styles.secondaryActionBtn, color: '#ef4444' }} 
                            onClick={() => handleUpdateRoomStatus(selectedRoom.id, 'Maintenance')}
                          >
                            <ShieldAlert size={16} /> Transfer to Maintenance
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* DYNAMIC FOLIO MANAGEMENT FOR OCCUPIED ROOMS */}
                {selectedRoom.status === 'Occupied' && activeReservation && (
                  <div style={styles.infoSection}>
                    <h4 style={styles.infoSectionTitle}>GUEST FOLIO & EXTRA SERVICES</h4>
                    
                    <div style={styles.folioContainer}>
                      {/* Summary box */}
                      <div style={styles.folioSummary}>
                        <div style={styles.folioSummaryRow}>
                          <span>Room Charge ({folioTotal.nights} nights):</span>
                          <strong>ETB {Number(folioTotal.roomCost).toFixed(0)}</strong>
                        </div>
                        <div style={styles.folioSummaryRow}>
                          <span>Extra Charges:</span>
                          <strong>ETB {Number(folioTotal.extras).toFixed(0)}</strong>
                        </div>
                        <div style={{ ...styles.folioSummaryRow, borderTop: '1px dashed #cbd5e1', paddingTop: '8px', marginTop: '8px', fontSize: '15px' }}>
                          <span style={{ color: '#0f766e', fontWeight: '800' }}>TOTAL AMOUNT:</span>
                          <strong style={{ color: '#0f766e', fontWeight: '900' }}>ETB {Number(folioTotal.grandTotal).toFixed(0)}</strong>
                        </div>
                      </div>

                      {/* Charges List */}
                      <div style={styles.folioList}>
                        {folioLoading ? (
                          <div style={{ textAlign: 'center', padding: '15px 0', color: '#64748b' }}><RefreshCcw size={16} className="animate-spin" /> Loading charges...</div>
                        ) : folioCharges.length === 0 ? (
                          <p style={styles.noFolioText}>No extra services/charges registered yet.</p>
                        ) : (
                          folioCharges.map(charge => (
                            <div key={charge.id} style={styles.folioItem}>
                              <div>
                                <span style={styles.folioItemDesc}>{charge.description}</span>
                                <small style={styles.folioItemMeta}>{new Date(charge.added_at).toLocaleDateString()}</small>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={styles.folioItemAmt}>ETB {Number(charge.amount).toFixed(0)}</span>
                                <button 
                                  onClick={() => handleDeleteFolioCharge(charge.id)} 
                                  style={styles.deleteChargeBtn}
                                  title="Remove Charge"
                                >
                                  <Trash2 size={12} />
                                </button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>

                      {/* Add Charge Form */}
                      <form onSubmit={handleAddFolioCharge} style={styles.addFolioForm}>
                        <input 
                          required
                          value={newCharge.description}
                          onChange={e => setNewCharge({ ...newCharge, description: e.target.value })}
                          placeholder="Laundry, Bar, Spa..."
                          style={styles.addFolioInputDesc}
                        />
                        <input 
                          required
                          type="number"
                          value={newCharge.amount}
                          onChange={e => setNewCharge({ ...newCharge, amount: e.target.value })}
                          placeholder="Amount"
                          style={styles.addFolioInputAmt}
                        />
                        <button type="submit" style={styles.addFolioSubmit} disabled={submitting}>Add</button>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* MODAL 3: CHECKOUT PAYMENT WIZARD */}
      <AnimatePresence>
        {showCheckoutModal && checkoutReservation && checkoutRoom && (
          <div style={styles.overlay} onClick={() => { if (!submitting) { setShowCheckoutModal(false); setCheckoutSuccess(null); } }}>
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 30 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 30 }}
              transition={{ type: 'spring', damping: 28 }}
              style={{ ...styles.modal, maxWidth: '560px', maxHeight: '92vh', overflowY: 'auto', padding: '0' }}
              onClick={e => e.stopPropagation()}
            >
              {/* SUCCESS SCREEN */}
              {checkoutSuccess ? (
                <div style={{ padding: '40px 32px', textAlign: 'center' }}>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', damping: 14 }}
                    style={{ width: 80, height: 80, borderRadius: '50%', background: 'linear-gradient(135deg,#10b981,#059669)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}
                  >
                    <CheckCircle size={44} color="#fff" />
                  </motion.div>
                  <h2 style={{ margin: '0 0 6px', color: '#0f172a', fontSize: '22px' }}>Checkout Complete!</h2>
                  <p style={{ color: '#64748b', margin: '0 0 24px', fontSize: '14px' }}>Room {checkoutRoom.room_number} is now set for cleaning.</p>
                  <div style={{ background: 'linear-gradient(135deg,#f0fdf4,#dcfce7)', border: '1px solid #86efac', borderRadius: '16px', padding: '20px 24px', marginBottom: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Guest</span>
                      <span style={{ color: '#15803d', fontWeight: 700 }}>{checkoutReservation.guest_name}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Payment Method</span>
                      <span style={{ color: '#15803d', fontWeight: 700 }}>{checkoutSuccess.method}</span>
                    </div>
                    {checkoutSuccess.reference && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Reference</span>
                        <span style={{ color: '#15803d', fontWeight: 700, fontSize: '12px' }}>{checkoutSuccess.reference}</span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed #86efac', paddingTop: '12px', marginTop: '4px' }}>
                      <span style={{ color: '#166534', fontSize: '15px', fontWeight: 700 }}>TOTAL PAID</span>
                      <span style={{ color: '#15803d', fontSize: '20px', fontWeight: 900 }}>ETB {Number(checkoutSuccess.grand_total).toLocaleString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => { setShowCheckoutModal(false); setCheckoutSuccess(null); setSelectedRoom(null); }}
                    style={{ ...styles.primaryActionBtn, backgroundColor: '#0f766e', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px' }}
                  >
                    <Check size={18} /> Done — Close
                  </button>
                </div>
              ) : (
                <>
                  {/* HEADER */}
                  <div style={{ background: 'linear-gradient(135deg,#1e293b 0%,#0f172a 100%)', padding: '22px 26px', borderRadius: '20px 20px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <small style={{ color: '#94a3b8', fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                        <LogOut size={12} style={{ marginRight: 4 }} /> GUEST CHECK-OUT
                      </small>
                      <h2 style={{ margin: '4px 0 0', color: '#fff', fontSize: '20px' }}>Room {checkoutRoom.room_number} — {checkoutReservation.guest_name}</h2>
                    </div>
                    <button onClick={() => setShowCheckoutModal(false)} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '10px', padding: '8px', cursor: 'pointer', color: '#fff', display: 'flex' }}>
                      <X size={20} />
                    </button>
                  </div>

                  <div style={{ padding: '24px 26px' }}>
                    {/* BILL BREAKDOWN */}
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '18px 20px', marginBottom: '20px' }}>
                      <h4 style={{ margin: '0 0 14px', color: '#0f172a', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Itemized Bill</h4>
                      {/* Room cost row */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px' }}>
                        <span style={{ color: '#475569' }}>Room {checkoutRoom.room_number} × {checkoutBill.nights} night{checkoutBill.nights > 1 ? 's' : ''} @ ETB {Number(checkoutRoom.base_price).toLocaleString()}</span>
                        <strong style={{ color: '#16a34a', fontSize: '12px' }}>Paid at Check-In</strong>
                      </div>
                      {/* Extra folio charges */}
                      {checkoutFolio.map(c => (
                        <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '13px' }}>
                          <span style={{ color: '#64748b' }}>• {c.description}</span>
                          <span style={{ color: '#475569', fontWeight: 600 }}>ETB {Number(c.amount).toLocaleString()}</span>
                        </div>
                      ))}
                      {checkoutFolio.length === 0 && (
                        <p style={{ color: '#94a3b8', fontSize: '12px', margin: '4px 0 10px', fontStyle: 'italic' }}>No extra charges registered.</p>
                      )}
                      {/* Grand total */}
                      <div style={{ borderTop: '2px dashed #cbd5e1', paddingTop: '12px', marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#0f766e', fontWeight: 800, fontSize: '15px' }}>AMOUNT DUE (EXTRAS ONLY)</span>
                        <span style={{ color: '#0f766e', fontWeight: 900, fontSize: '22px' }}>ETB {Number(checkoutBill.extras).toLocaleString()}</span>
                      </div>
                    </div>

                    {/* PAYMENT METHOD SELECTOR */}
                    <h4 style={{ margin: '0 0 12px', color: '#0f172a', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Select Payment Method</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '22px' }}>
                      {[
                        { id: 'Cash', label: 'Cash', icon: <Banknote size={20} />, color: '#16a34a', bg: '#f0fdf4', border: '#86efac' },
                        { id: 'Digital Payment', label: 'Digital (QR)', icon: <QrCode size={20} />, color: '#0284c7', bg: '#eff6ff', border: '#93c5fd' },
                        { id: 'Bank Transfer', label: 'Bank Transfer', icon: <Building2 size={20} />, color: '#7c3aed', bg: '#faf5ff', border: '#c4b5fd' },
                      ].map(m => (
                        <button
                          key={m.id}
                          onClick={() => { setCheckoutPaymentMethod(m.id); setChapaSession(null); setBankTransferRef(''); }}
                          style={{
                            border: `2px solid ${checkoutPaymentMethod === m.id ? m.color : '#e2e8f0'}`,
                            background: checkoutPaymentMethod === m.id ? m.bg : '#fff',
                            borderRadius: '14px',
                            padding: '14px 10px',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: '6px',
                            color: checkoutPaymentMethod === m.id ? m.color : '#94a3b8',
                            fontWeight: 700,
                            fontSize: '11px',
                            transition: 'all 0.18s ease',
                            boxShadow: checkoutPaymentMethod === m.id ? `0 4px 14px ${m.color}22` : 'none',
                          }}
                        >
                          {m.icon}
                          {m.label}
                        </button>
                      ))}
                    </div>

                    {/* CASH FLOW */}
                    {checkoutPaymentMethod === 'Cash' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '14px', padding: '16px 18px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <Banknote size={22} color="#16a34a" />
                          <p style={{ margin: 0, color: '#15803d', fontSize: '13px', fontWeight: 600 }}>
                            Collect ETB {Number(checkoutBill.extras).toLocaleString()} in cash from the guest and click below to complete checkout.
                          </p>
                        </div>
                        <button
                          disabled={submitting}
                          onClick={() => handleCompleteCheckout('Cash')}
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#16a34a', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(22,163,74,0.3)', opacity: submitting ? 0.7 : 1 }}
                        >
                          {submitting ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
                          {submitting ? 'Processing...' : 'Complete Checkout — Cash'}
                        </button>
                      </motion.div>
                    )}

                    {/* BANK TRANSFER FLOW */}
                    {checkoutPaymentMethod === 'Bank Transfer' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <div style={{ marginBottom: '14px' }}>
                          <label style={{ display: 'block', color: '#374151', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                            Bank Transaction Reference Number
                          </label>
                          <input
                            value={bankTransferRef}
                            onChange={e => setBankTransferRef(e.target.value)}
                            placeholder="e.g. CBE-20250527-4892, TXN-XXXXXXX"
                            style={{ ...styles.formInput, width: '100%', boxSizing: 'border-box', fontSize: '14px' }}
                          />
                        </div>
                        <button
                          disabled={submitting || !bankTransferRef.trim()}
                          onClick={() => handleCompleteCheckout('Bank Transfer', bankTransferRef.trim())}
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#7c3aed', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(124,58,237,0.3)', opacity: (submitting || !bankTransferRef.trim()) ? 0.6 : 1 }}
                        >
                          {submitting ? <Loader2 size={18} className="animate-spin" /> : <Building2 size={18} />}
                          {submitting ? 'Processing...' : 'Complete Checkout — Bank Transfer'}
                        </button>
                      </motion.div>
                    )}

                    {/* DIGITAL PAYMENT (CHAPA QR) FLOW */}
                    {checkoutPaymentMethod === 'Digital Payment' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        {!chapaSession ? (
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '14px', padding: '18px', marginBottom: '16px' }}>
                              <QrCode size={36} color="#0284c7" style={{ margin: '0 auto 10px', display: 'block' }} />
                              <p style={{ margin: 0, color: '#1e40af', fontSize: '13px', fontWeight: 600 }}>
                                Generate a Chapa payment session. The guest will scan the QR code and pay ETB {Number(checkoutBill.extras).toLocaleString()} directly on their phone.
                              </p>
                            </div>
                            <button
                              disabled={submitting}
                              onClick={handleInitiateDigitalPayment}
                              style={{ ...styles.primaryActionBtn, backgroundColor: '#0284c7', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(2,132,199,0.3)', opacity: submitting ? 0.7 : 1 }}
                            >
                              {submitting ? <Loader2 size={18} className="animate-spin" /> : <QrCode size={18} />}
                              {submitting ? 'Generating...' : 'Generate QR Code'}
                            </button>
                          </div>
                        ) : (
                          <div style={{ textAlign: 'center' }}>
                            {/* QR Code display */}
                            <div style={{ background: '#fff', border: '2px solid #0284c7', borderRadius: '16px', padding: '18px', marginBottom: '16px', display: 'inline-block' }}>
                              <img
                                src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(chapaSession.checkout_url)}`}
                                alt="Chapa Payment QR"
                                style={{ width: '180px', height: '180px', display: 'block' }}
                              />
                            </div>
                            <p style={{ color: '#0f172a', fontWeight: 700, fontSize: '14px', margin: '0 0 4px' }}>
                              Scan to Pay: ETB {Number(chapaSession.grand_total).toLocaleString()}
                            </p>
                            <p style={{ color: '#64748b', fontSize: '12px', margin: '0 0 18px' }}>
                              Guest scans this QR code → pays via Chapa → click Verify below
                            </p>
                            <div style={{ display: 'flex', gap: '10px' }}>
                              <button
                                onClick={() => window.open(chapaSession.checkout_url, '_blank')}
                                style={{ flex: 1, ...styles.secondaryActionBtn, border: '1px solid #bfdbfe', color: '#0284c7', justifyContent: 'center', padding: '12px' }}
                              >
                                <ArrowRight size={16} /> Open Link
                              </button>
                              <button
                                disabled={verifyingPayment}
                                onClick={handleVerifyDigitalPayment}
                                style={{ flex: 2, ...styles.primaryActionBtn, backgroundColor: '#0f766e', color: '#fff', justifyContent: 'center', padding: '12px', boxShadow: '0 4px 14px rgba(15,118,110,0.3)', opacity: verifyingPayment ? 0.7 : 1 }}
                              >
                                {verifyingPayment ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                                {verifyingPayment ? 'Verifying...' : 'Verify Payment'}
                              </button>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </div>
                </>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* MODAL 2: WALK-IN BOOKING & QUICK CHECKIN */}
      <AnimatePresence>
        {showBookingModal && bookingRoom && (
          <div style={styles.overlay} onClick={() => { setShowBookingModal(false); setBookingRoom(null); }}>
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              style={{ ...styles.modal, maxHeight: '92vh', overflowY: 'auto' }} 
              onClick={(e) => e.stopPropagation()}
            >
              <div style={styles.modalHeader}>
                <div>
                  <small style={styles.badge}><Plus size={14} /> NEW WALK-IN REGISTRATION</small>
                  <h2 style={{ margin: '5px 0 0', color: '#0f172a', fontSize: '20px' }}>Room {bookingRoom.room_number} ({bookingRoom.name})</h2>
                </div>
                <button onClick={() => { setShowBookingModal(false); setBookingRoom(null); }} style={styles.closeBtn}><X size={20}/></button>
              </div>

              <form onSubmit={handleCreateWalkInBooking} style={styles.bookingForm}>
                <div style={styles.formGrid}>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Guest Full Name</label>
                    <input 
                      required
                      placeholder="Enter guest full name"
                      value={bookingForm.guest_name}
                      onChange={e => setBookingForm({ ...bookingForm, guest_name: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Phone Number</label>
                    <input 
                      required
                      placeholder="e.g. +251..."
                      value={bookingForm.guest_phone}
                      onChange={e => setBookingForm({ ...bookingForm, guest_phone: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Email Address</label>
                    <input 
                      placeholder="e.g. guest@example.com"
                      value={bookingForm.guest_email}
                      onChange={e => setBookingForm({ ...bookingForm, guest_email: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Check-In Date</label>
                    <input 
                      type="date"
                      value={bookingForm.check_in_date}
                      onChange={e => setBookingForm({ ...bookingForm, check_in_date: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Check-Out Date</label>
                    <input 
                      type="date"
                      value={bookingForm.check_out_date}
                      onChange={e => setBookingForm({ ...bookingForm, check_out_date: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={styles.inputField}>
                    <label style={styles.fieldLabel}>Adults Count</label>
                    <input 
                      type="number"
                      min="1"
                      value={bookingForm.adults}
                      onChange={e => setBookingForm({ ...bookingForm, adults: e.target.value })}
                      style={styles.formInput}
                    />
                  </div>
                  <div style={{ ...styles.inputField, gridColumn: 'span 2' }}>
                    <label style={styles.fieldLabel}>Special Notes / Folio instructions</label>
                    <textarea 
                      placeholder="Enter stay requests, billing notes..."
                      value={bookingForm.notes}
                      onChange={e => setBookingForm({ ...bookingForm, notes: e.target.value })}
                      style={{ ...styles.formInput, height: '70px', resize: 'none' }}
                    />
                  </div>
                </div>

                <div style={styles.checkinSelector}>
                  <input 
                    type="checkbox" 
                    id="checkin-now-checkbox"
                    checked={bookingForm.check_in_now} 
                    onChange={e => setBookingForm({ ...bookingForm, check_in_now: e.target.checked })} 
                    style={styles.checkbox}
                  />
                  <label htmlFor="checkin-now-checkbox" style={styles.checkboxLabel}>
                    <strong>Complete Check-In Immediately</strong>
                    <span>Register guest and mark room as Occupied — requires payment</span>
                  </label>
                </div>

                {/* Payment selector — shown only when check_in_now is true */}
                {bookingForm.check_in_now && (
                  <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={{ borderTop: '1px dashed #cbd5e1', paddingTop: '16px' }}>
                    <label style={{ ...styles.fieldLabel, display: 'block', marginBottom: '10px' }}>Payment Method for Check-In</label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                      {[
                        { id: 'Cash', label: 'Cash', icon: <Banknote size={18} />, color: '#16a34a', bg: '#f0fdf4' },
                        { id: 'Digital Payment', label: 'Digital (QR)', icon: <QrCode size={18} />, color: '#0284c7', bg: '#eff6ff' },
                        { id: 'Bank Transfer', label: 'Bank Transfer', icon: <Building2 size={18} />, color: '#7c3aed', bg: '#faf5ff' },
                      ].map(m => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => setBookingForm({ ...bookingForm, payment_method: m.id, payment_reference: '' })}
                          style={{
                            border: `2px solid ${bookingForm.payment_method === m.id ? m.color : '#e2e8f0'}`,
                            background: bookingForm.payment_method === m.id ? m.bg : '#fff',
                            borderRadius: '12px', padding: '10px 8px', cursor: 'pointer',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
                            color: bookingForm.payment_method === m.id ? m.color : '#94a3b8',
                            fontWeight: 700, fontSize: '11px', transition: 'all 0.15s',
                          }}
                        >
                          {m.icon}{m.label}
                        </button>
                      ))}
                    </div>
                    {bookingForm.payment_method === 'Bank Transfer' && (
                      <input
                        required={bookingForm.check_in_now && bookingForm.payment_method === 'Bank Transfer'}
                        placeholder="Bank transaction reference (e.g. CBE-20250527-XXXX)"
                        value={bookingForm.payment_reference}
                        onChange={e => setBookingForm({ ...bookingForm, payment_reference: e.target.value })}
                        style={{ ...styles.formInput, width: '100%', boxSizing: 'border-box' }}
                      />
                    )}
                    {bookingForm.payment_method === 'Cash' && (
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '10px 14px', fontSize: '12px', color: '#15803d', fontWeight: 600 }}>
                        <Banknote size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                        Collect cash from guest and click Create Stay Registry to complete.
                      </div>
                    )}
                    {bookingForm.payment_method === 'Digital Payment' && (
                      <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px', padding: '10px 14px', fontSize: '12px', color: '#1e40af', fontWeight: 600 }}>
                        <QrCode size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                        A Chapa QR payment session will open after booking is created.
                      </div>
                    )}
                  </motion.div>
                )}

                <div style={styles.modalFooter}>
                  <button type="button" onClick={() => { setShowBookingModal(false); setBookingRoom(null); }} style={styles.cancelLink}>Cancel</button>
                  <button type="submit" style={styles.doneBtn} disabled={submitting}>
                    {submitting ? 'Processing...' : bookingForm.check_in_now ? 'Create & Check-In' : 'Create Reservation'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* MODAL 4: CHECK-IN PAYMENT WIZARD */}
      <AnimatePresence>
        {showCheckinPayModal && (
          <div style={styles.overlay} onClick={() => { if (!submitting) { setShowCheckinPayModal(false); setCheckinSuccess(null); } }}>
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 30 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 30 }}
              transition={{ type: 'spring', damping: 28 }}
              style={{ ...styles.modal, maxWidth: '520px', maxHeight: '92vh', overflowY: 'auto', padding: 0 }}
              onClick={e => e.stopPropagation()}
            >
              {/* SUCCESS SCREEN */}
              {checkinSuccess ? (
                <div style={{ padding: '40px 32px', textAlign: 'center' }}>
                  <motion.div
                    initial={{ scale: 0 }} animate={{ scale: 1 }}
                    transition={{ type: 'spring', damping: 14 }}
                    style={{ width: 80, height: 80, borderRadius: '50%', background: 'linear-gradient(135deg,#10b981,#059669)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}
                  >
                    <CheckCircle size={44} color="#fff" />
                  </motion.div>
                  <h2 style={{ margin: '0 0 6px', color: '#0f172a', fontSize: '22px' }}>Check-In Complete!</h2>
                  <p style={{ color: '#64748b', margin: '0 0 24px', fontSize: '14px' }}>Room {checkinSuccess.room_number} is now Occupied.</p>
                  <div style={{ background: 'linear-gradient(135deg,#f0fdf4,#dcfce7)', border: '1px solid #86efac', borderRadius: '16px', padding: '20px 24px', marginBottom: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Guest</span>
                      <span style={{ color: '#15803d', fontWeight: 700 }}>{checkinSuccess.guest_name}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Payment Method</span>
                      <span style={{ color: '#15803d', fontWeight: 700 }}>{checkinSuccess.method}</span>
                    </div>
                    {checkinSuccess.reference && (
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#166534', fontSize: '13px', fontWeight: 600 }}>Reference</span>
                        <span style={{ color: '#15803d', fontWeight: 700, fontSize: '12px' }}>{checkinSuccess.reference}</span>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => { setShowCheckinPayModal(false); setCheckinSuccess(null); }}
                    style={{ ...styles.primaryActionBtn, backgroundColor: '#0f766e', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px' }}
                  >
                    <Check size={18} /> Done — Close
                  </button>
                </div>
              ) : (
                <>
                  {/* HEADER */}
                  <div style={{ background: 'linear-gradient(135deg,#0f766e 0%,#065f46 100%)', padding: '22px 26px', borderRadius: '20px 20px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <small style={{ color: 'rgba(255,255,255,0.7)', fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                        <UserCheck size={12} style={{ marginRight: 4 }} /> GUEST CHECK-IN PAYMENT
                      </small>
                      <h2 style={{ margin: '4px 0 0', color: '#fff', fontSize: '20px' }}>
                        Room {checkinPayRoom?.room_number} — {checkinPayReservation?.guest_name || 'Guest'}
                      </h2>
                    </div>
                    <button onClick={() => setShowCheckinPayModal(false)} style={{ background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: '10px', padding: '8px', cursor: 'pointer', color: '#fff', display: 'flex' }}>
                      <X size={20} />
                    </button>
                  </div>

                  <div style={{ padding: '24px 26px' }}>
                    {/* Amount summary */}
                    {checkinPayRoom && checkinPayReservation && (() => {
                      const inD = new Date(checkinPayReservation.check_in_date);
                      const outD = new Date(checkinPayReservation.check_out_date);
                      const nights = Math.max(Math.round((outD - inD) / 86400000), 1);
                      const total = Number(checkinPayRoom.base_price || 0) * nights;
                      return (
                        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '16px 18px', marginBottom: '20px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', marginBottom: '6px' }}>
                            <span style={{ color: '#475569' }}>Room {checkinPayRoom.room_number} × {nights} night{nights > 1 ? 's' : ''} @ ETB {Number(checkinPayRoom.base_price).toLocaleString()}</span>
                            <strong>ETB {total.toLocaleString()}</strong>
                          </div>
                          <div style={{ borderTop: '2px dashed #cbd5e1', paddingTop: '10px', marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ color: '#0f766e', fontWeight: 800 }}>AMOUNT DUE</span>
                            <span style={{ color: '#0f766e', fontWeight: 900, fontSize: '20px' }}>ETB {total.toLocaleString()}</span>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Payment method selector */}
                    <h4 style={{ margin: '0 0 12px', color: '#0f172a', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Select Payment Method</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '22px' }}>
                      {[
                        { id: 'Cash', label: 'Cash', icon: <Banknote size={20} />, color: '#16a34a', bg: '#f0fdf4' },
                        { id: 'Digital Payment', label: 'Digital (QR)', icon: <QrCode size={20} />, color: '#0284c7', bg: '#eff6ff' },
                        { id: 'Bank Transfer', label: 'Bank Transfer', icon: <Building2 size={20} />, color: '#7c3aed', bg: '#faf5ff' },
                      ].map(m => (
                        <button
                          key={m.id}
                          onClick={() => { setCheckinPayMethod(m.id); setCheckinBankRef(''); setCheckinChapaSession(null); }}
                          style={{
                            border: `2px solid ${checkinPayMethod === m.id ? m.color : '#e2e8f0'}`,
                            background: checkinPayMethod === m.id ? m.bg : '#fff',
                            borderRadius: '14px', padding: '14px 10px', cursor: 'pointer',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                            color: checkinPayMethod === m.id ? m.color : '#94a3b8',
                            fontWeight: 700, fontSize: '11px', transition: 'all 0.18s ease',
                            boxShadow: checkinPayMethod === m.id ? `0 4px 14px ${m.color}22` : 'none',
                          }}
                        >
                          {m.icon}{m.label}
                        </button>
                      ))}
                    </div>

                    {/* CASH */}
                    {checkinPayMethod === 'Cash' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '14px', padding: '14px 18px', marginBottom: '14px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                          <Banknote size={20} color="#16a34a" />
                          <p style={{ margin: 0, color: '#15803d', fontSize: '13px', fontWeight: 600 }}>Collect cash from the guest and click below to confirm check-in.</p>
                        </div>
                        <button
                          disabled={submitting}
                          onClick={() => handleConfirmCheckinPayment('Cash')}
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#16a34a', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(22,163,74,0.3)', opacity: submitting ? 0.7 : 1 }}
                        >
                          {submitting ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
                          {submitting ? 'Processing...' : 'Confirm Check-In — Cash'}
                        </button>
                      </motion.div>
                    )}

                    {/* BANK TRANSFER */}
                    {checkinPayMethod === 'Bank Transfer' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <div style={{ marginBottom: '12px' }}>
                          <label style={{ display: 'block', color: '#374151', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Bank Transaction Reference Number</label>
                          <input
                            value={checkinBankRef}
                            onChange={e => setCheckinBankRef(e.target.value)}
                            placeholder="e.g. CBE-20250527-4892"
                            style={{ ...styles.formInput, width: '100%', boxSizing: 'border-box', fontSize: '14px' }}
                          />
                        </div>
                        <button
                          disabled={submitting || !checkinBankRef.trim()}
                          onClick={() => handleConfirmCheckinPayment('Bank Transfer', checkinBankRef.trim())}
                          style={{ ...styles.primaryActionBtn, backgroundColor: '#7c3aed', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(124,58,237,0.3)', opacity: (submitting || !checkinBankRef.trim()) ? 0.6 : 1 }}
                        >
                          {submitting ? <Loader2 size={18} className="animate-spin" /> : <Building2 size={18} />}
                          {submitting ? 'Processing...' : 'Confirm Check-In — Bank Transfer'}
                        </button>
                      </motion.div>
                    )}

                    {/* DIGITAL PAYMENT (CHAPA) */}
                    {checkinPayMethod === 'Digital Payment' && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        {!checkinChapaSession ? (
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '14px', padding: '16px', marginBottom: '14px' }}>
                              <QrCode size={34} color="#0284c7" style={{ margin: '0 auto 8px', display: 'block' }} />
                              <p style={{ margin: 0, color: '#1e40af', fontSize: '13px', fontWeight: 600 }}>Generate a Chapa QR session. Guest pays on their phone, then click Verify.</p>
                            </div>
                            <button
                              disabled={submitting}
                              onClick={handleInitiateCheckinDigitalPayment}
                              style={{ ...styles.primaryActionBtn, backgroundColor: '#0284c7', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', fontSize: '15px', boxShadow: '0 4px 14px rgba(2,132,199,0.3)', opacity: submitting ? 0.7 : 1 }}
                            >
                              {submitting ? <Loader2 size={18} className="animate-spin" /> : <QrCode size={18} />}
                              {submitting ? 'Generating...' : 'Generate QR Code'}
                            </button>
                          </div>
                        ) : (
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ background: '#fff', border: '2px solid #0284c7', borderRadius: '16px', padding: '16px', marginBottom: '14px', display: 'inline-block' }}>
                              <img
                                src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(checkinChapaSession.checkout_url)}`}
                                alt="Chapa Check-In QR"
                                style={{ width: 180, height: 180, display: 'block' }}
                              />
                            </div>
                            <p style={{ color: '#0f172a', fontWeight: 700, fontSize: '14px', margin: '0 0 4px' }}>Scan to Pay: ETB {Number(checkinChapaSession.grand_total).toLocaleString()}</p>
                            <p style={{ color: '#64748b', fontSize: '12px', margin: '0 0 16px' }}>Guest scans → pays via Chapa → click Verify below</p>
                            <div style={{ display: 'flex', gap: '10px' }}>
                              <button
                                onClick={() => window.open(checkinChapaSession.checkout_url, '_blank')}
                                style={{ flex: 1, ...styles.secondaryActionBtn, border: '1px solid #bfdbfe', color: '#0284c7', justifyContent: 'center', padding: '12px' }}
                              >
                                <ArrowRight size={16} /> Open Link
                              </button>
                              <button
                                disabled={verifyingCheckinPay}
                                onClick={handleVerifyCheckinDigitalPayment}
                                style={{ flex: 2, ...styles.primaryActionBtn, backgroundColor: '#0f766e', color: '#fff', justifyContent: 'center', padding: '12px', boxShadow: '0 4px 14px rgba(15,118,110,0.3)', opacity: verifyingCheckinPay ? 0.7 : 1 }}
                              >
                                {verifyingCheckinPay ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                                {verifyingCheckinPay ? 'Verifying...' : 'Verify Payment'}
                              </button>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </div>
                </>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
      {/* MODAL 5: ROOM DETAIL PREVIEW */}
      <AnimatePresence>
        {showRoomDetailModal && detailRoom && (() => {
          const imgs = detailRoom._images || [];
          const amenities = [
            ...(Array.isArray(detailRoom.amenities) ? detailRoom.amenities : []),
            ...(Array.isArray(detailRoom.common_amenities) ? detailRoom.common_amenities : []),
          ].filter(Boolean);
          const amenityIcon = (a) => {
            const s = String(a).toLowerCase();
            if (s.includes('wifi') || s.includes('wi-fi')) return <Wifi size={13} />;
            if (s.includes('tv') || s.includes('television')) return <Tv size={13} />;
            if (s.includes('air') || s.includes('ac') || s.includes('condition')) return <Wind size={13} />;
            if (s.includes('coffee') || s.includes('tea') || s.includes('bar')) return <Coffee size={13} />;
            if (s.includes('gym') || s.includes('fitness')) return <Dumbbell size={13} />;
            if (s.includes('park') || s.includes('car')) return <Car size={13} />;
            return <Star size={13} />;
          };
          return (
            <div
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
              onClick={() => setShowRoomDetailModal(false)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0, y: 24 }}
                animate={{ scale: 1, opacity: 1, y: 0 }}
                exit={{ scale: 0.9, opacity: 0, y: 24 }}
                transition={{ type: 'spring', damping: 26 }}
                onClick={e => e.stopPropagation()}
                style={{
                  background: '#fff', borderRadius: '24px', width: '100%', maxWidth: '680px',
                  maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 32px 80px rgba(0,0,0,0.35)',
                }}
              >
                {/* Image Carousel */}
                <div style={{ position: 'relative', background: '#0f172a', borderRadius: '24px 24px 0 0', overflow: 'hidden', height: '240px' }}>
                  {imgs.length > 0 ? (
                    <>
                      <img
                        src={imgs[detailImageIndex]}
                        alt={`Room ${detailRoom.room_number}`}
                        style={{ width: '100%', height: '240px', objectFit: 'cover', display: 'block' }}
                        onError={e => { e.target.style.display = 'none'; }}
                      />
                      {imgs.length > 1 && (
                        <div style={{ position: 'absolute', bottom: '12px', left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: '6px' }}>
                          {imgs.map((_, i) => (
                            <button
                              key={i}
                              onClick={() => setDetailImageIndex(i)}
                              style={{
                                width: i === detailImageIndex ? '24px' : '8px', height: '8px',
                                borderRadius: '999px', border: 'none', cursor: 'pointer',
                                background: i === detailImageIndex ? '#fff' : 'rgba(255,255,255,0.5)',
                                transition: 'all 0.2s',
                              }}
                            />
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div style={{ height: '240px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569' }}>
                      <Bed size={56} color="#334155" />
                    </div>
                  )}
                  {/* Close Button */}
                  <button
                    onClick={() => setShowRoomDetailModal(false)}
                    style={{ position: 'absolute', top: '14px', right: '14px', background: 'rgba(0,0,0,0.45)', border: 'none', borderRadius: '10px', padding: '8px', cursor: 'pointer', color: '#fff', display: 'flex' }}
                  >
                    <X size={20} />
                  </button>
                  {/* Status Badge */}
                  <div style={{
                    position: 'absolute', top: '14px', left: '14px',
                    background: `${getStatusColor(detailRoom.status)}cc`,
                    color: '#fff', borderRadius: '8px', padding: '4px 12px',
                    fontSize: '12px', fontWeight: 800, letterSpacing: '0.06em',
                  }}>{detailRoom.status}</div>
                </div>

                {/* Content */}
                <div style={{ padding: '24px 28px' }}>
                  {/* Title Row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px' }}>
                    <div>
                      <h2 style={{ margin: '0 0 4px', fontSize: '22px', color: '#0f172a', fontWeight: 900 }}>
                        Room {detailRoom.room_number}
                      </h2>
                      <p style={{ margin: 0, color: '#64748b', fontSize: '14px', fontWeight: 600 }}>
                        {detailRoom.name} — {detailRoom.room_type}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '22px', fontWeight: 900, color: '#0f766e' }}>ETB {Number(detailRoom.base_price).toLocaleString()}</div>
                      <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600 }}>per night</div>
                    </div>
                  </div>

                  {/* Info Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '20px' }}>
                    {[
                      { label: 'Floor', value: `Floor ${detailRoom.floor_number}` },
                      { label: 'Bed Type', value: detailRoom.bed_type || '—' },
                      { label: 'Beds', value: detailRoom.num_beds || 1 },
                      { label: 'Capacity', value: `${detailRoom.max_adults} Adults, ${detailRoom.max_children} Children` },
                      { label: 'Check-In', value: detailRoom.check_in_time ? String(detailRoom.check_in_time).slice(0, 5) : '14:00' },
                      { label: 'Check-Out', value: detailRoom.check_out_time ? String(detailRoom.check_out_time).slice(0, 5) : '11:00' },
                      detailRoom.weekend_price && { label: 'Weekend Price', value: `ETB ${Number(detailRoom.weekend_price).toLocaleString()}` },
                      detailRoom.holiday_price && { label: 'Holiday Price', value: `ETB ${Number(detailRoom.holiday_price).toLocaleString()}` },
                      detailRoom.discount_percent > 0 && { label: 'Discount', value: `${detailRoom.discount_percent}%` },
                      detailRoom.extra_bed_price > 0 && { label: 'Extra Bed', value: `ETB ${Number(detailRoom.extra_bed_price).toLocaleString()}` },
                      { label: 'Min Stay', value: `${detailRoom.min_stay || 1} night(s)` },
                      { label: 'Online Booking', value: detailRoom.is_available_online ? '✅ Yes' : '❌ No' },
                    ].filter(Boolean).map(({ label, value }) => (
                      <div key={label} style={{ background: '#f8fafc', borderRadius: '10px', padding: '10px 14px' }}>
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', marginBottom: '2px' }}>{label}</div>
                        <div style={{ fontSize: '14px', color: '#0f172a', fontWeight: 700 }}>{value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Description */}
                  {detailRoom.description && (
                    <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '12px', padding: '14px 16px', marginBottom: '18px' }}>
                      <div style={{ fontSize: '11px', color: '#16a34a', fontWeight: 700, textTransform: 'uppercase', marginBottom: '6px' }}>Description</div>
                      <p style={{ margin: 0, fontSize: '13px', color: '#166534', lineHeight: 1.6 }}>{detailRoom.description}</p>
                    </div>
                  )}

                  {/* Amenities */}
                  {amenities.length > 0 && (
                    <div style={{ marginBottom: '18px' }}>
                      <div style={{ fontSize: '12px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', marginBottom: '10px' }}>Amenities</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {amenities.map((a, i) => (
                          <span key={i} style={{
                            display: 'inline-flex', alignItems: 'center', gap: '5px',
                            background: 'linear-gradient(135deg,#eff6ff,#dbeafe)', border: '1px solid #bfdbfe',
                            color: '#1d4ed8', borderRadius: '999px', padding: '5px 12px',
                            fontSize: '12px', fontWeight: 600,
                          }}>
                            {amenityIcon(a)} {a}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {detailRoom.tags && (
                    <div style={{ marginBottom: '18px' }}>
                      <div style={{ fontSize: '12px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', marginBottom: '8px' }}>Tags</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {detailRoom.tags.split(',').map((t, i) => (
                          <span key={i} style={{ background: '#fef9c3', border: '1px solid #fde68a', color: '#92400e', borderRadius: '999px', padding: '4px 10px', fontSize: '11px', fontWeight: 700 }}>
                            #{t.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Cancellation Policy */}
                  {detailRoom.cancellation_policy && (
                    <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '12px', padding: '12px 16px', marginBottom: '10px' }}>
                      <div style={{ fontSize: '11px', color: '#c2410c', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>Cancellation Policy</div>
                      <p style={{ margin: 0, fontSize: '13px', color: '#9a3412', lineHeight: 1.6 }}>{detailRoom.cancellation_policy}</p>
                    </div>
                  )}

                  <button
                    onClick={() => setShowRoomDetailModal(false)}
                    style={{ ...styles.primaryActionBtn, backgroundColor: '#0f766e', color: '#fff', width: '100%', justifyContent: 'center', padding: '14px', marginTop: '8px' }}
                  >
                    <X size={16} /> Close
                  </button>
                </div>
              </motion.div>
            </div>
          );
        })()}
      </AnimatePresence>

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
  container: { minHeight: '100vh', background: 'linear-gradient(180deg, #f4fbff 0%, #f8fafc 42%, #f2f7f5 100%)', color: '#0f172a', fontFamily: 'system-ui, -apple-system, sans-serif' },
  header: { height: '80px', borderBottom: '1px solid rgba(148,163,184,0.16)', padding: '0 30px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: 'rgba(255, 255, 255, 0.76)', backdropFilter: 'blur(16px)' },
  logoBadge: { width: '40px', height: '40px', backgroundColor: 'rgba(15, 118, 110, 0.1)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  title: { margin: 0, fontSize: '18px', fontWeight: '800', letterSpacing: '-0.3px', color: '#0f172a' },
  subtitle: { margin: 0, fontSize: '11px', color: '#64748b', fontWeight: '500' },
  tabGroup: { display: 'flex', gap: '5px', backgroundColor: '#fff', padding: '4px', borderRadius: '10px', border: '1px solid rgba(148,163,184,0.16)' },
  tabBtn: { display: 'flex', alignItems: 'center', gap: '8px', border: 'none', backgroundColor: 'transparent', color: '#64748b', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600', transition: 'all 0.2s' },
  activeTabBtn: { display: 'flex', alignItems: 'center', gap: '8px', border: 'none', backgroundColor: '#0f766e', color: '#fff', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '800', transition: 'all 0.2s', boxShadow: '0 4px 12px rgba(15,118,110,0.15)' },
  userSection: { display: 'flex', alignItems: 'center', gap: '15px', paddingLeft: '20px', borderLeft: '1px solid rgba(148,163,184,0.16)' },
  userInfo: { textAlign: 'right' },
  userName: { margin: 0, fontSize: '13px', fontWeight: '700', color: '#0f172a' },
  userRole: { margin: 0, fontSize: '9px', color: '#0f766e', fontWeight: '800', letterSpacing: '1px' },
  logoutBtn: { backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', padding: '6px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  main: { padding: '30px', maxWidth: '1440px', margin: '0 auto' },
  notification: { position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)', zIndex: 1100, display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 24px', borderRadius: '12px', border: '1px solid', color: '#fff', fontSize: '14px', fontWeight: '600', boxShadow: '0 10px 25px rgba(0,0,0,0.2)' },
  
  // Stats row styles
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '35px' },
  statCard: { backgroundColor: 'rgba(255, 255, 255, 0.86)', padding: '20px', borderRadius: '18px', border: '1px solid rgba(148,163,184,0.16)', display: 'flex', gap: '15px', alignItems: 'center', boxShadow: '0 12px 28px rgba(15,23,42,0.05)' },
  statIconCircle: { width: '48px', height: '48px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  statLabel: { display: 'block', color: '#64748b', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px' },
  statValue: { margin: '5px 0 10px', fontSize: '22px', fontWeight: '800', color: '#0f172a' },
  progressBar: { height: '4px', width: '150px', backgroundColor: '#e2e8f0', borderRadius: '2px', overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: '2px' },

  // Grid/Map Tab Styles
  contentWrapper: { display: 'flex', flexDirection: 'column', gap: '25px' },
  toolbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.88)', padding: '15px 25px', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.16)', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' },
  filterBox: { display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#fff', border: '1px solid #cbd5e1', padding: '8px 12px', borderRadius: '8px' },
  select: { border: 'none', backgroundColor: 'transparent', color: '#0f172a', outline: 'none', fontSize: '13px', cursor: 'pointer', fontWeight: '600' },
  legend: { display: 'flex', gap: '15px' },
  legendItem: { display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontWeight: '600' },
  legendDot: { width: '8px', height: '8px', borderRadius: '50%' },
  
  // Floors list
  floorSection: { display: 'flex', flexDirection: 'column', gap: '15px' },
  floorTitle: { margin: 0, fontSize: '14px', fontWeight: '800', color: '#0f766e', textTransform: 'uppercase', letterSpacing: '1px', borderBottom: '1px dashed #cbd5e1', paddingBottom: '8px' },
  roomsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '15px' },
  
  // Room Card
  roomCard: { backgroundColor: '#fff', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.16)', padding: '18px', cursor: 'pointer', transition: 'all 0.2s', display: 'flex', flexDirection: 'column', gap: '12px', boxShadow: '0 10px 30px rgba(15,23,42,0.04)' },
  roomCardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  roomCardNumber: { margin: 0, fontSize: '20px', fontWeight: '900', color: '#0f172a' },
  statusBadge: { fontSize: '10px', fontWeight: '800', padding: '4px 8px', borderRadius: '6px', textTransform: 'uppercase' },
  roomCardType: { margin: 0, fontSize: '12px', color: '#64748b', fontWeight: '600' },
  roomCardFooter: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #e2e8f0', paddingTop: '10px', fontSize: '11px', color: '#64748b' },
  roomCardCap: { display: 'flex', alignItems: 'center', gap: '4px', fontWeight: '600' },
  roomCardPrice: { fontWeight: '700', color: '#0f172a' },

  // Arrivals & Stays log tab table
  tableHeader: { marginBottom: '10px' },
  tableScroll: { overflowX: 'auto', backgroundColor: '#fff', border: '1px solid rgba(148,163,184,0.16)', borderRadius: '18px', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' },
  table: { width: '100%', borderCollapse: 'collapse', textAlign: 'left' },
  trHead: { borderBottom: '2px solid #e2e8f0' },
  th: { padding: '16px 20px', color: '#64748b', fontSize: '12px', fontWeight: '800', textTransform: 'uppercase' },
  trRow: { borderBottom: '1px solid #e2e8f0', '&:hover': { backgroundColor: '#f8fafc' } },
  td: { padding: '16px 20px', fontSize: '13px' },
  tableName: { display: 'block', color: '#0f172a', fontSize: '14px', fontWeight: '700' },
  tableMeta: { display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#64748b', marginTop: '4px' },
  tablePill: { padding: '4px 8px', borderRadius: '6px', fontSize: '10px', fontWeight: '800' },
  code: { fontFamily: 'monospace', fontSize: '13px', color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.1)', padding: '2px 6px', borderRadius: '4px' },

  // Verification center
  checkinCenter: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '30px', padding: '30px 0' },
  searchCard: { width: '100%', maxWidth: '480px', backgroundColor: '#fff', borderRadius: '24px', padding: '35px', border: '1px solid rgba(148,163,184,0.16)', textAlign: 'center', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' },
  cardIcon: { width: '60px', height: '60px', backgroundColor: 'rgba(15, 118, 110, 0.1)', borderRadius: '15px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' },
  cardTitle: { fontSize: '22px', fontWeight: '900', margin: '0 0 8px', color: '#0f172a' },
  cardSub: { color: '#64748b', fontSize: '13px', marginBottom: '25px', fontWeight: '500' },
  form: { display: 'flex', flexDirection: 'column', gap: '15px' },
  inputWrapper: { position: 'relative' },
  searchIcon: { position: 'absolute', left: '15px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' },
  input: { width: '100%', boxSizing: 'border-box', backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '12px', padding: '15px 15px 15px 45px', color: '#0f172a', fontSize: '15px', outline: 'none' },
  submitBtn: { width: '100%', backgroundColor: '#0f766e', color: '#fff', border: 'none', borderRadius: '12px', padding: '15px', fontSize: '15px', fontWeight: '800', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', boxShadow: '0 8px 24px rgba(15,118,110,0.2)' },
  
  // Verified Info Card
  verifiedCard: { width: '100%', maxWidth: '560px', backgroundColor: '#fff', borderRadius: '24px', border: '1px solid rgba(148,163,184,0.16)', overflow: 'hidden', boxShadow: '0 12px 28px rgba(15,23,42,0.04)' },
  verifiedCardHeader: { padding: '18px 25px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  verifiedHero: { display: 'flex', gap: '20px', padding: '25px', alignItems: 'center' },
  guestIcon: { width: '56px', height: '56px', backgroundColor: '#0f766e', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  guestName: { fontSize: '24px', fontWeight: '800', margin: 0, color: '#0f172a' },
  paidBadge: { display: 'inline-block', color: '#10b981', fontSize: '11px', fontWeight: '800', backgroundColor: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '4px', marginTop: '6px' },
  pendingBadge: { display: 'inline-block', color: '#f59e0b', fontSize: '11px', fontWeight: '800', backgroundColor: 'rgba(245, 158, 11, 0.1)', padding: '2px 8px', borderRadius: '4px', marginTop: '6px' },
  detailsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', backgroundColor: '#cbd5e1' },
  detailBox: { padding: '18px 20px', backgroundColor: '#fff', display: 'flex', gap: '12px' },
  detailIcon: { color: '#64748b' },
  detailLabel: { display: 'block', color: '#64748b', fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px' },
  detailValue: { margin: 0, fontSize: '13px', fontWeight: '700', color: '#0f172a' },
  detailSub: { fontSize: '10px', color: '#0f766e', fontWeight: '600' },
  checkedInMessage: { display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontSize: '13px', fontWeight: '800', backgroundColor: 'rgba(16, 185, 129, 0.1)', padding: '8px 16px', borderRadius: '8px' },

  // Drawer / Sidebar popover
  overlay: { position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.42)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)' },
  drawer: { position: 'absolute', top: 0, right: 0, bottom: 0, width: '420px', backgroundColor: '#fff', borderLeft: '1px solid rgba(148,163,184,0.16)', display: 'flex', flexDirection: 'column', zIndex: 1010, boxShadow: '0 30px 80px rgba(15,23,42,0.18)' },
  drawerHeader: { padding: '25px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  drawerKicker: { fontSize: '10px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' },
  drawerTitle: { margin: 0, fontSize: '24px', fontWeight: '900', color: '#0f172a' },
  drawerClose: { backgroundColor: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' },
  drawerContent: { padding: '25px', display: 'flex', flexDirection: 'column', gap: '25px', overflowY: 'auto', flex: 1 },
  statusHero: { padding: '18px 20px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '5px' },
  statusHeroLabel: { fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' },
  statusHeroValue: { fontSize: '18px', fontWeight: '800' },
  infoSection: { display: 'flex', flexDirection: 'column', gap: '12px' },
  infoSectionTitle: { fontSize: '11px', fontWeight: '800', color: '#64748b', letterSpacing: '0.5px' },
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' },
  infoBox: { padding: '12px', backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '10px', display: 'flex', flexDirection: 'column', gap: '4px' },
  actionsStack: { display: 'flex', flexDirection: 'column', gap: '10px' },
  primaryActionBtn: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', backgroundColor: '#0f766e', color: '#fff', border: 'none', padding: '14px', borderRadius: '10px', fontSize: '13px', fontWeight: '800', cursor: 'pointer', boxShadow: '0 8px 24px rgba(15,118,110,0.15)' },
  secondaryActionBtn: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', backgroundColor: '#f8fafc', color: '#334155', border: '1px solid #cbd5e1', padding: '14px', borderRadius: '10px', fontSize: '13px', fontWeight: '700', cursor: 'pointer' },

  // Walkin booking modal
  modal: { width: '100%', maxWidth: '600px', backgroundColor: '#fff', borderRadius: '24px', border: '1px solid rgba(148,163,184,0.16)', overflow: 'hidden', boxShadow: '0 30px 80px rgba(15,23,42,0.18)' },
  modalHeader: { padding: '20px 25px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  badge: { display: 'flex', alignItems: 'center', gap: '5px', color: '#0f766e', fontSize: '11px', fontWeight: '800' },
  closeBtn: { backgroundColor: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' },
  bookingForm: { padding: '25px', display: 'flex', flexDirection: 'column', gap: '20px' },
  formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' },
  inputField: { display: 'flex', flexDirection: 'column', gap: '8px' },
  fieldLabel: { fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' },
  formInput: { boxSizing: 'border-box', width: '100%', backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '12px 14px', color: '#0f172a', fontSize: '13px', outline: 'none' },
  checkinSelector: { display: 'flex', gap: '12px', backgroundColor: 'rgba(15, 118, 110, 0.05)', border: '1px solid rgba(15, 118, 110, 0.15)', padding: '15px', borderRadius: '12px', alignItems: 'start' },
  checkbox: { marginTop: '4px', cursor: 'pointer' },
  checkboxLabel: { display: 'flex', flexDirection: 'column', gap: '2px', cursor: 'pointer', fontSize: '12px' },
  modalFooter: { display: 'flex', justifyContent: 'flex-end', gap: '15px', marginTop: '10px' },
  cancelLink: { backgroundColor: 'transparent', border: 'none', color: '#64748b', fontWeight: '700', cursor: 'pointer', fontSize: '13px', marginRight: '10px' },
  doneBtn: { backgroundColor: '#0f766e', color: '#fff', border: 'none', borderRadius: '10px', padding: '12px 25px', fontWeight: '800', cursor: 'pointer', fontSize: '13px', boxShadow: '0 8px 24px rgba(15,118,110,0.15)' },
  emptyCard: { padding: '40px', backgroundColor: '#fff', border: '1px dashed #cbd5e1', borderRadius: '16px', textAlign: 'center', color: '#64748b', fontSize: '13px' },
  loaderSection: { padding: '60px 0', textAlign: 'center', color: '#0f766e', display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: '600' },
  
  // Folio Panel Styles
  folioContainer: { display: 'flex', flexDirection: 'column', gap: '15px', backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '14px', padding: '15px', marginTop: '10px' },
  folioSummary: { display: 'flex', flexDirection: 'column', gap: '6px', borderBottom: '1px dashed #cbd5e1', paddingBottom: '10px' },
  folioSummaryRow: { display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#64748b', fontWeight: '600' },
  folioList: { display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', paddingRight: '5px' },
  noFolioText: { margin: 0, padding: '15px 0', textAlign: 'center', color: '#64748b', fontSize: '12px', fontWeight: '500' },
  folioItem: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', backgroundColor: '#fff', border: '1px solid rgba(148,163,184,0.16)', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' },
  folioItemDesc: { display: 'block', fontSize: '12px', fontWeight: '700', color: '#0f172a' },
  folioItemMeta: { fontSize: '10px', color: '#64748b' },
  folioItemAmt: { fontSize: '12px', fontWeight: '800', color: '#0f766e' },
  deleteChargeBtn: { background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  addFolioForm: { display: 'flex', gap: '8px', borderTop: '1px solid #cbd5e1', paddingTop: '10px' },
  addFolioInputDesc: { flex: 2, boxSizing: 'border-box', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '8px 10px', fontSize: '12px', outline: 'none', backgroundColor: '#fff', color: '#0f172a' },
  addFolioInputAmt: { flex: 1, boxSizing: 'border-box', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '8px 10px', fontSize: '12px', outline: 'none', backgroundColor: '#fff', color: '#0f172a' },
  addFolioSubmit: { border: 'none', backgroundColor: '#0f766e', color: '#fff', padding: '8px 14px', borderRadius: '8px', fontSize: '12px', fontWeight: '800', cursor: 'pointer' }
};

export default ReceptionDashboard;
