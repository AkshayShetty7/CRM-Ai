import React, { useState, useRef, useEffect } from 'react';
import { ask, resetConversation, exportResults } from '../../services/api';
import { useAppContext } from '../../context/AppContext';
import DataTable from './DataTable';
import SqlBlock from './SqlBlock';
import PlanViewer from './PlanViewer';
import styles from './QueryPanel.module.css';

const SUGGESTIONS = [
  'Show me all customers',
  'Customers whose warranty expires in the next 30 days',
  'How many customers per city, sorted by count descending?',
  'Show customers who bought Samsung products',
  'Top 10 customers by purchase amount',
];

export default function QueryPanel() {
  const { state, setQueryResult, setTab, setCampaign } = useAppContext();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [creatingCampaign, setCreatingCampaign] = useState(false);
  const [showPlan, setShowPlan] = useState(false);
  const inputRef = useRef();

  const result = state.lastResult;
  const hasData = result && result.data && result.data.length > 0;

  const handleAsk = async (q) => {
    const text = (q || question).trim();
    if (!text) return;
    setError('');
    setLoading(true);
    try {
      const res = await ask(text);
      if (res.error) {
        setError(res.error);
      } else {
        setQueryResult(text, res);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  

  const handleExport = async (fmt) => {
    setExporting(true);
    try {
      await exportResults(fmt);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>Query</h2>
          <p className={styles.subtitle}>Ask questions about your data in plain English.</p>
        </div>
        
      </div>

      {/* Input */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <textarea
            ref={inputRef}
            className={styles.textarea}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Show customers from Bangalore who bought a TV in the last 30 days"
            rows={2}
          />
          <button
            className={styles.askBtn}
            onClick={() => handleAsk()}
            disabled={loading || !question.trim()}
          >
            {loading ? <Spinner /> : <SendIcon />}
          </button>
        </div>
        {/* Suggestions */}
        {!hasData && (
          <div className={styles.suggestions}>
            {SUGGESTIONS.map((s) => (
              <button key={s} className={styles.chip} onClick={() => { setQuestion(s); handleAsk(s); }}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <div className={styles.error}><AlertIcon />{error}</div>}

      {/* Results */}
      {result && !error && (
        <div className={styles.results}>
          {/* Meta row */}
          <div className={styles.metaRow}>
            <div className={styles.intentBadge}>{result.intent_summary || 'Query result'}</div>
            <div className={styles.metaRight}>
              <span className={styles.rowCount}>
                {result.row_count?.toLocaleString()} row{result.row_count !== 1 ? 's' : ''}
              </span>
              <button className={styles.textBtn} onClick={() => setShowPlan((v) => !v)}>
                {showPlan ? 'Hide' : 'Show'} plan
              </button>
            </div>
          </div>

          {showPlan && result.plan && (
            <div className={styles.planWrap}>
              <PlanViewer plan={result.plan} />
              {result.sql && <SqlBlock sql={result.sql} />}
            </div>
          )}

          {hasData ? (
            <>
              <DataTable columns={result.columns} data={result.data} />

              <div className={styles.actions}>
                <div className={styles.exportBtns}>
                  <span className={styles.actionLabel}>Export:</span>
                  {['csv', 'excel', 'json'].map((fmt) => (
                    <button key={fmt} className={styles.exportBtn} onClick={() => handleExport(fmt)} disabled={exporting}>
                      .{fmt === 'excel' ? 'xlsx' : fmt}
                    </button>
                  ))}
                </div>
                <button
                  className={styles.campaignBtn}
                  onClick={async () => {
                    setCreatingCampaign(true);
                    try {
                      const { createCampaign } = await import('../../services/api');
                      const campaign = await createCampaign(`Campaign based on: ${state.queryHistory[0]?.question || 'last query'}`);
                      setCampaign(campaign);
                      setTab('campaign');
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setCreatingCampaign(false);
                    }
                  }}
                  disabled={creatingCampaign}
                >
                  {creatingCampaign ? 'Creating…' : '✉ Create email campaign'}
                </button>
              </div>
            </>
          ) : (
            <div className={styles.empty}>No rows returned.</div>
          )}
        </div>
      )}

      {/* History */}
      {state.queryHistory.length > 1 && (
        <div className={styles.historySection}>
          <p className={styles.historyTitle}>Recent queries</p>
          <div className={styles.history}>
            {state.queryHistory.slice(1, 6).map((h, i) => (
              <button key={i} className={styles.historyItem} onClick={() => { setQuestion(h.question); handleAsk(h.question); }}>
                <HistoryIcon />
                <span>{h.question}</span>
                <span className={styles.historyRows}>{h.result?.row_count ?? 0} rows</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return <span className={styles.spinner} />;
}
function SendIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>;
}
function ResetIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
  </svg>;
}
function AlertIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{flexShrink:0}}>
    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>;
}
function HistoryIcon() {
  return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{flexShrink:0}}>
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>;
}
