import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import AUDIT_LOG_PATH, SENT_EMAILS_LOG
from models import EmailCampaign, EmailStatus, SchemaSummary


class AuditLogger:

    def _write(self, path: Path, entry: Dict):
        entry["logged_at"] = datetime.now().isoformat()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    # ── Writers ───────────────────────────────────────────────────────────────

    def log_file_upload(self, file_path: str, schema: SchemaSummary):
        self._write(AUDIT_LOG_PATH, {
            "event":        "file_upload",
            "file_path":    file_path,
            "row_count":    schema.row_count,
            "column_count": len(schema.columns),
            "columns":      [c.name for c in schema.columns],
        })

    def log_query(
        self,
        question  : str,
        plan      : Dict,
        sql       : str,
        row_count : int,
        has_error : bool,
    ):
        self._write(AUDIT_LOG_PATH, {
            "event":     "query",
            "question":  question,
            "plan":      plan,
            "sql":       sql,
            "row_count": row_count,
            "has_error": has_error,
        })

    def log_campaign_created(self, campaign: EmailCampaign):
        self._write(AUDIT_LOG_PATH, {
            "event":           "campaign_created",
            "campaign_id":     campaign.campaign_id,
            "recipient_count": campaign.recipient_count,
            "subject":         campaign.subject,
            "status":          campaign.status,
        })

    def log_campaign_sent(self, result: Dict):
        self._write(AUDIT_LOG_PATH, {"event": "campaign_sent", **result})

    def log_email_status(self, status: EmailStatus):
        self._write(SENT_EMAILS_LOG, asdict(status))

    # ── Reader ────────────────────────────────────────────────────────────────

    def get_log(
        self,
        event_type : Optional[str] = None,
        last_n     : int = 50,
    ) -> List[Dict]:
        entries: List[Dict] = []
        if AUDIT_LOG_PATH.exists():
            with open(AUDIT_LOG_PATH, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if event_type is None or e.get("event") == event_type:
                            entries.append(e)
                    except Exception:
                        pass
        return entries[-last_n:]
