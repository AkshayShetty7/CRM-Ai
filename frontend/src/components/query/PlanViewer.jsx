import React from 'react';
import styles from './PlanViewer.module.css';

export default function PlanViewer({ plan }) {
  if (!plan) return null;
  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <span className={styles.label}>Query Plan</span>
        <span className={styles.op}>{plan.operation}</span>
      </div>
      <div className={styles.body}>
        {plan.filters?.length > 0 && (
          <Section title="Filters">
            {plan.filters.map((f, i) => (
              <div key={i} className={styles.filter}>
                {i > 0 && <span className={styles.logic}>{f.logic}</span>}
                <span className={styles.col}>{f.column}</span>
                <span className={styles.op2}>{f.operator}</span>
                {f.value != null && <span className={styles.val}>"{String(f.value)}"</span>}
                {f.value2 != null && <><span className={styles.op2}>→</span><span className={styles.val}>"{String(f.value2)}"</span></>}
              </div>
            ))}
          </Section>
        )}
        {plan.aggregations?.length > 0 && (
          <Section title="Aggregations">
            {plan.aggregations.map((a, i) => (
              <div key={i} className={styles.filter}>
                <span className={styles.op2}>{a.function.toUpperCase()}</span>
                <span className={styles.col}>{a.column}</span>
                {a.alias && <><span className={styles.op2}>as</span><span className={styles.val}>{a.alias}</span></>}
              </div>
            ))}
          </Section>
        )}
        {plan.group_by?.length > 0 && (
          <Section title="Group By">
            <div className={styles.filter}>{plan.group_by.map((c) => <span key={c} className={styles.col}>{c}</span>)}</div>
          </Section>
        )}
        {plan.sort?.length > 0 && (
          <Section title="Sort">
            {plan.sort.map((s, i) => (
              <div key={i} className={styles.filter}>
                <span className={styles.col}>{s.column}</span>
                <span className={styles.op2}>{s.direction}</span>
              </div>
            ))}
          </Section>
        )}
        <div className={styles.meta}>
          <span>Limit: <strong>{plan.limit}</strong></span>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}
