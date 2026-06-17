import React, { useState, useRef } from 'react';
import { initAgent, uploadFile } from '../../services/api';
import { useAppContext } from '../../context/AppContext';
import styles from './SetupPage.module.css';

export default function SetupPage() {
  const { setAgentReady, setSchema } = useAppContext();

  const [step, setStep] = useState(1); // 1 = config, 2 = upload
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    org_name: '',
    org_description: '',
    support_number: '1800-000-0000',
    email_id: 'support@example.com',
  });

  const [file, setFile] = useState(null);
  const fileRef = useRef();

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleInit = async (e) => {
    e.preventDefault();
    if (!form.org_name.trim()) {
  setError('Organisation Name is required.');
  return;
}
    setError('');
    setLoading(true);
    try {
      await initAgent(form);
      setAgentReady(form.org_name);
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setError('');
    setLoading(true);
    try {
      const schema = await uploadFile(file);
      setSchema(schema);
      setAgentReady(form.org_name);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        {/* Logo / brand */}
        <div className={styles.brand}>
          <span className={styles.dot} />
          <span className={styles.brandName}>CRM Agent</span>
        </div>

        {step === 1 && (
          <>
            <h1 className={styles.heading}>Configure your agent</h1>
            <p className={styles.sub}> Describe your organisation.</p>

            <form onSubmit={handleInit} className={styles.form}>
              <Field label="Organisation Name" required>
                <input name="org_name" value={form.org_name} onChange={handleChange} placeholder="Acme Corp" />
              </Field>
              <Field label="Description">
                <textarea name="org_description" value={form.org_description} onChange={handleChange}
                  rows={2} placeholder="What does your organisation do?" />
              </Field>
              <div className={styles.row2}>
                <Field label="Support Number">
                  <input name="support_number" value={form.support_number} onChange={handleChange} />
                </Field>
                <Field label="Support Email">
                  <input name="email_id" value={form.email_id} onChange={handleChange} type="email" />
                </Field>
              </div>
             

              {error && <p className={styles.error}>{error}</p>}

              <button type="submit" className={styles.btn} disabled={loading}>
                {loading ? 'Initialising…' : 'Continue →'}
              </button>
            </form>
          </>
        )}

        {step === 2 && (
          <>
            <h1 className={styles.heading}>Upload your data</h1>
            <p className={styles.sub}>Supports .xlsx, .xls, and .csv files.</p>

            <div
              className={`${styles.dropzone} ${file ? styles.dropzoneFilled : ''}`}
              onClick={() => fileRef.current.click()}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              <input
                ref={fileRef} type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: 'none' }}
                onChange={(e) => setFile(e.target.files[0])}
              />
              {file ? (
                <>
                  <FileIcon />
                  <span className={styles.filename}>{file.name}</span>
                  <span className={styles.filesize}>{(file.size / 1024).toFixed(1)} KB</span>
                </>
              ) : (
                <>
                  <UploadIcon />
                  <span>Drop file here or <strong>browse</strong></span>
                  <span className={styles.hint}>.xlsx · .xls · .csv</span>
                </>
              )}
            </div>

            {error && <p className={styles.error}>{error}</p>}

            <button
              className={styles.btn}
              disabled={!file || loading}
              onClick={handleUpload}
            >
              {loading ? 'Loading data…' : 'Load Data →'}
            </button>

            <button className={styles.skip} onClick={() => setAgentReady(form.org_name)}>
              Skip — no file yet
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--ink-3)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        {label}{required && <span style={{ color: 'var(--red)', marginLeft: 2 }}>*</span>}
      </span>
      {children}
    </label>
  );
}

function UploadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--ink-4)" strokeWidth="1.5">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
    </svg>
  );
}
