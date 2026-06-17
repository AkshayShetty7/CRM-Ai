import sys
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Dict, List, Optional
import math
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from config import logger

# ── Make sure sibling modules are importable ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from crm_agent import CRMAgent  # noqa: E402  (must come after sys.path tweak)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="AI CRM Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000","https://crm-ai-kappa.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton agent — created on POST /api/init
_agent: Optional[CRMAgent] = None


# ── Request schemas ───────────────────────────────────────────────────────────
class InitRequest(BaseModel):
    org_name: str
    org_description: str
    support_number: str = "1800-000-0000"
    email_id: str = "support@example.com"


class AskRequest(BaseModel):
    question: str


class CampaignRequest(BaseModel):
    context: str


class ExportRequest(BaseModel):
    fmt: str = "csv"   # csv | excel | json


# ── Helpers ───────────────────────────────────────────────────────────────────
def _require_agent() -> CRMAgent:
    if _agent is None:
        raise HTTPException(
            status_code=400,
            detail="Agent not initialised. POST /api/init first.",
        )
    return _agent


def _get_campaign(agent: CRMAgent, campaign_id: str):
    campaign = agent.db._campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")
    return campaign


def _serialise_schema(schema) -> Dict:
    return {
        "status":        "loaded",
        "row_count":     schema.row_count,
        "column_count":  len(schema.columns),
        "email_column":  schema.email_column,
        "name_column":   schema.name_column,
        "date_columns":  schema.date_columns,
        "columns": [
            {
                "name":         c.name,
                "dtype":        c.dtype,
                "null_pct":     c.null_pct,
                "unique_count": c.unique_count,
                "examples":     c.examples,
                "min_val":      c.min_val,
                "max_val":      c.max_val,
            }
            for c in schema.columns
        ],
    }

def clean_nan(obj):
    if obj is None:
        return None

    try:
        if math.isnan(obj):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]

    return obj

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "agent_ready": _agent is not None}


# ── Init ──────────────────────────────────────────────────────────────────────
@app.post("/api/init")
def init_agent(req: InitRequest):
    global _agent
    try:
        _agent = CRMAgent(
            org_name        = req.org_name,
            org_description = req.org_description,
            support_number  = req.support_number,
            email_id        = req.email_id,
        )
        return {"status": "initialized", "org_name": req.org_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── File upload ───────────────────────────────────────────────────────────────


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    agent = _require_agent()

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx, .xls, .csv files supported."
        )

    tmp_path = Path(gettempdir()) / f"crm_upload{suffix}"

    tmp_path.write_bytes(await file.read())

    try:
        schema = agent.load_file(str(tmp_path))
        return _serialise_schema(schema)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Schema ────────────────────────────────────────────────────────────────────
@app.get("/api/schema")
def get_schema():
    agent = _require_agent()
    if not agent.db.schema:
        raise HTTPException(status_code=404, detail="No data loaded.")
    return _serialise_schema(agent.db.schema)


# ── Query ─────────────────────────────────────────────────────────────────────
@app.post("/api/ask")
def ask(req: AskRequest):
    agent  = _require_agent()
    result = agent.ask(req.question)

    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"error": result["error"], "plan": result.get("plan")},
        )
    response = {
    "row_count": result.get("row_count", 0),
    "columns": result.get("columns", []),
    "data": result.get("data", []),
    "sql": result.get("sql", ""),
    "plan": result.get("plan", {}),
    "intent_summary": result.get("intent_summary", ""),
}
    import json

    try:
        json.dumps(response, allow_nan=False)
    except Exception as e:
        logger.error(f"JSON ERROR: {e}")
        logger.error(str(response))
    return clean_nan(response)

@app.post("/api/reset")
def reset_conversation():
    _require_agent().reset_conversation()
    return {"status": "reset"}


# ── Export ────────────────────────────────────────────────────────────────────
@app.post("/api/export")
def export_results(req: ExportRequest):
    agent = _require_agent()
    if req.fmt not in ("csv", "excel", "json"):
        raise HTTPException(status_code=400, detail="fmt must be csv, excel, or json.")
    try:
        path = agent.export(req.fmt)
        return FileResponse(str(path), filename=path.name, media_type="application/octet-stream")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Campaigns ─────────────────────────────────────────────────────────────────
@app.post("/api/campaign/create")
def create_campaign(req: CampaignRequest):
    agent = _require_agent()
    try:
        campaign = agent.create_campaign(context=req.context)
        return {
            "campaign_id":     campaign.campaign_id,
            "org_name":        campaign.org_name,
            "subject":         campaign.subject,
            "body_template":   campaign.body_template,
            "recipient_count": campaign.recipient_count,
            "status":          campaign.status,
            "created_at":      campaign.created_at,
            "warning": getattr(campaign, "warning", None),
        }
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/api/campaign/{campaign_id}/preview")
def preview_campaign(campaign_id: str, recipient_index: int = 0):
    agent = _require_agent()
    campaign = _get_campaign(agent, campaign_id)

    try:
        preview = agent.preview_campaign(campaign, recipient_index)

        email_col = (
            agent.db.schema.email_column
            if agent.db.schema else None
        )

        name_col = (
            agent.db.schema.name_column
            if agent.db.schema else None
        )

        recipient = (
            campaign.recipients[recipient_index]
            if recipient_index < len(campaign.recipients)
            else {}
        )

        return {
            "recipient_name": recipient.get(name_col, "") if name_col else "",
            "subject": preview["subject"],
            "body": preview["body"],
            "recipient_email": recipient.get(email_col, "") if email_col else "",
            "recipient_index": recipient_index,
            "total_recipients": campaign.recipient_count,
        }

    except IndexError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )
    

@app.delete("/api/dataset")
def delete_dataset():

    global _uploaded_file_loaded

    agent = _require_agent()

    agent.db.clear_data()

    for ext in [".xlsx", ".xls", ".csv"]:

        path = Path(gettempdir()) / f"crm_upload{ext}"

        if path.exists():
            path.unlink()

    _uploaded_file_loaded = False

    return {
        "status": "deleted"
    }


    
@app.delete("/api/campaign/{campaign_id}")
def delete_campaign(campaign_id: str):
    agent = _require_agent()

    campaign = agent.db._campaigns.get(campaign_id)

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found"
        )

    del agent.db._campaigns[campaign_id]

    return {
        "status": "deleted",
        "campaign_id": campaign_id
    }


@app.post("/api/campaign/{campaign_id}/approve")
def approve_and_send(campaign_id: str):
    agent    = _require_agent()
    campaign = _get_campaign(agent, campaign_id)
    try:
        return agent.approve_and_send(campaign)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Audit ─────────────────────────────────────────────────────────────────────
@app.get("/api/audit")
def get_audit_log(event_type: Optional[str] = None, last_n: int = 50):
    agent = _require_agent()
    try:
        logs = agent.get_audit_log(event_type=event_type or None, last_n=last_n)
        return {"entries": logs, "count": len(logs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
