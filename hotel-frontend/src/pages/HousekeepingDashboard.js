import React from 'react';
import { Sparkles, LogOut, User } from 'lucide-react';
import HousekeepingManager from './HousekeepingManager';

export default function HousekeepingDashboard({ userData, handleLogout }) {
  const doLogout = () => {
    localStorage.clear();
    if (handleLogout) handleLogout();
    else window.location.replace('/');
  };

  const username = userData?.username || userData?.first_name || 'Staff';

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', color: '#0f172a' }}>
      <header
        className="role-topbar"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '14px 24px',
          backgroundColor: '#0f172a',
          color: '#ffffff',
          borderBottom: '1px solid #1e293b'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#0f766e',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff'
            }}
          >
            <Sparkles size={20} />
          </div>
          <div>
            <div style={{ fontWeight: '800', fontSize: '15px', letterSpacing: '0.5px' }}>
              ACRMA <span style={{ fontWeight: 400, color: '#94a3b8' }}>HOTEL</span>
            </div>
            <div style={{ fontSize: '11px', color: '#14b8a6', fontWeight: '700' }}>
              Housekeeping & Minibar Operations
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'rgba(255,255,255,0.08)',
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '13px'
            }}
          >
            <User size={15} color="#14b8a6" />
            <span style={{ fontWeight: '600' }}>{username}</span>
            <span
              style={{
                fontSize: '10px',
                backgroundColor: '#0f766e',
                color: '#fff',
                padding: '2px 8px',
                borderRadius: '10px',
                fontWeight: '700'
              }}
            >
              HOUSEKEEPING
            </span>
          </div>

          <button
            onClick={doLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#ef4444',
              color: '#fff',
              border: 'none',
              padding: '7px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer'
            }}
            title="Logout"
          >
            <LogOut size={15} /> Logout
          </button>
        </div>
      </header>

      <main style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
        <HousekeepingManager userData={userData} handleLogout={handleLogout} />
      </main>
    </div>
  );
}
