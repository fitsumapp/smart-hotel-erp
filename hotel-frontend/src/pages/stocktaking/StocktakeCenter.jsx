import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  ClipboardCheck, Plus, Search, Lock, Eye, RefreshCw,
  Clock, Play, Pause, Trash2, Calendar, AlertTriangle,
  User, CheckCircle2
} from 'lucide-react';
import { API_BASE_URL } from '../../apiConfig';

import StocktakeCountDesk from './StocktakeCountDesk';
import StocktakeVarianceDesk from './StocktakeVarianceDesk';

const API_V1 = `${API_BASE_URL}/v1`;

export default function StocktakeCenter({ userData }) {
  // Main Tab Navigation: 'sessions' | 'schedules'
  const [mainTab, setMainTab] = useState('sessions');

  // Sessions State
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Sub-desk navigation
  const [activeSession, setActiveSession] = useState(null);
  const [deskView, setDeskView] = useState('center'); // 'center' | 'count' | 'variance'

  // New Session Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [locations, setLocations] = useState([]);
  const [categories, setCategories] = useState([]);
  const [staffUsers, setStaffUsers] = useState([]);
  const [newTitle, setNewTitle] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [newCountingMode, setNewCountingMode] = useState('blind');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  // Schedules State
  const [schedules, setSchedules] = useState([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [schedName, setSchedName] = useState('');
  const [schedFrequency, setSchedFrequency] = useState('daily');
  const [schedLocation, setSchedLocation] = useState('');
  const [schedCategory, setSchedCategory] = useState('');
  const [schedMode, setSchedMode] = useState('blind');
  const [schedStaff, setSchedStaff] = useState('');
  const [schedTime, setSchedTime] = useState('06:00');
  const [schedDayOfWeek, setSchedDayOfWeek] = useState(0);
  const [schedDayOfMonth, setSchedDayOfMonth] = useState(1);
  const [schedSubmitting, setSchedSubmitting] = useState(false);
  const [schedError, setSchedError] = useState(null);
  const [schedNotification, setSchedNotification] = useState(null);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const headers = getHeaders();
      const res = await axios.get(`${API_V1}/stocktaking/sessions/`, { headers });
      const data = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setSessions(data);
    } catch (err) {
      console.error('Failed to load stocktake sessions:', err);
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  const fetchSchedules = useCallback(async () => {
    setSchedulesLoading(true);
    try {
      const headers = getHeaders();
      const res = await axios.get(`${API_V1}/stocktaking/schedules/`, { headers });
      const data = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setSchedules(data);
    } catch (err) {
      console.error('Failed to load stocktake schedules:', err);
    } finally {
      setSchedulesLoading(false);
    }
  }, [getHeaders]);

  const fetchDropdownData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [locRes, catRes, userRes] = await Promise.all([
        axios.get(`${API_V1}/locations/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_V1}/inventory-categories/`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API_BASE_URL}/users/users/`, { headers }).catch(() =>
          axios.get(`${API_V1}/users/`, { headers }).catch(() => ({ data: [] }))
        )
      ]);

      const locs = Array.isArray(locRes.data) ? locRes.data : (locRes.data?.results || []);
      const cats = Array.isArray(catRes.data) ? catRes.data : (catRes.data?.results || []);
      const users = Array.isArray(userRes.data) ? userRes.data : (userRes.data?.results || []);

      setLocations(locs.filter(l => l.is_active !== false));
      setCategories(cats);
      setStaffUsers(users);

      if (locs.length > 0) {
        if (!newLocation) setNewLocation(locs[0].id);
        if (!schedLocation) setSchedLocation(locs[0].id);
      }
    } catch (err) {
      console.error('Failed to load locations, categories, or staff:', err);
    }
  }, [getHeaders, newLocation, schedLocation]);

  useEffect(() => {
    fetchSessions();
    fetchSchedules();
    fetchDropdownData();
  }, [fetchSessions, fetchSchedules, fetchDropdownData]);

  // Handle Manual Session Creation
  const handleCreateSession = async (e) => {
    e.preventDefault();
    setCreateError(null);
    const locId = newLocation || (locations.length > 0 ? locations[0].id : null);
    if (!locId) {
      setCreateError('Please select a stock location.');
      return;
    }

    setCreating(true);
    try {
      const headers = getHeaders();
      const payload = {
        location: locId,
        category: newCategory || null,
        counting_mode: newCountingMode,
        title: newTitle.trim() || undefined
      };

      const res = await axios.post(`${API_V1}/stocktaking/sessions/`, payload, { headers });
      setCreateModalOpen(false);
      setNewTitle('');
      setNewCategory('');
      fetchSessions();
      // Open count desk directly for newly created session
      setActiveSession(res.data);
      setDeskView('count');
    } catch (err) {
      console.error('Failed to create stocktake session:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setCreateError(`Creation failed: ${detail}`);
    } finally {
      setCreating(false);
    }
  };

  // Handle Schedule Creation
  const handleCreateSchedule = async (e) => {
    e.preventDefault();
    setSchedError(null);
    setSchedNotification(null);

    if (!schedName.trim()) {
      setSchedError('Please enter a descriptive schedule name.');
      return;
    }
    const locId = schedLocation || (locations.length > 0 ? locations[0].id : null);
    if (!locId) {
      setSchedError('Please select a storage location.');
      return;
    }

    setSchedSubmitting(true);
    try {
      const headers = getHeaders();
      const payload = {
        name: schedName.trim(),
        frequency: schedFrequency,
        location: locId,
        category: schedCategory || null,
        counting_mode: schedMode,
        assigned_staff: schedStaff || null,
        scheduled_time: schedTime ? (schedTime.length === 5 ? `${schedTime}:00` : schedTime) : '06:00:00',
        day_of_week: schedFrequency === 'weekly' ? Number(schedDayOfWeek) : null,
        day_of_month: schedFrequency === 'monthly' ? Number(schedDayOfMonth) : null,
        is_active: true
      };

      await axios.post(`${API_V1}/stocktaking/schedules/`, payload, { headers });
      setScheduleModalOpen(false);
      setSchedName('');
      setSchedCategory('');
      setSchedStaff('');
      setSchedNotification({ type: 'success', message: 'Automated stocktake schedule created successfully.' });
      fetchSchedules();
    } catch (err) {
      console.error('Failed to create stocktake schedule:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || JSON.stringify(err.response?.data) || err.message;
      setSchedError(`Schedule creation failed: ${detail}`);
    } finally {
      setSchedSubmitting(false);
    }
  };

  // Trigger Schedule Immediately
  const handleTriggerScheduleNow = async (scheduleId, scheduleName) => {
    setSchedError(null);
    try {
      const headers = getHeaders();
      const res = await axios.post(`${API_V1}/stocktaking/schedules/${scheduleId}/trigger-now/`, {}, { headers });
      const sessNum = res.data?.session_number || res.data?.session_id || 'newly created';
      setSchedNotification({
        type: 'success',
        message: `Execution complete for "${scheduleName}". Draft Stocktake Session #${sessNum} has been snapshot and is ready for count submission.`
      });
      fetchSchedules();
      fetchSessions();
    } catch (err) {
      console.error('Failed to trigger schedule:', err);
      const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
      setSchedNotification({ type: 'error', message: `Trigger failed: ${detail}` });
    }
  };

  // Toggle Schedule Pause / Activate
  const handleToggleSchedulePause = async (schedule) => {
    try {
      const headers = getHeaders();
      const action = schedule.is_active ? 'pause' : 'activate';
      await axios.post(`${API_V1}/stocktaking/schedules/${schedule.id}/${action}/`, {}, { headers });
      fetchSchedules();
    } catch (err) {
      console.error('Failed to toggle schedule status:', err);
    }
  };

  // Delete Schedule
  const handleDeleteSchedule = async (scheduleId, scheduleName) => {
    if (!window.confirm(`Are you sure you want to delete recurring schedule "${scheduleName}"? Any previously generated stocktake sessions will remain preserved in historical records.`)) {
      return;
    }
    try {
      const headers = getHeaders();
      await axios.delete(`${API_V1}/stocktaking/schedules/${scheduleId}/`, { headers });
      setSchedNotification({ type: 'success', message: `Schedule "${scheduleName}" removed.` });
      fetchSchedules();
    } catch (err) {
      console.error('Failed to delete schedule:', err);
      setSchedNotification({ type: 'error', message: `Delete failed: ${err.message}` });
    }
  };

  // KPIs for Sessions
  const activeCount = sessions.filter(s => s.status === 'draft' || s.status === 'in_progress').length;
  const underReviewCount = sessions.filter(s => s.status === 'under_review').length;
  const recountCount = sessions.filter(s => s.status === 'recount_required').length;
  const approvedCount = sessions.filter(s => s.status === 'approved').length;
  const totalVarianceVal = sessions.reduce((acc, s) => acc + Number(s.total_variance_value || 0), 0);

  // KPIs for Schedules
  const activeSchedCount = schedules.filter(s => s.is_active).length;
  const dailySchedCount = schedules.filter(s => s.frequency === 'daily').length;
  const weeklySchedCount = schedules.filter(s => s.frequency === 'weekly').length;
  const monthlySchedCount = schedules.filter(s => s.frequency === 'monthly').length;
  const overdueSchedCount = schedules.filter(s => s.is_overdue).length;

  // Filtered Sessions
  const filteredSessions = sessions.filter(s => {
    if (filterStatus !== 'all' && s.status !== filterStatus) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchNum = s.session_number?.toLowerCase().includes(q);
      const matchTitle = s.title?.toLowerCase().includes(q);
      const matchLoc = s.location_name?.toLowerCase().includes(q);
      if (!matchNum && !matchTitle && !matchLoc) return false;
    }
    return true;
  });

  // Render Sub-Desk if active
  if (deskView === 'count' && activeSession) {
    return (
      <StocktakeCountDesk
        session={activeSession}
        onBack={() => {
          setDeskView('center');
          setActiveSession(null);
          fetchSessions();
        }}
        onSessionUpdated={(updated) => {
          setActiveSession(updated);
          fetchSessions();
        }}
        userData={userData}
      />
    );
  }

  if (deskView === 'variance' && activeSession) {
    return (
      <StocktakeVarianceDesk
        session={activeSession}
        onBack={() => {
          setDeskView('center');
          setActiveSession(null);
          fetchSessions();
        }}
        onSessionUpdated={(updated) => {
          setActiveSession(updated);
          fetchSessions();
        }}
        userData={userData}
      />
    );
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '900', color: '#0f172a', margin: '0 0 6px 0', letterSpacing: '-0.5px' }}>
            Physical Stocktaking & Inventory Reconciliation
          </h1>
          <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
            Dual-mode physical counting (Blind & Visible), automated recurring schedules (Daily, Weekly, Monthly), and general ledger integration.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            type="button"
            onClick={() => {
              fetchSessions();
              fetchSchedules();
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: '10px',
              padding: '10px 16px',
              fontSize: '13px',
              fontWeight: '700',
              color: '#475569',
              cursor: 'pointer'
            }}
          >
            <RefreshCw size={15} /> Refresh
          </button>

          {mainTab === 'sessions' ? (
            <button
              type="button"
              id="btn-create-stocktake-session"
              onClick={() => setCreateModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#0f766e',
                border: 'none',
                borderRadius: '10px',
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '800',
                color: '#ffffff',
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(15,118,110,0.2)'
              }}
            >
              <Plus size={16} /> New Stocktake Session
            </button>
          ) : (
            <button
              type="button"
              id="btn-create-stocktake-schedule"
              onClick={() => setScheduleModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#0f766e',
                border: 'none',
                borderRadius: '10px',
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '800',
                color: '#ffffff',
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(15,118,110,0.2)'
              }}
            >
              <Calendar size={16} /> + New Recurring Schedule
            </button>
          )}
        </div>
      </div>

      {/* Main Tab Switcher */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
        <button
          type="button"
          id="tab-stocktake-sessions"
          onClick={() => setMainTab('sessions')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 22px',
            border: 'none',
            borderBottom: mainTab === 'sessions' ? '3px solid #0f766e' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: mainTab === 'sessions' ? '#0f766e' : '#64748b',
            fontSize: '14px',
            fontWeight: '800',
            cursor: 'pointer',
            marginBottom: '-2px'
          }}
        >
          <ClipboardCheck size={18} />
          Count Sessions & History
          <span style={{
            backgroundColor: mainTab === 'sessions' ? '#ccfbf1' : '#f1f5f9',
            color: mainTab === 'sessions' ? '#0f766e' : '#475569',
            borderRadius: '12px',
            padding: '2px 8px',
            fontSize: '11px',
            fontWeight: '800'
          }}>
            {sessions.length}
          </span>
        </button>

        <button
          type="button"
          id="tab-stocktake-schedules"
          onClick={() => {
            setMainTab('schedules');
            fetchSchedules();
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 22px',
            border: 'none',
            borderBottom: mainTab === 'schedules' ? '3px solid #0f766e' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: mainTab === 'schedules' ? '#0f766e' : '#64748b',
            fontSize: '14px',
            fontWeight: '800',
            cursor: 'pointer',
            marginBottom: '-2px'
          }}
        >
          <Clock size={18} />
          Recurring Schedules & Automation
          <span style={{
            backgroundColor: mainTab === 'schedules' ? '#ccfbf1' : '#f1f5f9',
            color: mainTab === 'schedules' ? '#0f766e' : '#475569',
            borderRadius: '12px',
            padding: '2px 8px',
            fontSize: '11px',
            fontWeight: '800'
          }}>
            {schedules.length}
          </span>
        </button>
      </div>

      {/* Global Notifications for Schedules */}
      {schedNotification && (
        <div style={{
          backgroundColor: schedNotification.type === 'error' ? '#fef2f2' : '#f0fdf4',
          border: `1px solid ${schedNotification.type === 'error' ? '#fca5a5' : '#86efac'}`,
          borderRadius: '12px',
          padding: '14px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          color: schedNotification.type === 'error' ? '#991b1b' : '#166534',
          fontSize: '13px',
          fontWeight: '600'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {schedNotification.type === 'error' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
            <span>{schedNotification.message}</span>
          </div>
          <button
            onClick={() => setSchedNotification(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: '800' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW A: STOCKTAKE SESSIONS & HISTORY                                      */}
      {/* ========================================================================= */}
      {mainTab === 'sessions' && (
        <>
          {/* KPI Stats Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Active In-Progress</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: '#0f172a', margin: '4px 0' }}>{activeCount}</div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Awaiting initial count submission</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Pending Review</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: underReviewCount > 0 ? '#b45309' : '#0f172a', margin: '4px 0' }}>
                {underReviewCount}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Counts submitted; awaiting sign-off</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Recounts Required</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: recountCount > 0 ? '#dc2626' : '#0f172a', margin: '4px 0' }}>
                {recountCount}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Flagged for high discrepancy</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Approved & Closed</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: '#16a34a', margin: '4px 0' }}>{approvedCount}</div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Adjusted & posted to GL</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Cumulative Net Variance</div>
              <div style={{
                fontSize: '20px',
                fontWeight: '900',
                color: totalVarianceVal < 0 ? '#dc2626' : (totalVarianceVal > 0 ? '#16a34a' : '#0f172a'),
                margin: '4px 0'
              }}>
                {totalVarianceVal > 0 ? '+' : ''}ETB {totalVarianceVal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Across all stocktakes</div>
            </div>
          </div>

          {/* Filter and Search Bar */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '16px 20px',
            border: '1px solid #e2e8f0',
            marginBottom: '20px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '14px'
          }}>
            {/* Filter Pills */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'All Sessions' },
                { id: 'draft', label: 'In Progress' },
                { id: 'under_review', label: 'Under Review' },
                { id: 'recount_required', label: 'Recount Required' },
                { id: 'approved', label: 'Approved' },
                { id: 'cancelled', label: 'Cancelled' }
              ].map(f => (
                <button
                  key={f.id}
                  onClick={() => setFilterStatus(f.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '20px',
                    border: filterStatus === f.id ? '1px solid #0f766e' : '1px solid #e2e8f0',
                    backgroundColor: filterStatus === f.id ? '#0f766e' : '#f8fafc',
                    color: filterStatus === f.id ? '#ffffff' : '#475569',
                    fontSize: '12px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Search input */}
            <div style={{ display: 'flex', alignItems: 'center', backgroundColor: '#f1f5f9', borderRadius: '10px', padding: '6px 12px', width: '280px' }}>
              <Search size={16} color="#64748b" />
              <input
                type="text"
                placeholder="Search session #, location..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ border: 'none', backgroundColor: 'transparent', outline: 'none', marginLeft: '8px', fontSize: '13px', width: '100%' }}
              />
            </div>
          </div>

          {/* Sessions List Table */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            overflow: 'hidden',
            boxShadow: '0 4px 12px rgba(15,23,42,0.03)'
          }}>
            {loading ? (
              <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                Loading physical stocktake sessions...
              </div>
            ) : filteredSessions.length === 0 ? (
              <div style={{ padding: '60px', textAlign: 'center' }}>
                <ClipboardCheck size={40} color="#94a3b8" style={{ marginBottom: '12px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: '800', color: '#1e293b', margin: '0 0 6px 0' }}>
                  No Stocktake Sessions Found
                </h3>
                <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 16px 0' }}>
                  {searchQuery || filterStatus !== 'all' ? 'Try adjusting your search filters.' : 'Initialize a new physical stocktake session to verify warehouse balances.'}
                </p>
                <button
                  onClick={() => setCreateModalOpen(true)}
                  style={{
                    backgroundColor: '#0f766e',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '8px 18px',
                    fontSize: '13px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  New Stocktake Session
                </button>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: '700' }}>
                    <th style={{ padding: '14px 18px' }}>Session #</th>
                    <th style={{ padding: '14px 18px' }}>Title & Scope</th>
                    <th style={{ padding: '14px 18px' }}>Origin</th>
                    <th style={{ padding: '14px 18px' }}>Location</th>
                    <th style={{ padding: '14px 18px' }}>Mode</th>
                    <th style={{ padding: '14px 18px' }}>Status</th>
                    <th style={{ padding: '14px 18px', textAlign: 'right' }}>Theoretical Val</th>
                    <th style={{ padding: '14px 18px', textAlign: 'right' }}>Variance Val</th>
                    <th style={{ padding: '14px 18px', textAlign: 'center' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSessions.map((s, idx) => {
                    const isBlind = s.counting_mode === 'blind';
                    const varVal = Number(s.total_variance_value || 0);

                    return (
                      <tr key={s.id} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f8fafc' }}>
                        <td style={{ padding: '14px 18px', fontWeight: '800', color: '#0f172a' }}>
                          {s.session_number}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ fontWeight: '700', color: '#1e293b' }}>{s.title}</div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>
                            {s.category_name ? `Category: ${s.category_name}` : 'All Categories'} • {s.items?.length || 0} items
                          </div>
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          {s.schedule ? (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: '700',
                              backgroundColor: '#f3e8ff',
                              color: '#7e22ce'
                            }}>
                              <Clock size={11} /> Auto: {s.schedule_name || 'Scheduled'}
                            </span>
                          ) : (
                            <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>
                              Manual
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px', color: '#334155', fontWeight: '600' }}>
                          {s.location_name}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: '700',
                            backgroundColor: isBlind ? '#eff6ff' : '#f0fdf4',
                            color: isBlind ? '#1d4ed8' : '#15803d'
                          }}>
                            {isBlind ? <Lock size={12} /> : <Eye size={12} />}
                            {isBlind ? 'Blind' : 'Visible'}
                          </span>
                          {s.is_mode_locked && (
                            <div style={{ fontSize: '10px', color: '#64748b', fontWeight: '600', marginTop: '2px' }}>
                              Locked (D-4)
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <StatusBadge status={s.status} />
                        </td>
                        <td style={{ padding: '14px 18px', textAlign: 'right', fontWeight: '600', color: '#334155' }}>
                          ETB {Number(s.total_theoretical_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '14px 18px', textAlign: 'right', fontWeight: '800' }}>
                          <span style={{
                            color: varVal < 0 ? '#dc2626' : (varVal > 0 ? '#16a34a' : '#64748b')
                          }}>
                            {varVal > 0 ? '+' : ''}ETB {varVal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </td>
                        <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
                            {(s.status === 'draft' || s.status === 'in_progress' || s.status === 'recount_required') && (
                              <button
                                type="button"
                                onClick={() => {
                                  setActiveSession(s);
                                  setDeskView('count');
                                }}
                                style={{
                                  backgroundColor: '#0f766e',
                                  color: '#ffffff',
                                  border: 'none',
                                  borderRadius: '6px',
                                  padding: '6px 12px',
                                  fontSize: '12px',
                                  fontWeight: '700',
                                  cursor: 'pointer'
                                }}
                              >
                                {s.status === 'recount_required' ? 'Recount' : 'Count'}
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => {
                                setActiveSession(s);
                                setDeskView('variance');
                              }}
                              style={{
                                backgroundColor: '#ffffff',
                                color: '#334155',
                                border: '1px solid #cbd5e1',
                                borderRadius: '6px',
                                padding: '6px 12px',
                                fontSize: '12px',
                                fontWeight: '700',
                                cursor: 'pointer'
                              }}
                            >
                              {s.status === 'under_review' ? 'Review & Approve' : 'Details'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* VIEW B: RECURRING SCHEDULES & AUTOMATION                                  */}
      {/* ========================================================================= */}
      {mainTab === 'schedules' && (
        <>
          {/* Schedules KPI Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Active Schedules</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: '#0f766e', margin: '4px 0' }}>{activeSchedCount}</div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Automated recurring jobs active</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Daily Cadence</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: '#0284c7', margin: '4px 0' }}>{dailySchedCount}</div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Everyday scheduled snapshots</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Weekly & Monthly</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: '#7e22ce', margin: '4px 0' }}>
                {weeklySchedCount + monthlySchedCount}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>{weeklySchedCount} weekly • {monthlySchedCount} monthly</div>
            </div>

            <div style={kpiCardStyle}>
              <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase' }}>Overdue Status</div>
              <div style={{ fontSize: '22px', fontWeight: '900', color: overdueSchedCount > 0 ? '#dc2626' : '#16a34a', margin: '4px 0' }}>
                {overdueSchedCount}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>
                {overdueSchedCount > 0 ? 'Schedules requiring catch-up execution' : 'All schedules on time'}
              </div>
            </div>
          </div>

          {/* Schedules Table */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            overflow: 'hidden',
            boxShadow: '0 4px 12px rgba(15,23,42,0.03)'
          }}>
            {schedulesLoading ? (
              <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                Loading automated stocktake schedules...
              </div>
            ) : schedules.length === 0 ? (
              <div style={{ padding: '60px', textAlign: 'center' }}>
                <Clock size={40} color="#94a3b8" style={{ marginBottom: '12px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: '800', color: '#1e293b', margin: '0 0 6px 0' }}>
                  No Automated Stocktaking Schedules Configured
                </h3>
                <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 16px 0' }}>
                  Set up recurring daily, weekly, or monthly stocktakes to automatically generate theoretical snapshots and notify assigned counters.
                </p>
                <button
                  onClick={() => setScheduleModalOpen(true)}
                  style={{
                    backgroundColor: '#0f766e',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '8px 18px',
                    fontSize: '13px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  Create Schedule Now
                </button>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: '700' }}>
                    <th style={{ padding: '14px 18px' }}>Schedule Name & Scope</th>
                    <th style={{ padding: '14px 18px' }}>Cadence</th>
                    <th style={{ padding: '14px 18px' }}>Location</th>
                    <th style={{ padding: '14px 18px' }}>Protocol</th>
                    <th style={{ padding: '14px 18px' }}>Designated Counter</th>
                    <th style={{ padding: '14px 18px' }}>Last Run</th>
                    <th style={{ padding: '14px 18px' }}>Next Scheduled</th>
                    <th style={{ padding: '14px 18px' }}>Status</th>
                    <th style={{ padding: '14px 18px', textAlign: 'center' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((sc, idx) => {
                    const isBlind = sc.counting_mode === 'blind';
                    const daysOfWeekMap = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

                    let timingLabel = `At ${sc.scheduled_time || '06:00'}`;
                    if (sc.frequency === 'weekly' && sc.day_of_week !== null && sc.day_of_week !== undefined) {
                      timingLabel = `Every ${daysOfWeekMap[sc.day_of_week] || ''} at ${sc.scheduled_time}`;
                    } else if (sc.frequency === 'monthly' && sc.day_of_month) {
                      timingLabel = `Day ${sc.day_of_month} of month at ${sc.scheduled_time}`;
                    }

                    return (
                      <tr key={sc.id} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f8fafc' }}>
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ fontWeight: '800', color: '#0f172a' }}>{sc.name}</div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>
                            {sc.category_name ? `Category: ${sc.category_name}` : 'All Categories (Full Location)'}
                          </div>
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: '800',
                            backgroundColor: sc.frequency === 'daily' ? '#eff6ff' : (sc.frequency === 'weekly' ? '#f0fdf4' : '#faf5ff'),
                            color: sc.frequency === 'daily' ? '#1d4ed8' : (sc.frequency === 'weekly' ? '#15803d' : '#7e22ce')
                          }}>
                            {sc.frequency_display || sc.frequency.toUpperCase()}
                          </span>
                          <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                            {timingLabel}
                          </div>
                        </td>
                        <td style={{ padding: '14px 18px', fontWeight: '600', color: '#334155' }}>
                          {sc.location_name}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: '700',
                            backgroundColor: isBlind ? '#eff6ff' : '#f0fdf4',
                            color: isBlind ? '#1d4ed8' : '#15803d'
                          }}>
                            {isBlind ? <Lock size={12} /> : <Eye size={12} />}
                            {isBlind ? 'Blind' : 'Visible'}
                          </span>
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          {sc.assigned_staff_name ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <User size={13} color="#0f766e" />
                              <span style={{ fontWeight: '700', color: '#0f172a' }}>{sc.assigned_staff_name}</span>
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '12px' }}>Unassigned (Open)</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          {sc.last_run_at ? (
                            <div>
                              <div style={{ fontWeight: '600', color: '#1e293b' }}>
                                {new Date(sc.last_run_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                              </div>
                              <span style={{
                                display: 'inline-block',
                                fontSize: '10px',
                                fontWeight: '800',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: sc.last_run_status === 'success' ? '#dcfce7' : (sc.last_run_status === 'failed' ? '#fee2e2' : '#f1f5f9'),
                                color: sc.last_run_status === 'success' ? '#166534' : (sc.last_run_status === 'failed' ? '#991b1b' : '#475569')
                              }}>
                                {sc.last_run_status.toUpperCase()}
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '11px' }}>Never executed</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          {sc.next_run_at ? (
                            <div>
                              <div style={{ fontWeight: '700', color: sc.is_overdue ? '#dc2626' : '#1e293b' }}>
                                {new Date(sc.next_run_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                              </div>
                              {sc.is_overdue && (
                                <span style={{
                                  display: 'inline-block',
                                  fontSize: '10px',
                                  fontWeight: '800',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor: '#fee2e2',
                                  color: '#991b1b',
                                  marginTop: '2px'
                                }}>
                                  OVERDUE
                                </span>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: '800',
                            backgroundColor: sc.is_active ? '#ecfdf5' : '#f1f5f9',
                            color: sc.is_active ? '#047857' : '#64748b'
                          }}>
                            {sc.is_active ? 'Active' : 'Paused'}
                          </span>
                        </td>
                        <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                          <div style={{ display: 'flex', justifyContent: 'center', gap: '6px' }}>
                            <button
                              type="button"
                              title="Trigger immediate snapshot now"
                              onClick={() => handleTriggerScheduleNow(sc.id, sc.name)}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                backgroundColor: '#0f766e',
                                color: '#ffffff',
                                border: 'none',
                                borderRadius: '6px',
                                padding: '6px 10px',
                                fontSize: '12px',
                                fontWeight: '700',
                                cursor: 'pointer'
                              }}
                            >
                              <Play size={12} fill="#ffffff" /> Run Now
                            </button>

                            <button
                              type="button"
                              title={sc.is_active ? 'Pause recurring trigger' : 'Activate schedule'}
                              onClick={() => handleToggleSchedulePause(sc)}
                              style={{
                                backgroundColor: '#ffffff',
                                color: sc.is_active ? '#b45309' : '#16a34a',
                                border: '1px solid #cbd5e1',
                                borderRadius: '6px',
                                padding: '6px 10px',
                                fontSize: '12px',
                                fontWeight: '700',
                                cursor: 'pointer'
                              }}
                            >
                              {sc.is_active ? <Pause size={13} /> : <Play size={13} />}
                            </button>

                            <button
                              type="button"
                              title="Delete schedule"
                              onClick={() => handleDeleteSchedule(sc.id, sc.name)}
                              style={{
                                backgroundColor: '#ffffff',
                                color: '#dc2626',
                                border: '1px solid #fee2e2',
                                borderRadius: '6px',
                                padding: '6px 8px',
                                fontSize: '12px',
                                cursor: 'pointer'
                              }}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* MODAL: Create New Stocktake Session (Manual)                              */}
      {/* ========================================================================= */}
      {createModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15,23,42,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '28px',
            maxWidth: '560px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 8px 0', color: '#0f172a' }}>
              Initialize Physical Stocktake Session
            </h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '20px' }}>
              Creates an authoritative snapshot of theoretical stock balances for the chosen location.
            </p>

            {createError && (
              <div style={{
                backgroundColor: '#fef2f2',
                border: '1px solid #fca5a5',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#b91c1c',
                fontSize: '12px',
                marginBottom: '16px'
              }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSession}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                  Session Title (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Month-End Main Warehouse Count"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={inputStyle}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Storage Location *
                  </label>
                  <select
                    value={newLocation}
                    onChange={(e) => setNewLocation(e.target.value)}
                    required
                    style={inputStyle}
                  >
                    {locations.map(loc => (
                      <option key={loc.id} value={loc.id}>
                        {loc.name} ({loc.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Category Filter (Optional)
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="">All Categories (Full Location)</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Counting Mode Selection Cards */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '8px', color: '#334155' }}>
                  Physical Counting Protocol *
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div
                    onClick={() => setNewCountingMode('blind')}
                    style={{
                      border: `2px solid ${newCountingMode === 'blind' ? '#0f766e' : '#e2e8f0'}`,
                      backgroundColor: newCountingMode === 'blind' ? '#f0fdfa' : '#ffffff',
                      borderRadius: '10px',
                      padding: '14px',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <Lock size={16} color="#0f766e" />
                      <strong style={{ fontSize: '13px', color: '#0f172a' }}>Blind Count (Recommended)</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: '11px', color: '#64748b', lineHeight: '1.4' }}>
                      Theoretical stock is completely hidden from counters to prevent confirmation bias.
                    </p>
                  </div>

                  <div
                    onClick={() => setNewCountingMode('visible')}
                    style={{
                      border: `2px solid ${newCountingMode === 'visible' ? '#0f766e' : '#e2e8f0'}`,
                      backgroundColor: newCountingMode === 'visible' ? '#f0fdfa' : '#ffffff',
                      borderRadius: '10px',
                      padding: '14px',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <Eye size={16} color="#0284c7" />
                      <strong style={{ fontSize: '13px', color: '#0f172a' }}>Visible Count</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: '11px', color: '#64748b', lineHeight: '1.4' }}>
                      Theoretical stock quantities are displayed to counters during physical tallying.
                    </p>
                  </div>
                </div>

                <div style={{
                  marginTop: '10px',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '11px',
                  color: '#475569'
                }}>
                  🔒 <strong>Owner Decision D-4:</strong> Selected counting mode is permanently locked once counts are submitted.
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    backgroundColor: '#f8fafc',
                    fontSize: '13px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: '#0f766e',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: '800',
                    cursor: creating ? 'not-allowed' : 'pointer'
                  }}
                >
                  {creating ? 'Snapshotting...' : 'Create & Snapshot Balances'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: Create New Stocktake Schedule (Automation)                         */}
      {/* ========================================================================= */}
      {scheduleModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15,23,42,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            padding: '28px',
            maxWidth: '620px',
            width: '92%',
            maxHeight: '90vh',
            overflowY: 'auto',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 6px 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={20} color="#0f766e" /> Configure Recurring Stocktake Schedule
            </h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '20px' }}>
              Automates theoretical stock snapshot creation at recurring intervals (Africa/Addis_Ababa timezone). Sessions are automatically created in Draft mode.
            </p>

            {schedError && (
              <div style={{
                backgroundColor: '#fef2f2',
                border: '1px solid #fca5a5',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#b91c1c',
                fontSize: '12px',
                marginBottom: '16px'
              }}>
                {schedError}
              </div>
            )}

            <form onSubmit={handleCreateSchedule}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                  Schedule Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Daily Nightly Central Store Count"
                  value={schedName}
                  onChange={(e) => setSchedName(e.target.value)}
                  required
                  style={inputStyle}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Recurrence Cadence *
                  </label>
                  <select
                    value={schedFrequency}
                    onChange={(e) => setSchedFrequency(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="daily">Daily (Everyday)</option>
                    <option value="weekly">Weekly (Specific Day)</option>
                    <option value="monthly">Monthly (Day of Month)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Execution Time (Local HH:MM) *
                  </label>
                  <input
                    type="time"
                    value={schedTime}
                    onChange={(e) => setSchedTime(e.target.value)}
                    required
                    style={inputStyle}
                  />
                </div>
              </div>

              {schedFrequency === 'weekly' && (
                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Day of the Week *
                  </label>
                  <select
                    value={schedDayOfWeek}
                    onChange={(e) => setSchedDayOfWeek(e.target.value)}
                    style={inputStyle}
                  >
                    <option value={0}>Monday</option>
                    <option value={1}>Tuesday</option>
                    <option value={2}>Wednesday</option>
                    <option value={3}>Thursday</option>
                    <option value={4}>Friday</option>
                    <option value={5}>Saturday</option>
                    <option value={6}>Sunday</option>
                  </select>
                </div>
              )}

              {schedFrequency === 'monthly' && (
                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Day of the Month (1..31) *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="31"
                    value={schedDayOfMonth}
                    onChange={(e) => setSchedDayOfMonth(e.target.value)}
                    style={inputStyle}
                  />
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Storage Location *
                  </label>
                  <select
                    value={schedLocation}
                    onChange={(e) => setSchedLocation(e.target.value)}
                    required
                    style={inputStyle}
                  >
                    {locations.map(loc => (
                      <option key={loc.id} value={loc.id}>
                        {loc.name} ({loc.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                    Category Filter (Optional)
                  </label>
                  <select
                    value={schedCategory}
                    onChange={(e) => setSchedCategory(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="">All Categories (Full Location)</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '6px', color: '#334155' }}>
                  Designated Counter / Assigned Staff (Optional)
                </label>
                <select
                  value={schedStaff}
                  onChange={(e) => setSchedStaff(e.target.value)}
                  style={inputStyle}
                >
                  <option value="">-- No Designated Counter (Open Assignment) --</option>
                  {staffUsers.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.username} ({u.role || 'Staff'})
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                  The designated counter will receive in-app notifications and be set as the counter when counting starts.
                </div>
              </div>

              {/* Counting Protocol */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', marginBottom: '8px', color: '#334155' }}>
                  Counting Protocol *
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div
                    onClick={() => setSchedMode('blind')}
                    style={{
                      border: `2px solid ${schedMode === 'blind' ? '#0f766e' : '#e2e8f0'}`,
                      backgroundColor: schedMode === 'blind' ? '#f0fdfa' : '#ffffff',
                      borderRadius: '10px',
                      padding: '12px',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <Lock size={15} color="#0f766e" />
                      <strong style={{ fontSize: '12px', color: '#0f172a' }}>Blind Count (Zero-Leak)</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>
                      Theoretical stock masked from counters.
                    </p>
                  </div>

                  <div
                    onClick={() => setSchedMode('visible')}
                    style={{
                      border: `2px solid ${schedMode === 'visible' ? '#0f766e' : '#e2e8f0'}`,
                      backgroundColor: schedMode === 'visible' ? '#f0fdfa' : '#ffffff',
                      borderRadius: '10px',
                      padding: '12px',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <Eye size={15} color="#0284c7" />
                      <strong style={{ fontSize: '12px', color: '#0f172a' }}>Visible Count</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>
                      Theoretical quantities visible during tallying.
                    </p>
                  </div>
                </div>
              </div>

              {/* Safeguard Notice */}
              <div style={{
                backgroundColor: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '11px',
                color: '#1e40af',
                marginBottom: '20px'
              }}>
                🛡️ <strong>Governance Safeguard:</strong> Automated scheduler execution creates snapshot draft sessions only. It NEVER automatically records physical counts, approves variances, or posts General Ledger journal entries. Strict Segregation of Duties remains enforced.
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setScheduleModalOpen(false)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    backgroundColor: '#f8fafc',
                    fontSize: '13px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={schedSubmitting}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: '#0f766e',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: '800',
                    cursor: schedSubmitting ? 'not-allowed' : 'pointer'
                  }}
                >
                  {schedSubmitting ? 'Saving Schedule...' : 'Save & Activate Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    draft: { label: 'In Progress', bg: '#f1f5f9', color: '#475569' },
    in_progress: { label: 'Counting Active', bg: '#eff6ff', color: '#1d4ed8' },
    under_review: { label: 'Under Review', bg: '#fffbeb', color: '#b45309' },
    recount_required: { label: 'Recount Required', bg: '#fef2f2', color: '#b91c1c' },
    approved: { label: 'Approved & Closed', bg: '#f0fdf4', color: '#15803d' },
    cancelled: { label: 'Cancelled', bg: '#f8fafc', color: '#94a3b8' }
  };

  const style = map[status] || { label: status, bg: '#f1f5f9', color: '#475569' };

  return (
    <span style={{
      display: 'inline-block',
      padding: '4px 10px',
      borderRadius: '12px',
      fontSize: '11px',
      fontWeight: '800',
      backgroundColor: style.bg,
      color: style.color
    }}>
      {style.label}
    </span>
  );
}

const kpiCardStyle = {
  backgroundColor: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '14px',
  padding: '18px',
  boxShadow: '0 2px 8px rgba(15,23,42,0.02)'
};

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '8px',
  border: '1px solid #cbd5e1',
  fontSize: '13px',
  outline: 'none',
  backgroundColor: '#ffffff'
};
