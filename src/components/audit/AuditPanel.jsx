import React, { useState, useEffect, useCallback } from 'react';
import { getAuditLog } from '../../services/api';
import styles from './AuditPanel.module.css';

const EVENT_TYPES = [
  { value: '', label: 'All events' },
  { value: 'file_upload', label: 'File uploads' },
  { value: 'query', label: 'Queries' },
  { value: 'campaign_created', label: 'Campaigns created' },
  { value: 'campaign_sent', label: 'Campaigns sent' },
];

const EVENT_COLORS = {
  file_upload:      { bg: 'var(--blue-bg)',   color: 'var(--blue)' },
  query:            { bg: 'var(--accent-soft)', color: 'var(--ink-3)' },
  campaign_created: { bg: 'var(--amber-bg)',   color: 'var(--amber)' },
  campaign_sent:    { bg: 'var(--green-bg)',   color: 'var(--green)' },
};

export default function AuditPanel() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterType, setFilterType] = useState('');
  const [lastN, setLastN] = useState(50);
  const [expanded, setExpanded] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getAuditLog(filterType || null, lastN);
      setLogs(data.entries.slice().reverse()); // newest first
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filterType, lastN]);

  useEffect(() => { load(); }, [load]);

  const toggle = (i) => setExpanded((e) => ({ ...e, [i]: !e[i] }));

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>Audit Log</h2>
          <p className={styles.subtitle}>Append-only trail of all agent activity.</p>
        </div>
        <div className={styles.controls}>
          <select
            className={styles.select}
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            {EVENT_TYPES.map((et) => (
              <option key={et.value} value={et.value}>{et.label}</option>
            ))}
          </select>
          <select
            className={styles.select}
            value={lastN}
            onChange={(e) => setLastN(Number(e.target.value))}
          >
            {[20, 50, 100, 200].map((n) => (
              <option key={n} value={n}>Last {n}</option>
            ))}
          </select>
          <button className={styles.refreshBtn} onClick={load} disabled={loading}>
            {loading ? '…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!loading && logs.length === 0 && (
        <div className={styles.empty}>
          No audit entries yet. Run queries or create campaigns to generate logs.
        </div>
      )}

      {loading && logs.length === 0 && (
        <div className={styles.loading}>
          <span className={styles.spinner} /> Loading…
        </div>
      )}

      <div className={styles.list}>
        {logs.map((entry, i) => {
          const ec = EVENT_COLORS[entry.event] || { bg: 'var(--accent-soft)', color: 'var(--ink-4)' };
          const isOpen = !!expanded[i];

          return (
            <div key={i} className={styles.entry}>
              <div className={styles.entryHeader} onClick={() => toggle(i)}>
                <div className={styles.entryMeta}>
                  <span className={styles.eventBadge} style={{ background: ec.bg, color: ec.color }}>
                    {entry.event?.replace(/_/g, ' ')}
                  </span>
                  <span className={styles.ts}>{formatTs(entry.logged_at)}</span>
                  {entry.event === 'query' && entry.question && (
                    <span className={styles.summary}>{entry.question}</span>
                  )}
                  {entry.event === 'file_upload' && (
                    <span className={styles.summary}>{entry.row_count?.toLocaleString()} rows, {entry.column_count} cols</span>
                  )}
                  {entry.event === 'campaign_created' && (
                    <span className={styles.summary}>#{entry.campaign_id} · {entry.recipient_count} recipients</span>
                  )}
                  {entry.event === 'campaign_sent' && (
                    <span className={styles.summary}>
                      #{entry.campaign_id} · sent {entry.sent}/{entry.total}
                    </span>
                  )}
                </div>
                <ChevronIcon dir={isOpen ? 'up' : 'down'} />
              </div>

              {isOpen && (
                <div className={styles.entryBody}>
                  {entry.event === 'query' && (
                    <>
                      {entry.sql && (
                        <div className={styles.field}>
                          <span className={styles.fieldLabel}>SQL</span>
                          <pre className={styles.sql}>{entry.sql}</pre>
                        </div>
                      )}
                      <div className={styles.row2}>
                        <InfoField label="Rows returned" val={entry.row_count?.toLocaleString()} />
                        <InfoField label="Error" val={entry.has_error ? 'Yes' : 'No'} color={entry.has_error ? 'var(--red)' : 'var(--green)'} />
                      </div>
                      {entry.plan && (
                        <div className={styles.field}>
                          <span className={styles.fieldLabel}>Query plan</span>
                          <pre className={styles.json}>{JSON.stringify(entry.plan, null, 2)}</pre>
                        </div>
                      )}
                    </>
                  )}
                  {entry.event === 'file_upload' && (
                    <div className={styles.field}>
                      <span className={styles.fieldLabel}>Columns</span>
                      <div className={styles.chips}>
                        {entry.columns?.map((c) => (
                          <span key={c} className={styles.chip}>{c}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {(entry.event === 'campaign_created' || entry.event === 'campaign_sent') && (
                    <pre className={styles.json}>{JSON.stringify(entry, null, 2)}</pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InfoField({ label, val, color }) {
  return (
    <div className={styles.infoField}>
      <span className={styles.fieldLabel}>{label}</span>
      <span style={{ color: color || 'var(--ink)' }}>{val}</span>
    </div>
  );
}

function formatTs(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function ChevronIcon({ dir }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      style={{ transform: dir === 'up' ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
