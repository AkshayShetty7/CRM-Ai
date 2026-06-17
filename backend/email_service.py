
import hashlib
import json
import re
from dataclasses import asdict
import resend
from datetime import datetime
from typing import Dict, List, Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import pandas as pd
from langchain_groq import ChatGroq

from config import SENT_EMAILS_LOG, logger
from models import EmailCampaign, EmailStatus, Organization


# ── Email Content Generator ───────────────────────────────────────────────────
class EmailGenerator:


    def __init__(self, llm: ChatGroq, org: Organization):
        self.llm = llm
        self.org = org

    def generate_campaign(
        self,
        campaign_context  : str,
        recipient_count   : int,
        sample_data       : List[Dict],
        available_columns : List[str],
    ) -> Dict[str, str]:
        sample_json  = json.dumps(sample_data[:3], indent=2, default=str)
        columns_list = ", ".join(available_columns)

        prompt = f"""\
You are a professional marketing copywriter for {self.org.name}.

COMPANY DETAILS (use these exactly — do not invent or substitute):
  Name        : {self.org.name}
  Description : {self.org.description}
  Phone       : {self.org.support_number}
  Email       : {self.org.email_id}

CAMPAIGN CONTEXT: {campaign_context}
TARGET AUDIENCE: {recipient_count} recipients
SAMPLE DATA (first 3 rows): {sample_json}
AVAILABLE COLUMNS FOR PLACEHOLDERS: {columns_list}

Write a professional email campaign.
Use {{{{Column Name}}}} placeholders from the available columns list for personalization.

STRICT RULES:
1. Only use placeholders for columns in the list above.
2. For contact info, ALWAYS use the company Phone and Email provided above.
   NEVER use a recipient's email address as a contact/reply-to address.
   The recipient email is only used as the delivery address — it must NOT appear in the body.
3. Sign off with the company name only.

Return ONLY valid JSON with keys 'subject' and 'body'. No markdown, no explanation.
"""
        response = self.llm.invoke(prompt)
        raw      = response.content.strip()
        raw      = re.sub(r"^```(?:json)?\s*", "", raw)
        raw      = re.sub(r"\s*```$",           "", raw).strip()

        try:
            data = json.loads(raw)
            return {"subject": data["subject"], "body": data["body"]}
        except Exception:
            logger.warning("Email generation JSON parse failed, using fallback.")
            return {
                "subject": f"Important Update from {self.org.name}",
                "body":    raw,
            }

    @staticmethod
    def personalize(template: str, row: Dict) -> str:
        """Replace {{Column Name}} placeholders with values from a row dict."""
        result = template
        for key, value in row.items():
            placeholder = "{{" + str(key) + "}}"
            if placeholder in result:
                safe_val = (
                    str(value)
                    if (value is not None
                        and not (isinstance(value, float) and pd.isna(value)))
                    else ""
                )
                result = result.replace(placeholder, safe_val)
        return result

    def preview(
        self,
        subject_template : str,
        body_template    : str,
        row              : Dict,
    ) -> Dict[str, str]:
        return {
            "subject": self.personalize(subject_template, row),
            "body":    self.personalize(body_template,    row),
        }


# ── SMTP Email Sender ─────────────────────────────────────────────────────────
class EmailService:


    def __init__(self, sendgrid_api_key, from_email):
        self.sendgrid_api_key = sendgrid_api_key
        self.from_email = from_email

        self._sent_hashes = set()
        self._load_sent_hashes()

    def _load_sent_hashes(self):
        if not SENT_EMAILS_LOG.exists():
            return
        with open(SENT_EMAILS_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "sent":
                        self._sent_hashes.add(
                            self._hash(entry["email"], entry["campaign_id"])
                        )
                except Exception:
                    pass

    @staticmethod
    def _hash(email: str, campaign_id: str) -> str:
        return hashlib.sha256(f"{email}:{campaign_id}".encode()).hexdigest()

    def _is_duplicate(self, email: str, campaign_id: str) -> bool:
        return self._hash(email, campaign_id) in self._sent_hashes

    def send_one(
        self,
        recipient   : str,
        subject     : str,
        body        : str,
        campaign_id : str,
    ) -> EmailStatus:
        ts = datetime.now().isoformat()

        if self._is_duplicate(recipient, campaign_id):
            return EmailStatus(
                email=recipient, status="duplicate", timestamp=ts,
                campaign_id=campaign_id, error="Already sent",
            )

        try:
            html_body = f"""
            <html>
            <body style="font-family:Arial,sans-serif;line-height:1.6;color:#333">
            <div style="max-width:600px;margin:0 auto;padding:20px">
            {body.replace(chr(10), '<br>')}
            <hr style="margin-top:30px;border:none;border-top:1px solid #eee">
            <p style="font-size:11px;color:#999">
            Campaign ID: {campaign_id}
            </p>
            </div>
            </body>
            </html>
            """

            message = Mail(
                from_email=self.from_email,
                to_emails=recipient,
                subject=subject,
                html_content=html_body,
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)

            response = sg.send(message)

            if response.status_code not in (200, 202):
                raise Exception(
                    f"SendGrid returned status {response.status_code}"
                )

            self._sent_hashes.add(
                self._hash(recipient, campaign_id)
            )

            status = EmailStatus(
                email=recipient,
                status="sent",
                timestamp=ts,
                campaign_id=campaign_id,
            )

        except Exception as exc:
            logger.error(
                f"EMAIL FAILED | recipient={recipient} | "
                f"{type(exc).__name__}: {exc}"
            )

            status = EmailStatus(
                email=recipient,
                status="failed",
                timestamp=ts,
                campaign_id=campaign_id,
                error=str(exc),
            )

        return status

    def send_campaign(
        self,
        campaign     : EmailCampaign,
        email_column : str,
        email_gen    : EmailGenerator,
    ) -> Dict:
        """
        Send all emails in a campaign.
        Returns summary dict.
        MUST only be called after the user explicitly approves the campaign.
        """
        sent, failed, dupes, skipped = [], [], [], []

        for row in campaign.recipients:
            email = str(row.get(email_column, "")).strip()
            if not email or "@" not in email:
                skipped.append(row)
                continue

            subject = email_gen.personalize(campaign.subject,       row)
            body    = email_gen.personalize(campaign.body_template, row)

            status_obj = self.send_one(email, subject, body, campaign.campaign_id)
            entry      = asdict(status_obj)

            if   status_obj.status == "sent":      sent.append(entry)
            elif status_obj.status == "duplicate": dupes.append(entry)
            elif status_obj.status == "failed":    failed.append(entry)

        campaign.sent_emails   = sent
        campaign.failed_emails = failed
        campaign.status        = "completed" if not failed else "partial"

        logger.info(
            f"Campaign {campaign.campaign_id}: sent={len(sent)}, "
            f"failed={len(failed)}, dupes={len(dupes)}, skipped={len(skipped)}"
        )

        return {
            "campaign_id": campaign.campaign_id,
            "total":       len(campaign.recipients),
            "sent":        len(sent),
            "failed":      len(failed),
            "duplicates":  len(dupes),
            "skipped":     len(skipped),
            "status":      campaign.status,
        }
