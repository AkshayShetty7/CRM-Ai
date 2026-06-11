import React, { useState } from 'react';
import { useAppContext } from '../../context/AppContext';
import styles from './Sidebar.module.css';

const NAV = [
  { id: 'query',    label: 'Query',    icon: SearchIcon },
  { id: 'schema',   label: 'Schema',   icon: TableIcon },
  { id: 'campaign', label: 'Campaigns', icon: MailIcon },
  { id: 'audit',    label: 'Audit Log', icon: ClockIcon },
];

export default function Sidebar() {
  const { state, setTab } = useAppContext();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      {/* Brand */}
      <div className={styles.brand}>
        <span className={styles.dot} />
        {!collapsed && (
          <div className={styles.brandText}>
            <span className={styles.appName}>CRM Agent</span>
            {state.orgName && <span className={styles.orgName}>{state.orgName}</span>}
          </div>
        )}
        <button className={styles.collapseBtn} onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand' : 'Collapse'}>
          <ChevronIcon dir={collapsed ? 'right' : 'left'} />
        </button>
      </div>

      {/* Schema status badge */}
      {!collapsed && (
        <div className={styles.status}>
          {state.schema ? (
            <span className={styles.connected}>
              <span className={styles.statusDot} />
              {state.schema.row_count?.toLocaleString()} rows loaded
            </span>
          ) : (
            <span className={styles.nodata}>No data loaded</span>
          )}
        </div>
      )}

      {/* Nav items */}
      <nav className={styles.nav}>
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`${styles.navItem} ${state.activeTab === id ? styles.active : ''}`}
            onClick={() => setTab(id)}
            title={collapsed ? label : undefined}
          >
            <Icon />
            {!collapsed && <span>{label}</span>}
          </button>
        ))}
      </nav>

      {/* Query history count */}
      {!collapsed && state.queryHistory.length > 0 && (
        <div className={styles.historyHint}>
          {state.queryHistory.length} quer{state.queryHistory.length === 1 ? 'y' : 'ies'} this session
        </div>
      )}
    </aside>
  );
}

function SearchIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
  </svg>;
}
function TableIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>
  </svg>;
}
function MailIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
    <polyline points="22,6 12,13 2,6"/>
  </svg>;
}
function ClockIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>;
}
function ChevronIcon({ dir }) {
  const rotate = dir === 'right' ? 0 : 180;
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    style={{ transform: `rotate(${rotate}deg)`, transition: 'transform 0.2s' }}>
    <polyline points="9 18 15 12 9 6"/>
  </svg>;
}
