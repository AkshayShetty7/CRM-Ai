import uuid
from pathlib import Path
from typing import Dict, List, Literal, Optional
from langchain_groq import ChatGroq

from audit_logger import AuditLogger
from config import (
    DEFAULT_MODEL,SENDGRID_API_KEY,FROM_EMAIL,GROQ_API_KEY,LLM_MAX_TOKENS,LLM_TEMPERATURE,logger,
)
from db_manager import DuckDBManager
from email_service import EmailGenerator, EmailService
from models import EmailCampaign, Organization, SchemaSummary
from query_executor import QueryExecutor
from query_plan_generator import QueryPlanGenerator


class CRMAgent:
    def __init__(
        self,
        org_name        : str,
        org_description : str,
        support_number  : str = "1800-000-0000",
        email_id        : str = "support@example.com",
        model           : str = DEFAULT_MODEL,
    ):
        self.org = Organization(
            name           = org_name,
            description    = org_description,
            support_number = support_number,
            email_id       = email_id,
        )

        self.db    = DuckDBManager()
        self.audit = AuditLogger()

       

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")

        self.llm = ChatGroq(
            model=model,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            groq_api_key=GROQ_API_KEY,
        )

        logger.info("Using Render environment Groq API key")

        plan_gen      = QueryPlanGenerator(self.llm)
        self.executor = QueryExecutor(self.db, plan_gen, self.audit)

        self.email_gen    : Optional[EmailGenerator] = None
        self.email_service: Optional[EmailService]   = None

        if SENDGRID_API_KEY and FROM_EMAIL:
            self.email_gen = EmailGenerator(self.llm, self.org)
            self.email_service = EmailService(
                SENDGRID_API_KEY,
                FROM_EMAIL,
            )

        logger.info(f"CRMAgent initialized for '{org_name}' with model '{model}'")

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_file(self, path: str) -> SchemaSummary:
        """Load an Excel or CSV file. Must be called before ask()."""
        schema = self.db.load_file(path)
        self.audit.log_file_upload(path, schema)
        if self.llm and not self.email_gen:
            self.email_gen = EmailGenerator(self.llm, self.org)
        return schema

    # ── Querying ──────────────────────────────────────────────────────────────

    def ask(self, question: str, verbose: bool = False) -> Dict:
        """Natural-language query. Returns result dict."""
        return self.executor.ask(question)

    def reset_conversation(self):
        self.executor.ctx.reset()

    # ── Export ────────────────────────────────────────────────────────────────

    def export(
        self,
        fmt  : Literal["csv", "excel", "json"] = "csv",
        data : Optional[List[Dict]] = None,
    ) -> Path:
        return self.db.export_results(fmt, data)

    # ── Email campaigns ───────────────────────────────────────────────────────

    def create_campaign(
        self,
        context: str,
        recipients: Optional[List[Dict]] = None,
    ) -> EmailCampaign:
        """Generate an email campaign draft (not yet sent)."""

        if not self.email_gen:
            raise RuntimeError(
                "EmailGenerator not initialized (LLM not available)."
            )

        recipients = recipients or self.executor.ctx.last_data

        if not recipients:
            raise ValueError(
                "No recipients. Run a query first or pass recipients explicitly."
            )

        # ── Email warning check (DO NOT BLOCK CAMPAIGN) ───────────

        email_column = (
    self.db.schema.email_column
    if self.db.schema
    else None
)

        logger.warning(f"EMAIL COLUMN = {email_column}")
        missing_count = 0

        if email_column:
            for row in recipients:
                email = str(
                    row.get(email_column, "")
                ).strip()

                if not email or "@" not in email:
                    missing_count += 1

        warning = None

        if missing_count > 0:
            warning = (
                f"{missing_count} recipient(s) have missing or invalid email addresses. "
                "They will be skipped when sending."
            )

            logger.warning(warning)

        # ── Existing code ────────────────────────────────────────

        available_cols = [
            c.name
            for c in (
                self.db.schema.columns
                if self.db.schema
                else []
            )
        ]

        content = self.email_gen.generate_campaign(
            campaign_context=context,
            recipient_count=len(recipients),
            sample_data=recipients[:3],
            available_columns=available_cols,
        )

        campaign = EmailCampaign(
            campaign_id=str(uuid.uuid4())[:8],
            org_name=self.org.name,
            query_description=context,
            recipient_count=len(recipients),
            subject=content["subject"],
            body_template=content["body"],
            recipients=recipients,
            status="pending_approval",
        )

        # attach warning dynamically
        campaign.warning = warning

        self.db._campaigns[campaign.campaign_id] = campaign
        self.audit.log_campaign_created(campaign)

        return campaign

    def preview_campaign(
        self,
        campaign        : EmailCampaign,
        recipient_index : int = 0,
    ) -> Dict:
        if not self.email_gen:
            raise RuntimeError("EmailGenerator not initialized.")
        if recipient_index >= len(campaign.recipients):
            raise IndexError("Recipient index out of range.")

        row = campaign.recipients[recipient_index]
        return self.email_gen.preview(campaign.subject, campaign.body_template, row)

    def approve_and_send(self, campaign: EmailCampaign) -> Dict:
        """REQUIRES explicit human approval. Sends campaign and returns delivery summary."""
        if not self.email_service or not self.email_gen:
            raise RuntimeError(
                "Email service not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
            )
        if campaign.status != "pending_approval":
            raise ValueError(
                f"Campaign status is '{campaign.status}', not 'pending_approval'."
            )
        if not self.db.schema or not self.db.schema.email_column:
            raise ValueError("No email column detected in the loaded data.")

        result = self.email_service.send_campaign(
            campaign     = campaign,
            email_column = self.db.schema.email_column,
            email_gen    = self.email_gen,
        )
        self.audit.log_campaign_sent(result)
        return result

    # ── Audit ─────────────────────────────────────────────────────────────────

    def get_audit_log(
        self,
        event_type : Optional[str] = None,
        last_n     : int = 20,
    ) -> List[Dict]:
        return self.audit.get_log(event_type, last_n)
