import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import {
  Sparkles, CheckCircle2, AlertCircle, Clock, CheckSquare,
  Wine, Package, ShieldAlert, Search, RefreshCw, UserCheck,
  Plus, Eye, X, AlertTriangle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;
const TASKS_API = `${API_BASE}housekeeping/tasks/`;
const TASK_INSPECT_API = (id) => `${API_BASE}housekeeping/tasks/${id}/inspect/`;
const MINIBAR_ITEMS_API = `${API_BASE}minibar/items/`;
const MINIBAR_CANDIDATES_API = `${API_BASE}minibar/candidates/`;
const MINIBAR_CONSUME_API = `${API_BASE}minibar/consume/`;
const LOST_FOUND_API = `${API_BASE}lost-and-found/`;
const LOST_FOUND_CLAIM_API = (id) => `${API_BASE}lost-and-found/${id}/claim/`;
const ROOMS_API = `${API_BASE}rooms/`;
const OCCUPIED_ROOMS_API = `${API_BASE}occupied-rooms/`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export default function HousekeepingManager({ userData }) {
  const [activeTab, setActiveTab] = useState('tasks'); // 'tasks' | 'minibar' | 'lost_found'

  // Data states
  const [tasks, setTasks] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [occupiedRooms, setOccupiedRooms] = useState([]);
  const [minibarItems, setMinibarItems] = useState([]);
  const [inventoryCandidates, setInventoryCandidates] = useState([]);
  const [lostFoundItems, setLostFoundItems] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters & Search
  const [taskFilter, setTaskFilter] = useState('all'); // all, pending, in_progress, cleaned, inspected, urgent
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [isNewTaskModalOpen, setIsNewTaskModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [isChecklistModalOpen, setIsChecklistModalOpen] = useState(false);
  const [isInspectModalOpen, setIsInspectModalOpen] = useState(false);
  const [isNewLostFoundModalOpen, setIsNewLostFoundModalOpen] = useState(false);
  const [selectedLostItem, setSelectedLostItem] = useState(null);
  const [isClaimModalOpen, setIsClaimModalOpen] = useState(false);
  const [isAddMinibarItemModalOpen, setIsAddMinibarItemModalOpen] = useState(false);

  // Minibar consumption draft
  const [selectedMinibarRoom, setSelectedMinibarRoom] = useState('');
  const [consumedQuantities, setConsumedQuantities] = useState({}); // { itemId: quantity }
  const [minibarNotes, setMinibarNotes] = useState('');
  const [minibarPosting, setMinibarPosting] = useState(false);
  const [postingSuccess, setPostingSuccess] = useState(null);

  // New task form state
  const [newTaskRoom, setNewTaskRoom] = useState('');
  const [newTaskType, setNewTaskType] = useState('stayover_cleaning');
  const [newTaskPriority, setNewTaskPriority] = useState('normal');
  const [newTaskAssignee, setNewTaskAssignee] = useState('');
  const [newTaskNotes, setNewTaskNotes] = useState('');

  // Inspection form state
  const [inspectApproval, setInspectApproval] = useState(true);
  const [inspectNotes, setInspectNotes] = useState('');

  // Lost & Found form state
  const [newLostName, setNewLostName] = useState('');
  const [newLostRoom, setNewLostRoom] = useState('');
  const [newLostLocation, setNewLostLocation] = useState('');
  const [newLostGuest, setNewLostGuest] = useState('');
  const [newLostStorage, setNewLostStorage] = useState('Locker Shelf A');
  const [newLostDesc, setNewLostDesc] = useState('');

  // Claim form state
  const [claimantName, setClaimantName] = useState('');
  const [claimantPhone, setClaimantPhone] = useState('');
  const [claimNotes, setClaimNotes] = useState('');

  // Add minibar catalog item form state
  const [catalogInvId, setCatalogInvId] = useState('');
  const [catalogStandardQty, setCatalogStandardQty] = useState(2);
  const [catalogPrice, setCatalogPrice] = useState('');

  // Toast / notification
  const [alertMsg, setAlertMsg] = useState(null);

  const showAlert = (message, type = 'success') => {
    setAlertMsg({ message, type });
    setTimeout(() => setAlertMsg(null), 4000);
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers = getAuthHeaders();
      const [
        tasksRes,
        roomsRes,
        occupiedRes,
        mbItemsRes,
        candidatesRes,
        lfRes
      ] = await Promise.all([
        axios.get(TASKS_API, { headers }).catch(() => ({ data: [] })),
        axios.get(ROOMS_API, { headers }).catch(() => ({ data: [] })),
        axios.get(OCCUPIED_ROOMS_API, { headers }).catch(() => ({ data: { occupied_rooms: [] } })),
        axios.get(MINIBAR_ITEMS_API, { headers }).catch(() => ({ data: [] })),
        axios.get(MINIBAR_CANDIDATES_API, { headers }).catch(() => ({ data: [] })),
        axios.get(LOST_FOUND_API, { headers }).catch(() => ({ data: [] })),
      ]);

      setTasks(tasksRes.data || []);
      setRooms(roomsRes.data || []);
      setOccupiedRooms(occupiedRes.data?.occupied_rooms || []);
      setMinibarItems(mbItemsRes.data || []);
      setInventoryCandidates(candidatesRes.data || []);
      setLostFoundItems(lfRes.data || []);
    } catch (err) {
      console.error('Error fetching housekeeping data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // ── Stats Computations ──────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const totalActive = tasks.filter(t => ['pending', 'in_progress'].includes(t.status)).length;
    const inProgress = tasks.filter(t => t.status === 'in_progress').length;
    const awaitingInspection = tasks.filter(t => t.status === 'cleaned').length;
    const inspectedToday = tasks.filter(t => t.status === 'inspected').length;
    const lostStored = lostFoundItems.filter(l => l.status === 'stored').length;
    return { totalActive, inProgress, awaitingInspection, inspectedToday, lostStored };
  }, [tasks, lostFoundItems]);

  // ── Filtered Tasks ─────────────────────────────────────────────────────────
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      const matchesSearch =
        !searchQuery ||
        (task.room_number && task.room_number.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (task.assigned_to_username && task.assigned_to_username.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (task.notes && task.notes.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchesSearch) return false;

      if (taskFilter === 'urgent') return task.priority === 'urgent';
      if (taskFilter === 'pending') return task.status === 'pending';
      if (taskFilter === 'in_progress') return task.status === 'in_progress';
      if (taskFilter === 'cleaned') return task.status === 'cleaned';
      if (taskFilter === 'inspected') return task.status === 'inspected';
      return true;
    });
  }, [tasks, taskFilter, searchQuery]);

  // ── Actions: Tasks ─────────────────────────────────────────────────────────
  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!newTaskRoom) {
      showAlert('Please select a room', 'error');
      return;
    }
    try {
      const headers = getAuthHeaders();
      await axios.post(TASKS_API, {
        room: newTaskRoom,
        task_type: newTaskType,
        priority: newTaskPriority,
        assigned_to_username: newTaskAssignee,
        notes: newTaskNotes,
      }, { headers });

      showAlert('Housekeeping task created successfully!');
      setIsNewTaskModalOpen(false);
      setNewTaskRoom('');
      setNewTaskNotes('');
      setNewTaskAssignee('');
      fetchData();
    } catch (err) {
      showAlert(err.response?.data?.error || 'Failed to create task.', 'error');
    }
  };

  const handleStartCleaning = async (task) => {
    try {
      const headers = getAuthHeaders();
      await axios.patch(`${TASKS_API}${task.id}/`, { status: 'in_progress' }, { headers });
      showAlert(`Cleaning started for Room ${task.room_number}`);
      fetchData();
    } catch (err) {
      showAlert('Failed to start cleaning.', 'error');
    }
  };

  const handleToggleChecklistItem = async (itemIndex) => {
    if (!selectedTask) return;
    const updatedChecklist = [...(selectedTask.checklist || [])];
    updatedChecklist[itemIndex].done = !updatedChecklist[itemIndex].done;

    setSelectedTask(prev => ({ ...prev, checklist: updatedChecklist }));

    try {
      const headers = getAuthHeaders();
      await axios.patch(`${TASKS_API}${selectedTask.id}/`, {
        checklist: updatedChecklist
      }, { headers });
    } catch (err) {
      console.error('Failed to update checklist item:', err);
    }
  };

  const handleMarkCleaned = async () => {
    if (!selectedTask) return;
    try {
      const headers = getAuthHeaders();
      await axios.patch(`${TASKS_API}${selectedTask.id}/`, {
        status: 'cleaned',
        checklist: selectedTask.checklist,
      }, { headers });
      showAlert(`Room ${selectedTask.room_number} marked cleaned! Awaiting supervisor inspection.`);
      setIsChecklistModalOpen(false);
      setSelectedTask(null);
      fetchData();
    } catch (err) {
      showAlert('Failed to mark task as cleaned.', 'error');
    }
  };

  const handleSubmitInspection = async (e) => {
    e.preventDefault();
    if (!selectedTask) return;
    try {
      const headers = getAuthHeaders();
      await axios.post(TASK_INSPECT_API(selectedTask.id), {
        approved: inspectApproval,
        notes: inspectNotes,
      }, { headers });

      showAlert(
        inspectApproval
          ? `Room ${selectedTask.room_number} inspected & approved! Status set to Available.`
          : `Inspection rejected. Room ${selectedTask.room_number} returned to cleaning queue.`
      );
      setIsInspectModalOpen(false);
      setSelectedTask(null);
      setInspectNotes('');
      fetchData();
    } catch (err) {
      showAlert('Failed to record inspection.', 'error');
    }
  };

  // ── Actions: Minibar ───────────────────────────────────────────────────────
  const handleQuantityChange = (itemId, delta) => {
    setConsumedQuantities(prev => {
      const current = prev[itemId] || 0;
      const next = Math.max(0, current + delta);
      return { ...prev, [itemId]: next };
    });
  };

  const minibarSelectedRoomDetails = useMemo(() => {
    if (!selectedMinibarRoom) return null;
    return occupiedRooms.find(r => String(r.room_id) === String(selectedMinibarRoom));
  }, [selectedMinibarRoom, occupiedRooms]);

  const minibarLineItems = useMemo(() => {
    const list = minibarItems.length > 0 ? minibarItems : inventoryCandidates.map(c => ({
      item: c.id,
      item_name: c.name,
      item_code: c.item_code,
      unit: c.unit,
      price: c.selling_price || 40.0,
      current_quantity: 2,
    }));
    return list;
  }, [minibarItems, inventoryCandidates]);

  const minibarGrandTotal = useMemo(() => {
    return minibarLineItems.reduce((acc, it) => {
      const qty = consumedQuantities[it.item || it.id] || 0;
      return acc + (qty * Number(it.price || 0));
    }, 0);
  }, [minibarLineItems, consumedQuantities]);

  const handlePostMinibarConsumption = async () => {
    if (!selectedMinibarRoom) {
      showAlert('Please select a room.', 'error');
      return;
    }
    const consumedList = Object.entries(consumedQuantities)
      .filter(([_, qty]) => qty > 0)
      .map(([idStr, qty]) => {
        const itemObj = minibarLineItems.find(it => String(it.item || it.id) === idStr);
        return {
          item_id: Number(idStr),
          quantity: qty,
          price: itemObj ? itemObj.price : 0,
        };
      });

    if (consumedList.length === 0) {
      showAlert('Please enter at least one consumed item quantity.', 'error');
      return;
    }

    setMinibarPosting(true);
    try {
      const headers = getAuthHeaders();
      const res = await axios.post(MINIBAR_CONSUME_API, {
        room_id: selectedMinibarRoom,
        items: consumedList,
        notes: minibarNotes || 'Room minibar consumption',
      }, { headers });

      setPostingSuccess(res.data);
      setConsumedQuantities({});
      setMinibarNotes('');
      showAlert(`Successfully charged ETB ${minibarGrandTotal.toFixed(2)} to Room ${res.data.room_number} Folio!`);
      fetchData();
    } catch (err) {
      showAlert(err.response?.data?.error || 'Failed to post minibar charges.', 'error');
    } finally {
      setMinibarPosting(false);
    }
  };

  const handleAddCatalogItem = async (e) => {
    e.preventDefault();
    if (!catalogInvId) {
      showAlert('Select an inventory item', 'error');
      return;
    }
    try {
      const headers = getAuthHeaders();
      await axios.post(MINIBAR_ITEMS_API, {
        item: catalogInvId,
        standard_quantity: catalogStandardQty,
        current_quantity: catalogStandardQty,
        price: catalogPrice || 0,
      }, { headers });
      showAlert('Minibar item added to catalog!');
      setIsAddMinibarItemModalOpen(false);
      setCatalogInvId('');
      setCatalogPrice('');
      fetchData();
    } catch (err) {
      showAlert(err.response?.data?.error || 'Failed to add minibar item.', 'error');
    }
  };

  // ── Actions: Lost & Found ──────────────────────────────────────────────────
  const handleCreateLostFound = async (e) => {
    e.preventDefault();
    if (!newLostName) {
      showAlert('Item name is required', 'error');
      return;
    }
    try {
      const headers = getAuthHeaders();
      await axios.post(LOST_FOUND_API, {
        item_name: newLostName,
        room: newLostRoom || null,
        location_found: newLostLocation,
        guest_name: newLostGuest,
        storage_location: newLostStorage,
        description: newLostDesc,
      }, { headers });
      showAlert('Lost item registered into vault!');
      setIsNewLostFoundModalOpen(false);
      setNewLostName('');
      setNewLostLocation('');
      setNewLostGuest('');
      setNewLostDesc('');
      fetchData();
    } catch (err) {
      showAlert('Failed to register lost item.', 'error');
    }
  };

  const handleClaimLostFound = async (e) => {
    e.preventDefault();
    if (!selectedLostItem) return;
    if (!claimantName) {
      showAlert('Claimant name is required', 'error');
      return;
    }
    try {
      const headers = getAuthHeaders();
      await axios.post(LOST_FOUND_CLAIM_API(selectedLostItem.id), {
        claimed_by: claimantName,
        claimant_phone: claimantPhone,
        notes: claimNotes,
      }, { headers });
      showAlert(`Item returned to ${claimantName}! Status updated to Claimed.`);
      setIsClaimModalOpen(false);
      setSelectedLostItem(null);
      setClaimantName('');
      setClaimantPhone('');
      setClaimNotes('');
      fetchData();
    } catch (err) {
      showAlert('Failed to process claim.', 'error');
    }
  };

  return (
    <div style={styles.container}>
      {/* Toast Alert */}
      <AnimatePresence>
        {alertMsg && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            style={{
              ...styles.toast,
              backgroundColor: alertMsg.type === 'error' ? '#ef4444' : '#10b981',
            }}
          >
            {alertMsg.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
            <span>{alertMsg.message}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Housekeeping & Minibar Management</h1>
          <p style={styles.subtitle}>
            Manage room cleaning workflows, digital checklists, minibar consumption to folio, and lost & found vault.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={fetchData} style={styles.refreshBtn} title="Refresh Data">
            <RefreshCw size={16} />
          </button>
          {activeTab === 'tasks' && (
            <button onClick={() => setIsNewTaskModalOpen(true)} style={styles.primaryActionBtn}>
              <Plus size={16} /> Assign / New Task
            </button>
          )}
          {activeTab === 'minibar' && (
            <button onClick={() => setIsAddMinibarItemModalOpen(true)} style={styles.primaryActionBtn}>
              <Plus size={16} /> Add Minibar Item
            </button>
          )}
          {activeTab === 'lost_found' && (
            <button onClick={() => setIsNewLostFoundModalOpen(true)} style={styles.primaryActionBtn}>
              <Plus size={16} /> Register Found Item
            </button>
          )}
        </div>
      </div>

      {/* Metric Cards Banner */}
      <div style={styles.statsGrid}>
        <div style={styles.statCard}>
          <div style={{ ...styles.statIcon, background: 'rgba(245, 158, 11, 0.12)', color: '#d97706' }}>
            <Clock size={20} />
          </div>
          <div>
            <div style={styles.statLabel}>Active Cleaning Tasks</div>
            <div style={styles.statValue}>{stats.totalActive}</div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={{ ...styles.statIcon, background: 'rgba(14, 165, 233, 0.12)', color: '#0284c7' }}>
            <Sparkles size={20} />
          </div>
          <div>
            <div style={styles.statLabel}>In Progress</div>
            <div style={styles.statValue}>{stats.inProgress}</div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={{ ...styles.statIcon, background: 'rgba(168, 85, 247, 0.12)', color: '#9333ea' }}>
            <CheckSquare size={20} />
          </div>
          <div>
            <div style={styles.statLabel}>Awaiting Inspection</div>
            <div style={styles.statValue}>{stats.awaitingInspection}</div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={{ ...styles.statIcon, background: 'rgba(16, 185, 129, 0.12)', color: '#059669' }}>
            <UserCheck size={20} />
          </div>
          <div>
            <div style={styles.statLabel}>Inspected & Approved</div>
            <div style={styles.statValue}>{stats.inspectedToday}</div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={{ ...styles.statIcon, background: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' }}>
            <Package size={20} />
          </div>
          <div>
            <div style={styles.statLabel}>Lost & Found in Vault</div>
            <div style={styles.statValue}>{stats.lostStored}</div>
          </div>
        </div>
      </div>

      {/* Top Tab Navigator */}
      <div style={styles.tabBar}>
        <button
          onClick={() => setActiveTab('tasks')}
          style={{
            ...styles.tabBtn,
            ...(activeTab === 'tasks' ? styles.tabBtnActive : {})
          }}
        >
          <Sparkles size={16} /> Cleaning Tasks & Inspections ({tasks.length})
        </button>
        <button
          onClick={() => setActiveTab('minibar')}
          style={{
            ...styles.tabBtn,
            ...(activeTab === 'minibar' ? styles.tabBtnActive : {})
          }}
        >
          <Wine size={16} /> Minibar Consumption & Restock
        </button>
        <button
          onClick={() => setActiveTab('lost_found')}
          style={{
            ...styles.tabBtn,
            ...(activeTab === 'lost_found' ? styles.tabBtnActive : {})
          }}
        >
          <ShieldAlert size={16} /> Lost & Found Vault ({lostFoundItems.length})
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 1: CLEANING TASKS & INSPECTIONS
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'tasks' && (
        <div>
          {/* Filter Bar */}
          <div style={styles.filterRow}>
            <div style={styles.searchBox}>
              <Search size={16} color="#94a3b8" />
              <input
                type="text"
                placeholder="Search Room #, Housekeeper, Notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={styles.searchInput}
              />
            </div>
            <div style={styles.pillGroup}>
              {['all', 'urgent', 'pending', 'in_progress', 'cleaned', 'inspected'].map((filterKey) => (
                <button
                  key={filterKey}
                  onClick={() => setTaskFilter(filterKey)}
                  style={{
                    ...styles.filterPill,
                    ...(taskFilter === filterKey ? styles.filterPillActive : {})
                  }}
                >
                  {filterKey.replace('_', ' ').toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Tasks Grid */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '60px', color: '#64748b' }}>
              <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 12px' }} />
              <p>Loading Housekeeping Tasks...</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div style={styles.emptyState}>
              <Sparkles size={48} color="#cbd5e1" style={{ margin: '0 auto 12px' }} />
              <h3>No Cleaning Tasks Found</h3>
              <p>All rooms are currently inspected or no tasks match your filter.</p>
              <button onClick={() => setIsNewTaskModalOpen(true)} style={styles.primaryActionBtn}>
                <Plus size={16} /> Create Cleaning Task
              </button>
            </div>
          ) : (
            <div style={styles.cardsGrid}>
              {filteredTasks.map((task) => {
                const totalChecklist = task.checklist?.length || 0;
                const completedChecklist = task.checklist?.filter(c => c.done)?.length || 0;
                const progressPct = totalChecklist > 0 ? (completedChecklist / totalChecklist) * 100 : 0;

                const isUrgent = task.priority === 'urgent';
                const statusStyle = {
                  pending: { bg: '#fef3c7', text: '#b45309', label: 'Pending' },
                  in_progress: { bg: '#e0f2fe', text: '#0369a1', label: 'In Progress' },
                  cleaned: { bg: '#f3e8ff', text: '#7e22ce', label: 'Cleaned (Inspection Due)' },
                  inspected: { bg: '#dcfce7', text: '#15803d', label: 'Inspected & Approved' },
                  failed: { bg: '#fee2e2', text: '#b91c1c', label: 'Failed (Re-clean)' },
                }[task.status] || { bg: '#f1f5f9', text: '#475569', label: task.status };

                return (
                  <div key={task.id} style={{ ...styles.taskCard, borderColor: isUrgent ? '#f87171' : 'rgba(226,232,240,0.8)' }}>
                    <div style={styles.taskCardHeader}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={styles.roomBadge}>Room {task.room_number}</span>
                        <span style={styles.roomTypeTag}>{task.room_type || 'Standard'}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {isUrgent && <span style={styles.urgentBadge}>🔥 URGENT</span>}
                        <span style={{ ...styles.statusBadge, backgroundColor: statusStyle.bg, color: statusStyle.text }}>
                          {statusStyle.label}
                        </span>
                      </div>
                    </div>

                    <div style={styles.taskCardBody}>
                      <div style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b', marginBottom: '4px' }}>
                        {task.task_type_display || task.task_type}
                      </div>
                      {task.notes && (
                        <p style={{ fontSize: '12px', color: '#64748b', margin: '4px 0 10px', fontStyle: 'italic' }}>
                          "{task.notes}"
                        </p>
                      )}

                      <div style={styles.metaRow}>
                        <span style={styles.metaLabel}>Assigned To:</span>
                        <span style={styles.metaValue}>{task.assigned_to_username || 'Unassigned'}</span>
                      </div>

                      {/* Checklist Progress */}
                      {totalChecklist > 0 && (
                        <div style={{ marginTop: '12px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>
                            <span>Checklist Progress</span>
                            <span>{completedChecklist}/{totalChecklist} ({progressPct.toFixed(0)}%)</span>
                          </div>
                          <div style={styles.progressBarBg}>
                            <div style={{ ...styles.progressBarFill, width: `${progressPct}%`, backgroundColor: progressPct === 100 ? '#10b981' : '#0ea5e9' }} />
                          </div>
                        </div>
                      )}
                    </div>

                    <div style={styles.taskCardFooter}>
                      {task.status === 'pending' && (
                        <button onClick={() => handleStartCleaning(task)} style={styles.startCleanBtn}>
                          <Sparkles size={14} /> Start Cleaning
                        </button>
                      )}

                      {task.status === 'in_progress' && (
                        <button
                          onClick={() => {
                            setSelectedTask(task);
                            setIsChecklistModalOpen(true);
                          }}
                          style={styles.openChecklistBtn}
                        >
                          <CheckSquare size={14} /> Complete Checklist ({completedChecklist}/{totalChecklist})
                        </button>
                      )}

                      {task.status === 'cleaned' && (
                        <button
                          onClick={() => {
                            setSelectedTask(task);
                            setIsInspectModalOpen(true);
                          }}
                          style={styles.inspectBtn}
                        >
                          <UserCheck size={14} /> Supervisor Inspect & Sign-off
                        </button>
                      )}

                      {task.status === 'inspected' && (
                        <div style={{ fontSize: '12px', color: '#15803d', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={15} /> Room Available for Check-in
                        </div>
                      )}

                      <button
                        onClick={() => {
                          setSelectedTask(task);
                          setIsChecklistModalOpen(true);
                        }}
                        style={styles.viewDetailsBtn}
                        title="View Checklist"
                      >
                        <Eye size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 2: MINIBAR CONSUMPTION & RESTOCK
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'minibar' && (
        <div style={styles.minibarContainer}>
          <div style={styles.minibarLeftCol}>
            <div style={styles.cardBox}>
              <h2 style={styles.cardTitle}>1. Select Room & Guest</h2>
              <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '14px' }}>
                Select an occupied room to charge minibar items directly to the guest's folio and deduct store inventory.
              </p>

              <select
                value={selectedMinibarRoom}
                onChange={(e) => {
                  setSelectedMinibarRoom(e.target.value);
                  setPostingSuccess(null);
                }}
                style={styles.selectInput}
              >
                <option value="">-- Choose Room --</option>
                {rooms.map(room => {
                  const occ = occupiedRooms.find(o => String(o.room_id) === String(room.id));
                  return (
                    <option key={room.id} value={room.id}>
                      Room {room.room_number} {occ ? `(🏨 ${occ.guest_name} - Checked In)` : `(${room.status})`}
                    </option>
                  );
                })}
              </select>

              {minibarSelectedRoomDetails ? (
                <div style={styles.guestFolioInfo}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: '800', color: '#0f766e' }}>
                      {minibarSelectedRoomDetails.guest_name}
                    </span>
                    <span style={styles.activeGuestBadge}>Active Check-In</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
                    Confirmation: <b>{minibarSelectedRoomDetails.confirmation_code}</b> | Room: <b>{minibarSelectedRoomDetails.room_number}</b>
                  </div>
                </div>
              ) : selectedMinibarRoom ? (
                <div style={styles.warningNotice}>
                  <AlertTriangle size={15} color="#d97706" />
                  <span>No active check-in on this room. Charges will deduct inventory but cannot link to guest folio.</span>
                </div>
              ) : null}

              {/* Notes */}
              <div style={{ marginTop: '16px' }}>
                <label style={styles.formLabel}>Consumption Audit Notes</label>
                <input
                  type="text"
                  placeholder="e.g. Daily mini-bar restock / check-out audit"
                  value={minibarNotes}
                  onChange={(e) => setMinibarNotes(e.target.value)}
                  style={styles.textInput}
                />
              </div>

              {/* Success Result */}
              {postingSuccess && (
                <div style={styles.successReceiptBox}>
                  <CheckCircle2 size={18} color="#15803d" />
                  <div>
                    <div style={{ fontWeight: '800', color: '#15803d', fontSize: '13px' }}>
                      Posted to Room {postingSuccess.room_number} Folio!
                    </div>
                    <div style={{ fontSize: '11px', color: '#334155', marginTop: '4px' }}>
                      Guest: <b>{postingSuccess.guest_name}</b> | Charges: {postingSuccess.charges?.length} items
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div style={styles.minibarRightCol}>
            <div style={styles.cardBox}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <div>
                  <h2 style={styles.cardTitle}>2. Record Consumed Items</h2>
                  <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>
                    Adjust consumed quantity. System will post charges to room folio and auto-deduct inventory.
                  </p>
                </div>
                <div style={styles.grandTotalBadge}>
                  Total: ETB {minibarGrandTotal.toFixed(2)}
                </div>
              </div>

              <div style={styles.minibarItemsTable}>
                {minibarLineItems.map(item => {
                  const itemId = item.item || item.id;
                  const qty = consumedQuantities[itemId] || 0;
                  const lineTotal = qty * Number(item.price || 0);

                  return (
                    <div key={itemId} style={styles.minibarRow}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: '700', fontSize: '13px', color: '#0f172a' }}>
                          {item.item_name || item.name}
                        </div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                          Unit Price: <b>ETB {Number(item.price || 0).toFixed(2)}</b> | Standard: {item.standard_quantity || 2} {item.unit || 'pcs'}
                        </div>
                      </div>

                      <div style={styles.stepperBox}>
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(itemId, -1)}
                          style={styles.stepperBtn}
                          disabled={qty <= 0}
                        >
                          -
                        </button>
                        <span style={styles.stepperVal}>{qty}</span>
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(itemId, 1)}
                          style={styles.stepperBtn}
                        >
                          +
                        </button>
                      </div>

                      <div style={{ width: '90px', textAlign: 'right', fontWeight: '800', fontSize: '13px', color: qty > 0 ? '#0f766e' : '#94a3b8' }}>
                        ETB {lineTotal.toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={handlePostMinibarConsumption}
                  disabled={minibarPosting || minibarGrandTotal <= 0}
                  style={{
                    ...styles.primaryActionBtn,
                    padding: '12px 24px',
                    fontSize: '14px',
                    opacity: (minibarPosting || minibarGrandTotal <= 0) ? 0.6 : 1,
                  }}
                >
                  {minibarPosting ? (
                    <>Posting Charges...</>
                  ) : (
                    <>
                      <Wine size={16} /> Post ETB {minibarGrandTotal.toFixed(2)} to Room Folio & Deduct Stock
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 3: LOST & FOUND VAULT
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'lost_found' && (
        <div>
          <div style={styles.cardsGrid}>
            {lostFoundItems.length === 0 ? (
              <div style={styles.emptyState}>
                <Package size={48} color="#cbd5e1" style={{ margin: '0 auto 12px' }} />
                <h3>No Lost & Found Items</h3>
                <p>Register guest forgotten belongings to keep a digital track record.</p>
                <button onClick={() => setIsNewLostFoundModalOpen(true)} style={styles.primaryActionBtn}>
                  <Plus size={16} /> Register Found Item
                </button>
              </div>
            ) : (
              lostFoundItems.map(item => (
                <div key={item.id} style={styles.taskCard}>
                  <div style={styles.taskCardHeader}>
                    <div style={{ fontWeight: '800', fontSize: '15px', color: '#0f172a' }}>
                      {item.item_name}
                    </div>
                    <span style={{
                      ...styles.statusBadge,
                      backgroundColor: item.status === 'claimed' ? '#dcfce7' : '#fef3c7',
                      color: item.status === 'claimed' ? '#15803d' : '#b45309',
                    }}>
                      {item.status_display || item.status}
                    </span>
                  </div>

                  <div style={styles.taskCardBody}>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Found Location:</span>
                      <span style={styles.metaValue}>
                        {item.room_number ? `Room ${item.room_number}` : (item.location_found || 'Hotel Area')}
                      </span>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Found By:</span>
                      <span style={styles.metaValue}>{item.found_by_name} ({item.found_date})</span>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Safe Storage:</span>
                      <span style={styles.metaValue}>🔐 {item.storage_location}</span>
                    </div>
                    {item.guest_name && (
                      <div style={styles.metaRow}>
                        <span style={styles.metaLabel}>Guest Name:</span>
                        <span style={styles.metaValue}>{item.guest_name}</span>
                      </div>
                    )}
                    {item.description && (
                      <p style={{ fontSize: '12px', color: '#64748b', margin: '8px 0 0', fontStyle: 'italic' }}>
                        "{item.description}"
                      </p>
                    )}

                    {item.status === 'claimed' && (
                      <div style={styles.claimedNotice}>
                        ✓ Claimed by <b>{item.claimed_by}</b> {item.claimant_phone && `(${item.claimant_phone})`}
                      </div>
                    )}
                  </div>

                  {item.status === 'stored' && (
                    <div style={styles.taskCardFooter}>
                      <button
                        onClick={() => {
                          setSelectedLostItem(item);
                          setIsClaimModalOpen(true);
                        }}
                        style={styles.claimActionBtn}
                      >
                        <UserCheck size={14} /> Hand Over / Process Claim
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: NEW TASK / ASSIGN ROOM
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isNewTaskModalOpen && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>Assign Room Cleaning Task</h3>
                <button onClick={() => setIsNewTaskModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleCreateTask} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <label style={styles.formLabel}>Select Room *</label>
                  <select
                    value={newTaskRoom}
                    onChange={(e) => setNewTaskRoom(e.target.value)}
                    required
                    style={styles.selectInput}
                  >
                    <option value="">-- Choose Room --</option>
                    {rooms.map(r => (
                      <option key={r.id} value={r.id}>
                        Room {r.room_number} ({r.room_type} - {r.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={styles.formLabel}>Task Type</label>
                    <select
                      value={newTaskType}
                      onChange={(e) => setNewTaskType(e.target.value)}
                      style={styles.selectInput}
                    >
                      <option value="checkout_cleaning">Checkout Cleaning</option>
                      <option value="stayover_cleaning">Stayover / Daily Cleaning</option>
                      <option value="deep_cleaning">Deep Cleaning</option>
                      <option value="touch_up">Touch Up / Inspection</option>
                      <option value="turndown">Turn-Down Service</option>
                    </select>
                  </div>
                  <div>
                    <label style={styles.formLabel}>Priority</label>
                    <select
                      value={newTaskPriority}
                      onChange={(e) => setNewTaskPriority(e.target.value)}
                      style={styles.selectInput}
                    >
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                      <option value="urgent">🔥 Urgent (Incoming Guest)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label style={styles.formLabel}>Assign to Staff Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Almaz / Tigist / Cleaner A"
                    value={newTaskAssignee}
                    onChange={(e) => setNewTaskAssignee(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div>
                  <label style={styles.formLabel}>Cleaning Instructions / Notes</label>
                  <textarea
                    rows={2}
                    placeholder="e.g. Extra towels requested, check minibar fridge"
                    value={newTaskNotes}
                    onChange={(e) => setNewTaskNotes(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsNewTaskModalOpen(false)} style={styles.secondaryBtn}>
                    Cancel
                  </button>
                  <button type="submit" style={styles.primaryActionBtn}>
                    Create Task
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CHECKLIST & MARK CLEANED
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isChecklistModalOpen && selectedTask && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <div>
                  <h3 style={styles.modalTitle}>Room {selectedTask.room_number} Cleaning Checklist</h3>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    {selectedTask.task_type_display} | Assigned to: <b>{selectedTask.assigned_to_username || 'Staff'}</b>
                  </div>
                </div>
                <button onClick={() => setIsChecklistModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <div style={{ maxHeight: '350px', overflowY: 'auto', paddingRight: '6px' }}>
                {(selectedTask.checklist || []).map((item, idx) => (
                  <label key={idx} style={styles.checklistRow}>
                    <input
                      type="checkbox"
                      checked={item.done}
                      onChange={() => handleToggleChecklistItem(idx)}
                      style={{ width: '18px', height: '18px', accentColor: '#0f766e', cursor: 'pointer' }}
                    />
                    <span style={{ fontSize: '13px', color: item.done ? '#64748b' : '#0f172a', textDecoration: item.done ? 'line-through' : 'none' }}>
                      {item.label}
                    </span>
                  </label>
                ))}
              </div>

              <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#64748b' }}>
                  Checked: {(selectedTask.checklist || []).filter(c => c.done).length} / {(selectedTask.checklist || []).length}
                </span>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button type="button" onClick={() => setIsChecklistModalOpen(false)} style={styles.secondaryBtn}>
                    Close
                  </button>
                  <button type="button" onClick={handleMarkCleaned} style={styles.primaryActionBtn}>
                    <CheckCircle2 size={16} /> Mark as Cleaned & Submit for Inspection
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: SUPERVISOR INSPECTION
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isInspectModalOpen && selectedTask && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>Supervisor Inspection — Room {selectedTask.room_number}</h3>
                <button onClick={() => setIsInspectModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleSubmitInspection} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                  Review cleaning quality and verify room readiness before releasing room to <b>Available</b>.
                </p>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setInspectApproval(true)}
                    style={{
                      flex: 1,
                      padding: '12px',
                      borderRadius: '10px',
                      border: inspectApproval ? '2px solid #10b981' : '1px solid #cbd5e1',
                      backgroundColor: inspectApproval ? 'rgba(16, 185, 129, 0.1)' : '#fff',
                      color: inspectApproval ? '#065f46' : '#64748b',
                      fontWeight: '700',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px'
                    }}
                  >
                    <CheckCircle2 size={18} /> Approve & Make Available
                  </button>

                  <button
                    type="button"
                    onClick={() => setInspectApproval(false)}
                    style={{
                      flex: 1,
                      padding: '12px',
                      borderRadius: '10px',
                      border: !inspectApproval ? '2px solid #ef4444' : '1px solid #cbd5e1',
                      backgroundColor: !inspectApproval ? 'rgba(239, 68, 68, 0.1)' : '#fff',
                      color: !inspectApproval ? '#991b1b' : '#64748b',
                      fontWeight: '700',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px'
                    }}
                  >
                    <AlertTriangle size={18} /> Reject / Needs Re-cleaning
                  </button>
                </div>

                <div>
                  <label style={styles.formLabel}>Supervisor Feedback Notes</label>
                  <textarea
                    rows={3}
                    placeholder={inspectApproval ? "Everything spotless, room ready for next guest." : "Dust on headboard, mirrors streaky. Re-clean required."}
                    value={inspectNotes}
                    onChange={(e) => setInspectNotes(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsInspectModalOpen(false)} style={styles.secondaryBtn}>
                    Cancel
                  </button>
                  <button type="submit" style={styles.primaryActionBtn}>
                    Submit Inspection Sign-off
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: REGISTER LOST & FOUND
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isNewLostFoundModalOpen && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>Register Found Guest Belongings</h3>
                <button onClick={() => setIsNewLostFoundModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleCreateLostFound} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={styles.formLabel}>Item Name / Description *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Black Leather Wallet, iPhone 14, Gold Watch"
                    value={newLostName}
                    onChange={(e) => setNewLostName(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={styles.formLabel}>Room (if found in room)</label>
                    <select
                      value={newLostRoom}
                      onChange={(e) => setNewLostRoom(e.target.value)}
                      style={styles.selectInput}
                    >
                      <option value="">-- Non-Room Location --</option>
                      {rooms.map(r => (
                        <option key={r.id} value={r.id}>Room {r.room_number}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={styles.formLabel}>Specific Location Found</label>
                    <input
                      type="text"
                      placeholder="e.g. Under bed, Closet shelf, Lobby sofa"
                      value={newLostLocation}
                      onChange={(e) => setNewLostLocation(e.target.value)}
                      style={styles.textInput}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={styles.formLabel}>Guest Name (if known)</label>
                    <input
                      type="text"
                      placeholder="e.g. Fitsum Belay"
                      value={newLostGuest}
                      onChange={(e) => setNewLostGuest(e.target.value)}
                      style={styles.textInput}
                    />
                  </div>
                  <div>
                    <label style={styles.formLabel}>Safe Storage Locker</label>
                    <input
                      type="text"
                      placeholder="e.g. Locker B-12 / Front Desk Safe"
                      value={newLostStorage}
                      onChange={(e) => setNewLostStorage(e.target.value)}
                      style={styles.textInput}
                    />
                  </div>
                </div>

                <div>
                  <label style={styles.formLabel}>Additional Notes / Color / Serial #</label>
                  <textarea
                    rows={2}
                    placeholder="Notable markings, serial numbers, case color..."
                    value={newLostDesc}
                    onChange={(e) => setNewLostDesc(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsNewLostFoundModalOpen(false)} style={styles.secondaryBtn}>
                    Cancel
                  </button>
                  <button type="submit" style={styles.primaryActionBtn}>
                    Register Item in Vault
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CLAIM LOST ITEM
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isClaimModalOpen && selectedLostItem && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>Process Claim: {selectedLostItem.item_name}</h3>
                <button onClick={() => setIsClaimModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleClaimLostFound} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>
                  Verify guest identity before handing over stored property.
                </p>

                <div>
                  <label style={styles.formLabel}>Claimant Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="Guest or representative name"
                    value={claimantName}
                    onChange={(e) => setClaimantName(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div>
                  <label style={styles.formLabel}>Claimant Phone Number</label>
                  <input
                    type="text"
                    placeholder="e.g. 0911223344"
                    value={claimantPhone}
                    onChange={(e) => setClaimantPhone(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div>
                  <label style={styles.formLabel}>Verification / ID Details</label>
                  <textarea
                    rows={2}
                    placeholder="e.g. Verified National ID / Room Key / Item unlock pin"
                    value={claimNotes}
                    onChange={(e) => setClaimNotes(e.target.value)}
                    style={styles.textInput}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsClaimModalOpen(false)} style={styles.secondaryBtn}>
                    Cancel
                  </button>
                  <button type="submit" style={styles.primaryActionBtn}>
                    Confirm Handover & Complete Claim
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: ADD MINIBAR CATALOG ITEM
         ───────────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isAddMinibarItemModalOpen && (
          <div style={styles.modalOverlay}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={styles.modalContent}>
              <div style={styles.modalHeader}>
                <h3 style={styles.modalTitle}>Add Item to Minibar Catalog</h3>
                <button onClick={() => setIsAddMinibarItemModalOpen(false)} style={styles.closeBtn}><X size={18} /></button>
              </div>

              <form onSubmit={handleAddCatalogItem} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={styles.formLabel}>Select Inventory Item *</label>
                  <select
                    value={catalogInvId}
                    onChange={(e) => {
                      setCatalogInvId(e.target.value);
                      const chosen = inventoryCandidates.find(c => String(c.id) === e.target.value);
                      if (chosen && chosen.selling_price) setCatalogPrice(chosen.selling_price);
                    }}
                    required
                    style={styles.selectInput}
                  >
                    <option value="">-- Choose Inventory Item --</option>
                    {inventoryCandidates.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.item_code}) - In Stock: {c.current_stock} {c.unit}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={styles.formLabel}>Selling Price (ETB) *</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      placeholder="e.g. 50.00"
                      value={catalogPrice}
                      onChange={(e) => setCatalogPrice(e.target.value)}
                      style={styles.textInput}
                    />
                  </div>
                  <div>
                    <label style={styles.formLabel}>Standard Room Stock</label>
                    <input
                      type="number"
                      required
                      min={1}
                      value={catalogStandardQty}
                      onChange={(e) => setCatalogStandardQty(Number(e.target.value))}
                      style={styles.textInput}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                  <button type="button" onClick={() => setIsAddMinibarItemModalOpen(false)} style={styles.secondaryBtn}>
                    Cancel
                  </button>
                  <button type="submit" style={styles.primaryActionBtn}>
                    Add to Minibar Catalog
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STYLES
// ─────────────────────────────────────────────────────────────────────────────
const styles = {
  container: {
    padding: '24px 30px',
    backgroundColor: '#f8fafc',
    minHeight: '100vh',
    fontFamily: "'Inter', sans-serif",
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
  },
  title: {
    fontSize: '24px',
    fontWeight: '800',
    color: '#0f172a',
    margin: 0,
    letterSpacing: '-0.5px',
  },
  subtitle: {
    fontSize: '13px',
    color: '#64748b',
    margin: '4px 0 0',
  },
  refreshBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '10px 14px',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
    backgroundColor: '#ffffff',
    color: '#475569',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  primaryActionBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 18px',
    borderRadius: '10px',
    border: 'none',
    backgroundColor: '#0f766e',
    color: '#ffffff',
    fontWeight: '700',
    fontSize: '13px',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(15, 118, 110, 0.2)',
    transition: 'all 0.2s ease',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
    gap: '14px',
    marginBottom: '24px',
  },
  statCard: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    padding: '16px 18px',
    backgroundColor: '#ffffff',
    borderRadius: '14px',
    border: '1px solid rgba(226, 232, 240, 0.8)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
  },
  statIcon: {
    width: '42px',
    height: '42px',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  statLabel: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.4px',
  },
  statValue: {
    fontSize: '22px',
    fontWeight: '800',
    color: '#0f172a',
    marginTop: '2px',
  },
  tabBar: {
    display: 'flex',
    gap: '10px',
    borderBottom: '2px solid #e2e8f0',
    marginBottom: '22px',
    paddingBottom: '2px',
  },
  tabBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 18px',
    backgroundColor: 'transparent',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#64748b',
    fontWeight: '700',
    fontSize: '13px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    marginBottom: '-4px',
  },
  tabBtnActive: {
    color: '#0f766e',
    borderBottom: '2px solid #0f766e',
  },
  filterRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '14px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 14px',
    backgroundColor: '#ffffff',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
    width: '320px',
  },
  searchInput: {
    border: 'none',
    outline: 'none',
    fontSize: '13px',
    color: '#0f172a',
    width: '100%',
  },
  pillGroup: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  filterPill: {
    padding: '6px 14px',
    borderRadius: '20px',
    border: '1px solid #e2e8f0',
    backgroundColor: '#ffffff',
    color: '#64748b',
    fontSize: '11px',
    fontWeight: '700',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  filterPillActive: {
    backgroundColor: '#0f766e',
    color: '#ffffff',
    borderColor: '#0f766e',
  },
  cardsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '16px',
  },
  taskCard: {
    backgroundColor: '#ffffff',
    borderRadius: '14px',
    border: '1px solid #e2e8f0',
    padding: '16px',
    boxShadow: '0 2px 6px rgba(0,0,0,0.02)',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  },
  taskCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  roomBadge: {
    fontSize: '15px',
    fontWeight: '800',
    color: '#0f172a',
  },
  roomTypeTag: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#64748b',
    backgroundColor: '#f1f5f9',
    padding: '2px 8px',
    borderRadius: '6px',
  },
  urgentBadge: {
    fontSize: '10px',
    fontWeight: '800',
    color: '#dc2626',
    backgroundColor: '#fee2e2',
    padding: '4px 8px',
    borderRadius: '12px',
    letterSpacing: '0.4px',
  },
  statusBadge: {
    fontSize: '11px',
    fontWeight: '700',
    padding: '4px 10px',
    borderRadius: '12px',
  },
  taskCardBody: {
    marginBottom: '16px',
  },
  metaRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    marginTop: '4px',
  },
  metaLabel: {
    color: '#64748b',
  },
  metaValue: {
    fontWeight: '700',
    color: '#1e293b',
  },
  progressBarBg: {
    height: '6px',
    backgroundColor: '#e2e8f0',
    borderRadius: '10px',
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: '10px',
    transition: 'width 0.3s ease',
  },
  taskCardFooter: {
    display: 'flex',
    gap: '8px',
    borderTop: '1px solid #f1f5f9',
    paddingTop: '12px',
    alignItems: 'center',
  },
  startCleanBtn: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '8px 12px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#0284c7',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  openChecklistBtn: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '8px 12px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#0f766e',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  inspectBtn: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '8px 12px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#9333ea',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  viewDetailsBtn: {
    padding: '8px 12px',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
    backgroundColor: '#f8fafc',
    color: '#64748b',
    cursor: 'pointer',
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px',
    backgroundColor: '#ffffff',
    borderRadius: '14px',
    border: '1px solid #e2e8f0',
    color: '#64748b',
  },
  // Minibar tab
  minibarContainer: {
    display: 'grid',
    gridTemplateColumns: '1fr 2fr',
    gap: '20px',
  },
  minibarLeftCol: {},
  minibarRightCol: {},
  cardBox: {
    backgroundColor: '#ffffff',
    borderRadius: '14px',
    border: '1px solid #e2e8f0',
    padding: '20px',
    boxShadow: '0 2px 6px rgba(0,0,0,0.02)',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: '800',
    color: '#0f172a',
    margin: '0 0 4px',
  },
  guestFolioInfo: {
    backgroundColor: 'rgba(15, 118, 110, 0.08)',
    borderRadius: '10px',
    padding: '12px',
    marginTop: '12px',
    border: '1px solid rgba(15, 118, 110, 0.15)',
  },
  activeGuestBadge: {
    fontSize: '10px',
    fontWeight: '800',
    color: '#0f766e',
    backgroundColor: '#ffffff',
    padding: '2px 8px',
    borderRadius: '10px',
  },
  warningNotice: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: '#fffbeb',
    border: '1px solid #fde68a',
    borderRadius: '8px',
    padding: '10px',
    fontSize: '12px',
    color: '#b45309',
    marginTop: '12px',
  },
  grandTotalBadge: {
    fontSize: '15px',
    fontWeight: '800',
    color: '#0f766e',
    backgroundColor: 'rgba(15, 118, 110, 0.1)',
    padding: '6px 14px',
    borderRadius: '20px',
  },
  minibarItemsTable: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    maxHeight: '440px',
    overflowY: 'auto',
    paddingRight: '6px',
  },
  minibarRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 14px',
    backgroundColor: '#f8fafc',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
  },
  stepperBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  stepperBtn: {
    width: '28px',
    height: '28px',
    borderRadius: '6px',
    border: '1px solid #cbd5e1',
    backgroundColor: '#ffffff',
    fontWeight: '800',
    fontSize: '14px',
    color: '#1e293b',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepperVal: {
    width: '28px',
    textAlign: 'center',
    fontWeight: '800',
    fontSize: '14px',
    color: '#0f172a',
  },
  successReceiptBox: {
    marginTop: '16px',
    padding: '12px',
    borderRadius: '10px',
    backgroundColor: '#f0fdf4',
    border: '1px solid #bbf7d0',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  // Lost & Found
  claimedNotice: {
    marginTop: '8px',
    fontSize: '11px',
    color: '#15803d',
    backgroundColor: '#dcfce7',
    padding: '4px 8px',
    borderRadius: '6px',
    fontWeight: '600',
  },
  claimActionBtn: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '8px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#0f766e',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  // Forms & Modals
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    padding: '20px',
  },
  modalContent: {
    backgroundColor: '#ffffff',
    borderRadius: '16px',
    width: '100%',
    maxWidth: '520px',
    padding: '24px',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
    borderBottom: '1px solid #f1f5f9',
    paddingBottom: '12px',
  },
  modalTitle: {
    fontSize: '18px',
    fontWeight: '800',
    color: '#0f172a',
    margin: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    padding: '4px',
  },
  formLabel: {
    display: 'block',
    fontSize: '12px',
    fontWeight: '700',
    color: '#475569',
    marginBottom: '6px',
  },
  selectInput: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid #cbd5e1',
    backgroundColor: '#ffffff',
    color: '#0f172a',
    fontSize: '13px',
    outline: 'none',
  },
  textInput: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid #cbd5e1',
    backgroundColor: '#ffffff',
    color: '#0f172a',
    fontSize: '13px',
    outline: 'none',
    boxSizing: 'border-box',
  },
  secondaryBtn: {
    padding: '10px 18px',
    borderRadius: '10px',
    border: '1px solid #cbd5e1',
    backgroundColor: '#ffffff',
    color: '#475569',
    fontWeight: '700',
    fontSize: '13px',
    cursor: 'pointer',
  },
  checklistRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '10px',
    borderRadius: '8px',
    backgroundColor: '#f8fafc',
    marginBottom: '6px',
    cursor: 'pointer',
    border: '1px solid #e2e8f0',
  },
  toast: {
    position: 'fixed',
    top: '20px',
    right: '20px',
    zIndex: 10000,
    color: '#ffffff',
    padding: '12px 20px',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '13px',
    fontWeight: '700',
    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
  },
};
