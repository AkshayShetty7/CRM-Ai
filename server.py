"""
server.py — Thin FastAPI wrapper around the CRMAgent notebook backend.
This file does NOT modify any notebook logic. It only imports the existing
classes and exposes them as HTTP endpoints.

Run:
    pip install fastapi uvicorn python-multipart
    uvicorn server:app --reload --port 8000
"""

import os
import sys
import json
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ── Import the notebook's classes (assumes notebook cells were extracted to crm_agent.py)
# The user should run:  jupyter nbconvert --to script their_notebook.ipynb --output crm_agent
# Then this import works:
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Attempt to import from a converted .py version of the notebook
    from crm_agent import (
        CRMAgent, QueryPlan, FilterCondition, AggregationSpec, SortSpec,
        AuditLogger, EXPORT_DIR, DEFAULT_QUERY_LIMIT,
    )
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

app = FastAPI(title="AI CRM Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singleton agent (initialized on first /init call) ─────────────────────────
_agent: Optional[Any] = None


# ── Request Models ─────────────────────────────────────────────────────────────

class InitRequest(BaseModel):
    org_name: str
    org_description: str
    support_number: str = "1800-000-0000"
    email_id: str = "support@example.com"
    groq_api_key: str


class AskRequest(BaseModel):
    question: str


class CampaignRequest(BaseModel):
    context: str
    recipient_indices: Optional[List[int]] = None  # if None → use last_data


class ApproveCampaignRequest(BaseModel):
    campaign_id: str


class ExportRequest(BaseModel):
    fmt: str = "csv"  # csv | excel | json


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "agent_ready": _agent is not None,
        "backend_available": AGENT_AVAILABLE,
    }


# ── Init ───────────────────────────────────────────────────────────────────────

@app.post("/api/init")
def init_agent(req: InitRequest):
    global _agent
    if not AGENT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Backend classes not found. "
                "Convert the notebook: "
                "jupyter nbconvert --to script your_notebook.ipynb --output crm_agent"
            ),
        )
    try:
        _agent = CRMAgent(
            org_name=req.org_name,
            org_description=req.org_description,
            support_number=req.support_number,
            email_id=req.email_id,
            groq_api_key=req.groq_api_key,
        )
        return {"status": "initialized", "org_name": req.org_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── File Upload ────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    _require_agent()
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, .csv files are supported.")

    tmp_path = Path(f"/tmp/crm_upload{suffix}")
    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        schema = _agent.load_file(str(tmp_path))
        return {
            "status": "loaded",
            "row_count": schema.row_count,
            "column_count": len(schema.columns),
            "email_column": schema.email_column,
            "name_column": schema.name_column,
            "date_columns": schema.date_columns,
            "columns": [
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "null_pct": c.null_pct,
                    "unique_count": c.unique_count,
                    "examples": c.examples,
                    "min_val": c.min_val,
                    "max_val": c.max_val,
                }
                for c in schema.columns
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Query ──────────────────────────────────────────────────────────────────────

@app.post("/api/ask")
def ask(req: AskRequest):
    _require_agent()
    try:
        result = _agent.ask(req.question, verbose=False)
        if "error" in result:
            return JSONResponse(status_code=422, content={"error": result["error"], "plan": result.get("plan")})
        return {
            "row_count": result.get("row_count", 0),
            "columns": result.get("columns", []),
            "data": result.get("data", []),
            "sql": result.get("sql", ""),
            "plan": result.get("plan", {}),
            "intent_summary": result.get("intent_summary", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reset")
def reset_conversation():
    _require_agent()
    _agent.reset_conversation()
    return {"status": "reset"}


# ── Schema ─────────────────────────────────────────────────────────────────────

@app.get("/api/schema")
def get_schema():
    _require_agent()
    if not _agent.db.schema:
        raise HTTPException(status_code=404, detail="No data loaded.")
    schema = _agent.db.schema
    return {
        "table_name": schema.table_name,
        "row_count": schema.row_count,
        "email_column": schema.email_column,
        "name_column": schema.name_column,
        "date_columns": schema.date_columns,
        "columns": [
            {
                "name": c.name,
                "dtype": c.dtype,
                "null_pct": c.null_pct,
                "unique_count": c.unique_count,
                "examples": c.examples,
                "min_val": c.min_val,
                "max_val": c.max_val,
            }
            for c in schema.columns
        ],
    }


# ── Export ─────────────────────────────────────────────────────────────────────

@app.post("/api/export")
def export_results(req: ExportRequest):
    _require_agent()
    if req.fmt not in ("csv", "excel", "json"):
        raise HTTPException(status_code=400, detail="fmt must be csv, excel, or json.")
    try:
        path = _agent.export(req.fmt)
        return FileResponse(
            str(path),
            filename=path.name,
            media_type="application/octet-stream",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Email Campaigns ────────────────────────────────────────────────────────────

@app.post("/api/campaign/create")
def create_campaign(req: CampaignRequest):
    _require_agent()
    try:
        recipients = None
        if req.recipient_indices is not None:
            last = _agent.executor.ctx.last_data
            recipients = [last[i] for i in req.recipient_indices if i < len(last)]

        campaign = _agent.create_campaign(context=req.context, recipients=recipients)
        return {
            "campaign_id": campaign.campaign_id,
            "org_name": campaign.org_name,
            "subject": campaign.subject,
            "body_template": campaign.body_template,
            "recipient_count": campaign.recipient_count,
            "status": campaign.status,
            "created_at": campaign.created_at,
        }
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/campaign/{campaign_id}/preview")
def preview_campaign(campaign_id: str, recipient_index: int = 0):
    _require_agent()
    campaign = _get_campaign(campaign_id)
    try:
        preview = _agent.preview_campaign(campaign, recipient_index)
        email_col = _agent.db.schema.email_column if _agent.db.schema else None
        recipient = campaign.recipients[recipient_index] if recipient_index < len(campaign.recipients) else {}
        return {
            "subject": preview["subject"],
            "body": preview["body"],
            "recipient_email": recipient.get(email_col, "") if email_col else "",
            "recipient_index": recipient_index,
            "total_recipients": campaign.recipient_count,
        }
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/campaign/{campaign_id}/approve")
def approve_and_send(campaign_id: str):
    _require_agent()
    campaign = _get_campaign(campaign_id)
    try:
        result = _agent.approve_and_send(campaign)
        return result
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Audit Log ──────────────────────────────────────────────────────────────────

@app.get("/api/audit")
def get_audit_log(event_type: Optional[str] = None, last_n: int = 50):
    _require_agent()
    try:
        logs = _agent.get_audit_log(event_type=event_type, last_n=last_n)
        return {"entries": logs, "count": len(logs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_agent():
    if _agent is None:
        raise HTTPException(status_code=400, detail="Agent not initialized. POST /api/init first.")


def _get_campaign(campaign_id: str):
    campaign = _agent.db._campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")
    return campaign
