"""
models.py
Pure data containers — dataclasses only.
No business logic, no I/O, no LLM calls.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Organisation ──────────────────────────────────────────────────────────────
@dataclass
class Organization:
    name: str
    description: str
    support_number: str = "1800-000-0000"
    email_id: str = "support@example.com"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Column Metadata ───────────────────────────────────────────────────────────
@dataclass
class ColumnMeta:
    name: str
    dtype: str          # 'text' | 'integer' | 'float' | 'date' | 'datetime' | 'boolean'
    null_pct: float
    unique_count: int
    examples: List[Any]
    min_val: Any = None
    max_val: Any = None


# ── Schema Summary ────────────────────────────────────────────────────────────
@dataclass
class SchemaSummary:
    table_name: str
    row_count: int
    columns: List[ColumnMeta]
    email_column: Optional[str]
    name_column: Optional[str]
    date_columns: List[str]

    def to_llm_context(self) -> str:
        """Compact schema string sent to the LLM."""
        lines = [
            f"TABLE: {self.table_name} ({self.row_count:,} rows)",
            f"COLUMNS ({len(self.columns)}):",
        ]
        for c in self.columns:
            ex = ", ".join(str(e) for e in c.examples[:3])
            lines.append(f'  - "{c.name}" [{c.dtype}]  examples: {ex}')
        if self.date_columns:
            lines.append(f"DATE COLUMNS: {self.date_columns}")
        return "\n".join(lines)


# ── Email Campaign ─────────────────────────────────────────────────────────────
@dataclass
class EmailCampaign:
    campaign_id: str
    org_name: str
    query_description: str
    recipient_count: int
    subject: str
    body_template: str
    recipients: List[Dict]
    status: str = "draft"   # draft | pending_approval | sending | completed | partial | failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sent_emails: List[Dict] = field(default_factory=list)
    failed_emails: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


# ── Email Status ───────────────────────────────────────────────────────────────
@dataclass
class EmailStatus:
    email: str
    status: str       # sent | failed | duplicate | skipped
    timestamp: str
    campaign_id: str
    error: Optional[str] = None
