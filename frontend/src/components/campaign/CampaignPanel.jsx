import React, { useState, useEffect } from 'react';
import { createCampaign, previewCampaign, approveCampaign, deleteCampaign } from '../../services/api';
import { useAppContext } from '../../context/AppContext';
import styles from './CampaignPanel.module.css';

export default function CampaignPanel() {


  const { state, setCampaign, setCampaignSent, removeCampaign } = useAppContext();

  const [context, setContext] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const campaigns = Object.values(state.campaigns);

  const handleCreate = async () => {
    if (!context.trim()) return;
    setCreating(true);
    setError('');
    try {
      const campaign = await createCampaign(context.trim());
      setCampaign(campaign);
      setContext('');
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const hasLastData = state.lastResult?.data?.length > 0;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>Email Campaigns</h2>
          <p className={styles.subtitle}>
            Create personalised email campaigns from your query results.
          </p>
        </div>
      </div>

      {/* Create new */}
      <div className={styles.createCard}>
        <div className={styles.createCardTitle}>New Campaign</div>
        {!hasLastData && (
          <div className={styles.notice}>
            <InfoIcon /> Run a query first to select campaign recipients.
          </div>
        )}
        <div className={styles.createRow}>
          <textarea
            className={styles.contextInput}
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="Describe the campaign goal, e.g. 'Inform customers that their warranty expires soon and offer a 20% renewal discount.'"
            rows={3}
          />
          <button
            className={styles.createBtn}
            onClick={handleCreate}
            disabled={creating || !context.trim() || !hasLastData}
          >
            {creating ? 'Generating…' : 'Generate Campaign'}
          </button>
        </div>
        {error && <div className={styles.error}>{error}</div>}
      </div>

      {/* Campaigns list */}
      {campaigns.length === 0 ? (
        <div className={styles.empty}>No campaigns yet. Create one above.</div>
      ) : (
        <div className={styles.list}>
          {campaigns.map((c) => (
            <CampaignCard
              key={c.campaign_id}
              campaign={c}
              onSent={(result) => setCampaignSent(c.campaign_id, result)}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function CampaignCard({ campaign, onSent }) {
  const [preview, setPreview] = useState(null);
  const [selectedRecipient, setSelectedRecipient] = useState(0);
  const [recipientList, setRecipientList] = useState([]);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(campaign.sendResult || null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);
  const [confirmed, setConfirmed] = useState(false);

  const { removeCampaign } = useAppContext();

  const loadPreview = async (idx) => {
    setLoadingPreview(true);

    try {
      const p = await previewCampaign(
        campaign.campaign_id,
        idx
      );

      setPreview(p);
      setSelectedRecipient(idx);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingPreview(false);
    }
  };

  const loadRecipients = async () => {
    const recipients = [];

    for (let i = 0; i < campaign.recipient_count; i++) {
      try {
        const p = await previewCampaign(
          campaign.campaign_id,
          i
        );

        recipients.push({
          index: i,
          email: p.recipient_email,
          name:
            p.recipient_name ||
            p.recipient_email.split('@')[0] ||
            `Recipient ${i + 1}`,
        });
      } catch {}
    }

    setRecipientList(recipients);

    if (recipients.length > 0) {
      await loadPreview(0);
    }
  };

  useEffect(() => {
    loadRecipients();
  }, []);

  const handleSend = async () => {
    if (!confirmed) {
      setConfirmed(true);
      return;
    }

    setSending(true);

    try {
      const result = await approveCampaign(
        campaign.campaign_id
      );

      setSendResult(result);

      onSent(result);

      setConfirmed(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const statusColors = {
    pending_approval: {
      bg: 'var(--amber-bg)',
      color: 'var(--amber)',
    },
    completed: {
      bg: 'var(--green-bg)',
      color: 'var(--green)',
    },
    partial: {
      bg: 'var(--amber-bg)',
      color: 'var(--amber)',
    },
    failed: {
      bg: 'var(--red-bg)',
      color: 'var(--red)',
    },
  };

  const sc =
    statusColors[campaign.status] || {
      bg: 'var(--accent-soft)',
      color: 'var(--ink-3)',
    };

  return (
    <div className={styles.card}>
      <div
        className={styles.cardHeader}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className={styles.cardMeta}>
          <span className={styles.campaignId}>
            #{campaign.campaign_id}
          </span>

          <span
            className={styles.statusBadge}
            style={{
              background: sc.bg,
              color: sc.color,
            }}
          >
            {campaign.status?.replace('_', ' ')}
          </span>

          <span className={styles.recipientCount}>
            {campaign.recipient_count} recipients
          </span>
        </div>

        <ChevronIcon
          dir={expanded ? 'up' : 'down'}
        />
      </div>

      {expanded && (
        <div className={styles.cardBody}>
          <div className={styles.field}>
            <span className={styles.fieldLabel}>
              Subject
            </span>

            <span className={styles.fieldVal}>
              {campaign.subject}
            </span>
          </div>

          {error && (
            <div className={styles.error}>
              {error}
            </div>
          )}

          <div className={styles.previewBar}>
            <select
              className={styles.recipientSelect}
              value={selectedRecipient}
              onChange={async (e) => {
                const idx = Number(
                  e.target.value
                );

                await loadPreview(idx);
              }}
            >
              {recipientList.map((r) => (
                <option
                  key={r.index}
                  value={r.index}
                >
                  {r.name}
                </option>
              ))}
            </select>

            <button
              className={styles.outlineBtn}
              onClick={async () => {
                if (
                  !window.confirm(
                    'Delete this campaign?'
                  )
                )
                  return;

                try {
                  await deleteCampaign(
                    campaign.campaign_id
                  );

                  removeCampaign(
                    campaign.campaign_id
                  );
                } catch (err) {
                  setError(err.message);
                }
              }}
            >
              Delete
            </button>
          </div>

          {loadingPreview && (
            <div>Loading preview...</div>
          )}

          {preview && (
            <div className={styles.previewCard}>
              <div className={styles.previewRow}>
                <span
                  className={styles.previewLabel}
                >
                  To
                </span>

                {preview.recipient_email}
              </div>

              <div className={styles.previewRow}>
                <span
                  className={styles.previewLabel}
                >
                  Subject
                </span>

                {preview.subject}
              </div>

              <pre
                className={styles.previewBody}
              >
                {preview.body}
              </pre>
            </div>
          )}

          {campaign.status ===
            'pending_approval' &&
            !sendResult && (
              <div className={styles.sendArea}>
                {confirmed && (
                  <div
                    className={styles.confirmNote}
                  >
                    ⚠ This will send real
                    emails to{' '}
                    {
                      campaign.recipient_count
                    }{' '}
                    recipients.
                  </div>
                )}

                <button
                  className={`${styles.sendBtn} ${
                    confirmed
                      ? styles.sendBtnDanger
                      : ''
                  }`}
                  onClick={handleSend}
                  disabled={sending}
                >
                  {sending
                    ? 'Sending...'
                    : confirmed
                    ? '⚠ Confirm & Send'
                    : `Send to ${campaign.recipient_count} recipients`}
                </button>
              </div>
            )}

          {sendResult && (
            <div className={styles.resultCard}>
              <div
                className={styles.resultTitle}
              >
                Campaign sent
              </div>

              <div
                className={styles.resultGrid}
              >
                <Stat
                  label="Sent"
                  val={sendResult.sent}
                  color="var(--green)"
                />

                <Stat
                  label="Failed"
                  val={sendResult.failed}
                  color={
                    sendResult.failed > 0
                      ? 'var(--red)'
                      : 'var(--ink-3)'
                  }
                />

                <Stat
                  label="Duplicates"
                  val={
                    sendResult.duplicates
                  }
                />

                <Stat
                  label="Skipped"
                  val={sendResult.skipped}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}



function Stat({ label, val, color }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statVal} style={{ color: color || 'var(--ink)' }}>{val}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}

function InfoIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{flexShrink:0}}>
    <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
  </svg>;
}

function ChevronIcon({ dir }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    style={{ transform: dir === 'up' ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>;
}
