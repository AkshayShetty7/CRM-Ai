# AI CRM Agent — Frontend

A professional React dashboard for the AI-powered CRM Agent notebook backend.

---

## Architecture

```
Notebook classes (immutable)
        ↓
  server.py  (thin FastAPI wrapper — new file, does NOT modify notebook)
        ↓ HTTP (localhost:8000)
  React Frontend (this project)
```

The notebook backend is **never modified**. `server.py` imports the notebook's
Python classes and exposes them as REST endpoints. The React frontend talks only
to those endpoints.

---

## Prerequisites

- Python 3.9+
- Node.js 18+
- A Groq API key (`gsk_…`)
- Your CRM data file (`.xlsx`, `.xls`, or `.csv`)

---

## Step 1 — Prepare the Python backend

### 1a. Convert your notebook to a Python script

```bash
jupyter nbconvert --to script your_notebook.ipynb --output crm_agent
```

This produces `crm_agent.py` in the same folder.

> If your notebook has cell magic (`%`, `!`) or `display()` calls, remove them
> from `crm_agent.py` (or wrap in `try/except`). The notebook logic itself must
> not be changed — only the Jupyter-specific boilerplate around it.

### 1b. Install Python dependencies

```bash
pip install fastapi "uvicorn[standard]" python-multipart
# The notebook's own deps (duckdb, pandas, etc.) should already be installed
```

### 1c. Place server.py next to crm_agent.py

```
your-project/
├── crm_agent.py          ← converted from notebook (do not edit logic)
├── server.py             ← the thin FastAPI wrapper (provided)
├── .env                  ← optional: GROQ_API_KEY, GMAIL_ADDRESS, etc.
└── crm-frontend/         ← this React project
```

### 1d. Start the backend

```bash
uvicorn server:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Visit http://localhost:8000/health — you should see `{"status":"ok","agent_ready":false}`.

---

## Step 2 — Start the React frontend

```bash
cd crm-frontend
npm install
npm start
```

The app opens at **http://localhost:3000**.

---

## Step 3 — Use the app

1. **Configure** — Enter your org name, description, and Groq API key on the setup screen.
2. **Upload** — Drop your `.xlsx` / `.csv` file.
3. **Query** — Type natural language questions. The LLM generates a `QueryPlan` JSON; Python builds safe parameterised SQL from it.
4. **Explore** — View the Schema tab to inspect column types, nulls, examples.
5. **Campaign** — After a query, go to Campaigns → describe the goal → Generate → Preview → Send.
6. **Audit** — View the full append-only audit log with filters.

---

## Environment variables

### Backend (`server.py` reads these via python-dotenv)

| Variable            | Required | Description                          |
|---------------------|----------|--------------------------------------|
| `GROQ_API_KEY`      | Yes*     | Groq API key (* or pass in UI)       |
| `GMAIL_ADDRESS`     | No       | Gmail address for sending campaigns  |
| `GMAIL_APP_PASSWORD`| No       | Gmail app password (not your login)  |

### Frontend (`.env`)

| Variable               | Default                    | Description          |
|------------------------|----------------------------|----------------------|
| `REACT_APP_API_URL`    | `http://localhost:8000`    | Backend base URL     |

---

## API endpoints (exposed by server.py)

| Method | Path                                  | Description                        |
|--------|---------------------------------------|------------------------------------|
| GET    | `/health`                             | Health check                       |
| POST   | `/api/init`                           | Initialise the CRM agent           |
| POST   | `/api/upload`                         | Upload Excel/CSV file              |
| GET    | `/api/schema`                         | Get current schema                 |
| POST   | `/api/ask`                            | Natural language query             |
| POST   | `/api/reset`                          | Reset conversation context         |
| POST   | `/api/export`                         | Export results (csv/excel/json)    |
| POST   | `/api/campaign/create`                | Create email campaign (draft)      |
| GET    | `/api/campaign/:id/preview`           | Preview campaign for one recipient |
| POST   | `/api/campaign/:id/approve`           | Approve and send campaign          |
| GET    | `/api/audit`                          | Get audit log entries              |

---

## Project structure

```
crm-frontend/
├── public/
│   └── index.html
├── src/
│   ├── App.jsx
│   ├── index.js
│   ├── index.css               ← design tokens (CSS variables)
│   ├── context/
│   │   └── AppContext.jsx      ← global state (useReducer)
│   ├── services/
│   │   └── api.js              ← all HTTP calls (axios)
│   └── components/
│       ├── layout/
│       │   ├── SetupPage.jsx   ← onboarding (init + upload)
│       │   ├── Dashboard.jsx   ← shell with sidebar
│       │   └── Sidebar.jsx     ← navigation
│       ├── query/
│       │   ├── QueryPanel.jsx  ← NL query input + results
│       │   ├── DataTable.jsx   ← sortable paginated table
│       │   ├── SqlBlock.jsx    ← generated SQL display
│       │   └── PlanViewer.jsx  ← QueryPlan visualiser
│       ├── schema/
│       │   └── SchemaPanel.jsx ← column browser
│       ├── campaign/
│       │   └── CampaignPanel.jsx ← campaign create/preview/send
│       └── audit/
│           └── AuditPanel.jsx  ← audit log viewer
├── .env
├── package.json
└── README.md
```

---

## CORS

`server.py` allows requests from `http://localhost:3000`. For production,
update the `allow_origins` list in `server.py` with your frontend domain.

---

## Notes

- The notebook's Python classes are imported as-is. No logic is changed.
- `server.py` is a **separate** file — it only wraps, never modifies.
- The LLM never generates SQL. The `QueryPlan` JSON → Python `QueryBuilder` → SQL
  pipeline is fully preserved.
- Email sending requires Gmail SMTP credentials set in the backend `.env`.
