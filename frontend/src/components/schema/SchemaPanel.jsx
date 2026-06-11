import React, { useEffect, useState } from 'react';
import { getSchema, uploadFile } from '../../services/api';
import { useAppContext } from '../../context/AppContext';
import styles from './SchemaPanel.module.css';

const DTYPE_COLORS = {
  text: { bg: '#eef4fc', color: '#1a4d8f' },
  integer: { bg: '#eaf4ef', color: '#2d6a4f' },
  float: { bg: '#eaf4ef', color: '#2d6a4f' },
  date: { bg: '#fdf7e3', color: '#9a6c00' },
  datetime: { bg: '#fdf7e3', color: '#9a6c00' },
  boolean: { bg: '#f4eafc', color: '#6a2d8f' },
};

export default function SchemaPanel() {
  const { state, setSchema } = useAppContext();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileRef = React.useRef();

  const schema = state.schema;

  const refresh = async () => {
    setLoading(true);
    setError('');
    try {
      const s = await getSchema();
      setSchema(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!schema) refresh();
  }, []); // eslint-disable-line

  const handleUpload = async (file) => {
    setUploading(true);
    setError('');
    try {
      const s = await uploadFile(file);
      setSchema(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>Schema</h2>
          <p className={styles.subtitle}>Inspect your loaded dataset's structure.</p>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.outlineBtn} onClick={() => fileRef.current.click()} disabled={uploading}>
            {uploading ? 'Uploading…' : '↑ Upload new file'}
          </button>
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" style={{ display: 'none' }}
            onChange={(e) => e.target.files[0] && handleUpload(e.target.files[0])} />
          <button className={styles.outlineBtn} onClick={refresh} disabled={loading}>
            {loading ? '…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!schema && !loading && (
        <div className={styles.empty}>
          No data loaded. Upload a file to get started.
        </div>
      )}

      {loading && <div className={styles.loading}><span className={styles.spinner} /> Loading schema…</div>}

      {schema && (
        <>
          {/* Summary cards */}
          <div className={styles.cards}>
            <StatCard label="Rows" value={schema.row_count?.toLocaleString()} />
            <StatCard label="Columns" value={schema.columns?.length} />
            <StatCard label="Email column" value={schema.email_column || '—'} highlight={!!schema.email_column} />
            <StatCard label="Name column" value={schema.name_column || '—'} highlight={!!schema.name_column} />
            <StatCard label="Date columns" value={schema.date_columns?.length || 0} />
          </div>

          {/* Column table */}
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Unique</th>
                  <th>Null %</th>
                  <th>Min</th>
                  <th>Max</th>
                  <th>Examples</th>
                </tr>
              </thead>
              <tbody>
                {schema.columns?.map((col) => {
                  const dc = DTYPE_COLORS[col.dtype] || { bg: '#f5f5f5', color: '#555' };
                  const isSpecial =
                    col.name === schema.email_column || col.name === schema.name_column ||
                    schema.date_columns?.includes(col.name);
                  return (
                    <tr key={col.name} className={isSpecial ? styles.specialRow : ''}>
                      <td className={styles.colName}>
                        {col.name}
                        {col.name === schema.email_column && <Badge label="email" color="#1a4d8f" />}
                        {col.name === schema.name_column && <Badge label="name" color="#2d6a4f" />}
                        {schema.date_columns?.includes(col.name) && <Badge label="date" color="#9a6c00" />}
                      </td>
                      <td>
                        <span className={styles.typeBadge} style={{ background: dc.bg, color: dc.color }}>
                          {col.dtype}
                        </span>
                      </td>
                      <td className={styles.num}>{col.unique_count?.toLocaleString()}</td>
                      <td className={styles.num}>
                        <span style={{ color: col.null_pct > 20 ? 'var(--red)' : 'inherit' }}>
                          {col.null_pct?.toFixed(1)}%
                        </span>
                      </td>
                      <td className={styles.muted}>{col.min_val ?? '—'}</td>
                      <td className={styles.muted}>{col.max_val ?? '—'}</td>
                      <td className={styles.examples}>
                        {col.examples?.slice(0, 3).map((ex, i) => (
                          <span key={i} className={styles.exampleChip}>{String(ex).slice(0, 30)}</span>
                        ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, highlight }) {
  return (
    <div className={styles.card} style={highlight ? { borderColor: 'var(--green)', background: 'var(--green-bg)' } : {}}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
    </div>
  );
}

function Badge({ label, color }) {
  return (
    <span className={styles.badge} style={{ background: color + '1a', color }}>
      {label}
    </span>
  );
}
