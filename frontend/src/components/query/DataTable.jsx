import React, { useState, useMemo } from 'react';
import styles from './DataTable.module.css';

const MAX_ROWS_SHOWN = 100;

export default function DataTable({ columns = [], data = [] }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
    setPage(0);
  };

  const sorted = useMemo(() => {
    if (!sortCol) return data;
    return [...data].sort((a, b) => {
      const va = a[sortCol]; const vb = b[sortCol];
      if (va == null) return 1; if (vb == null) return -1;
      const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [data, sortCol, sortDir]);

  const pageData = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  if (!columns.length) return null;

  return (
    <div className={styles.wrap}>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} onClick={() => handleSort(col)} className={styles.th}>
                  <span>{col}</span>
                  {sortCol === col && (
                    <span className={styles.sortArrow}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, i) => (
              <tr key={i} className={styles.tr}>
                {columns.map((col) => {
                  const val = row[col];
                  return (
                    <td key={col} className={styles.td}>
                      <span title={val != null ? String(val) : ''}>
                        {formatCell(val)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button onClick={() => setPage(0)} disabled={page === 0}>«</button>
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>‹</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>›</button>
          <button onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1}>»</button>
          <span className={styles.total}>{data.length.toLocaleString()} rows total</span>
        </div>
      )}
    </div>
  );
}

function formatCell(val) {
  if (val == null) return <span style={{color:'var(--ink-4)'}}>—</span>;
  const s = String(val);
  if (s.length > 60) return s.slice(0, 60) + '…';
  return s;
}
