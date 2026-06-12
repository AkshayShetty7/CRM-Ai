import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ── Response interceptor for consistent error shape ───────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.error ||
      err.message ||
      'Unknown error';
    return Promise.reject(new Error(message));
  }
);

// ── Health ─────────────────────────────────────────────────────────────────────
export const checkHealth = () => api.get('/health').then((r) => r.data);

// ── Init ───────────────────────────────────────────────────────────────────────
export const initAgent = (payload) =>
  api.post('/api/init', payload).then((r) => r.data);

// ── Upload ─────────────────────────────────────────────────────────────────────
export const uploadFile = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api
    .post('/api/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    .then((r) => r.data);
};

export const deleteDataset = () =>
  api.delete('/api/dataset').then((r) => r.data);

// ── Schema ─────────────────────────────────────────────────────────────────────
export const getSchema = () => api.get('/api/schema').then((r) => r.data);

// ── Query ──────────────────────────────────────────────────────────────────────
export const ask = (question) =>
  api.post('/api/ask', { question }).then((r) => r.data);

export const resetConversation = () =>
  api.post('/api/reset').then((r) => r.data);

// ── Export ─────────────────────────────────────────────────────────────────────
export const exportResults = async (fmt = 'csv') => {
  const res = await api.post(
    '/api/export',
    { fmt },
    { responseType: 'blob' }
  );
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  const ext = fmt === 'excel' ? 'xlsx' : fmt;
  link.setAttribute('download', `export.${ext}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ── Campaign ───────────────────────────────────────────────────────────────────
export const createCampaign = (context) =>
  api.post('/api/campaign/create', { context }).then((r) => r.data);

export const previewCampaign = (campaignId, recipientIndex = 0) =>
  api
    .get(`/api/campaign/${campaignId}/preview`, { params: { recipient_index: recipientIndex } })
    .then((r) => r.data);

export const approveCampaign = (campaignId) =>
  api.post(`/api/campaign/${campaignId}/approve`).then((r) => r.data);

// ── Audit ──────────────────────────────────────────────────────────────────────
export const getAuditLog = (eventType = null, lastN = 50) =>
  api
    .get('/api/audit', { params: { event_type: eventType || undefined, last_n: lastN } })
    .then((r) => r.data);

export default api;
