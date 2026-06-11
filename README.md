# AI CRM Agent — Full Stack

React frontend + modular Python backend for the AI-powered CRM Agent.

---

## Project structure

```
crm-frontend/
│
├── backend/                     ← Python backend (FastAPI + CRM logic)
│   ├── server.py                ← FastAPI app — HTTP entry point
│   ├── crm_agent.py             ← Top-level CRMAgent orchestrator
│   ├── config.py                ← Env vars, paths, logging
│   ├── models.py                ← Pure dataclasses (no I/O)
│   ├── schema_analyzer.py       ← DataFrame → SchemaSummary
│   ├── db_manager.py            ← DuckDB connection + SQL execution
│   ├── query_plan.py            ← Pydantic QueryPlan models
│   ├── query_plan_generator.py  ← LLM → QueryPlan JSON
│   ├── query_builder.py         ← QueryPlan → safe parameterised SQL
│   ├── query_executor.py        ← Pipeline orchestrator + ConversationContext
│   ├── email_service.py         ← EmailGenerator (LLM) + EmailService (SMTP)
│   ├── audit_logger.py          ← Append-only JSONL audit trail
│   ├── requirements.txt
│   └── .env.example
│
├── src/                         ← React frontend
│   ├── App.jsx
│   ├── index.js / index.css
│   ├── context/AppContext.jsx   ← Global state (useReducer)
│   ├── services/api.js          ← All HTTP calls (axios)
│   └── components/
│       ├── layout/              ← SetupPage, Dashboard, Sidebar
│       ├── query/               ← QueryPanel, DataTable, SqlBlock, PlanViewer
│       ├── schema/              ← SchemaPanel
│       ├── campaign/            ← CampaignPanel
│       └── audit/               ← AuditPanel
│
├── public/index.html
├── package.json
└── .env                         ← REACT_APP_API_URL=http://localhost:8000
```

---

## Backend module dependency graph

```
server.py
  └── crm_agent.py
        ├── config.py          (no deps)
        ├── models.py          (no deps)
        ├── db_manager.py      → config, models, schema_analyzer
        ├── schema_analyzer.py → models
        ├── query_executor.py  → audit_logger, db_manager, query_builder,
        │                         query_plan, query_plan_generator
        ├── query_plan.py      → config
        ├── query_plan_generator.py → config, models, query_plan
        ├── query_builder.py   → db_manager, models, query_plan
        ├── email_service.py   → config, models
        └── audit_logger.py    → config, models
```

---

## Quick start

### 1 — Backend

```bash
cd backend
cp .env.example .env
# Edit .env — add GROQ_API_KEY (and optionally GMAIL_* for email campaigns)

pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

Health check: http://localhost:8000/health → `{"status":"ok","agent_ready":false}`
Auto docs:    http://localhost:8000/docs

### 2 — Frontend

```bash
# from the crm-frontend/ root
npm install
npm start          # opens http://localhost:3000
```

### 3 — Use

1. **Configure** — Enter org name, description, Groq API key on the setup screen.
2. **Upload** — Drop your `.xlsx` / `.csv` file.
3. **Query** — Ask questions in plain English. Results appear with generated SQL and QueryPlan.
4. **Schema** — Browse column types, nulls, and example values.
5. **Campaigns** — Generate → Preview → Approve → Send personalised email campaigns.
6. **Audit** — View the full append-only activity log.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/health` | Health check |
| POST | `/api/init` | Initialise agent (org + API key) |
| POST | `/api/upload` | Upload .xlsx/.xls/.csv |
| GET  | `/api/schema` | Current schema |
| POST | `/api/ask` | Natural language query |
| POST | `/api/reset` | Reset conversation context |
| POST | `/api/export` | Download results (csv/excel/json) |
| POST | `/api/campaign/create` | Generate campaign draft |
| GET  | `/api/campaign/:id/preview` | Preview one recipient |
| POST | `/api/campaign/:id/approve` | Approve and send |
| GET  | `/api/audit` | Audit log (filterable) |

---

## Environment variables

### `backend/.env`
| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key (`gsk_…`) |
| `GMAIL_ADDRESS` | No | Gmail sender address |
| `GMAIL_APP_PASSWORD` | No | Gmail app password |

### `crm-frontend/.env`
| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend URL |
