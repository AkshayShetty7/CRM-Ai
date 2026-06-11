import React, { useState } from 'react';
import styles from './SqlBlock.module.css';

export default function SqlBlock({ sql }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.bar}>
        <span className={styles.label}>Generated SQL</span>
        <button className={styles.copy} onClick={copy}>{copied ? '✓ Copied' : 'Copy'}</button>
      </div>
      <pre className={styles.pre}><code>{sql}</code></pre>
    </div>
  );
}
