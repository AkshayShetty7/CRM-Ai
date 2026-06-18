# AI CRM Agent

An AI-powered CRM application that allows businesses to upload customer data, ask questions in natural language, generate insights, and create personalized email campaigns.

The system uses Large Language Models (LLMs) to convert user questions into database queries, making customer data accessible without writing SQL.

---

## Features

- Upload customer datasets (`.csv`, `.xlsx`, `.xls`)
- Query data using plain English
- Automatic SQL generation
- Schema analysis and data profiling
- AI-generated email campaigns
- Personalized email previews
- Send campaigns through SendGrid
- Audit logging for transparency
- Export results as CSV, Excel, or JSON

---

## Project Structure

```text
crm-frontend/
│
├── backend/
│   ├── server.py
│   ├── crm_agent.py
│   ├── config.py
│   ├── models.py
│   ├── schema_analyzer.py
│   ├── db_manager.py
│   ├── query_plan.py
│   ├── query_plan_generator.py
│   ├── query_builder.py
│   ├── query_executor.py
│   ├── email_service.py
│   ├── audit_logger.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── context/
│   │   ├── services/
│   │   └── components/
│   │
│   └── public/
│
├── package.json
└── README.md
```

---

## Technology Stack

### Frontend

- React

### Backend

- FastAPI
- DuckDB
- Pandas
- LangChain
- Groq LLM
- SendGrid

### Deployment

- Frontend: Vercel
- Backend: Render

---



---

## How to Use

### 1. Configure Agent

Enter:

- Organization Name
- Organization Description
- Support Number
- Support Email

### 2. Upload Dataset

Supported formats:

```text
.csv
.xlsx
.xls
```

### 3. Query Data

Example questions:

```text
Show customers whose warranty expires within 30 days

List customers who purchased an iPhone

Show total revenue by product
```

The AI automatically generates and executes SQL.

### 4. Create Campaign

Generate personalized email campaigns based on query results.

### 5. Preview Campaign

Review generated content before sending.

### 6. Send Campaign

Emails are delivered through SendGrid.

### 7. Export Results

Export data as:

```text
CSV
Excel
JSON
```

---

## API Endpoints

| Method | Endpoint | Description |
|----------|----------|----------|
| GET | `/health` | Health check |
| POST | `/api/init` | Initialize CRM Agent |
| POST | `/api/upload` | Upload dataset |
| GET | `/api/schema` | Get schema summary |
| POST | `/api/ask` | Ask a natural language question |
| POST | `/api/reset` | Reset conversation |
| POST | `/api/export` | Export results |
| POST | `/api/campaign/create` | Create email campaign |
| GET | `/api/campaign/{id}/preview` | Preview campaign |
| POST | `/api/campaign/{id}/approve` | Send campaign |
| DELETE | `/api/campaign/{id}` | Delete campaign |
| DELETE | `/api/dataset` | Remove uploaded dataset |
| GET | `/api/audit` | View audit logs |

---

## Environment Variables

### Backend (`.env`)

```env
GROQ_API_KEY=your_groq_key

SENDGRID_API_KEY=your_sendgrid_key

FROM_EMAIL=verified_sender@example.com
```

---


## Live Demo

Frontend:
https://crm-ai-kappa.vercel.app/

Backend:
https://crm-ai-x5gw.onrender.com

