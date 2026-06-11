"""
query_executor.py
Orchestrates the full query pipeline:
  Question → QueryPlanGenerator → QueryBuilder → DuckDBManager → Result

Also manages rolling conversation context and calls the AuditLogger.
"""

from datetime import datetime
from typing import Dict, List, Optional

from audit_logger import AuditLogger
from db_manager import DuckDBManager
from query_builder import QueryBuilder, QueryValidationError
from query_plan import QueryPlan
from query_plan_generator import QueryPlanGenerator


class ConversationContext:
    """Rolling window conversation history with previous query plan tracking."""

    MAX_TURNS = 10

    def __init__(self):
        self._history : List[Dict]          = []
        self.last_plan: Optional[QueryPlan] = None
        self.last_data: List[Dict]          = []

    def add(self, role: str, content: str):
        self._history.append({
            "role":    role,
            "content": content[:500],
            "ts":      datetime.now().isoformat(),
        })
        if len(self._history) > self.MAX_TURNS * 2:
            self._history = self._history[-(self.MAX_TURNS * 2):]

    def to_string(self) -> str:
        recent = self._history[-6:]
        return "\n".join(f"{t['role'].upper()}: {t['content']}" for t in recent)

    def reset(self):
        self._history  = []
        self.last_plan = None
        self.last_data = []


class QueryExecutor:
    def __init__(
        self,
        db       : DuckDBManager,
        plan_gen : QueryPlanGenerator,
        audit    : AuditLogger,
    ):
        self.db       = db
        self.plan_gen = plan_gen
        self.audit    = audit
        self.ctx      = ConversationContext()

    def ask(self, question: str) -> Dict:
        """Full pipeline: question → plan → SQL → result dict."""
        if not self.db.schema:
            return {"error": "No data loaded. Please upload a file first."}

        self.ctx.add("user", question)

        # Step 1 — generate query plan via LLM
        try:
            plan, _raw_plan = self.plan_gen.generate(
                question         = question,
                schema_summary   = self.db.schema,
                previous_plan    = self.ctx.last_plan,
                conversation_ctx = "",
            )
        except ValueError as exc:
            return {"error": f"Query planning failed: {exc}"}

        # Step 2 — build SQL from plan
        builder = QueryBuilder(self.db.schema)
        try:
            sql, params = builder.build(plan)
        except QueryValidationError as exc:
            return {"error": str(exc), "plan": plan.model_dump()}

        # Step 3 — execute
        result = self.db.execute(sql, params if params else None)

        # Update context
        self.ctx.last_plan = plan
        if "data" in result:
            self.ctx.last_data = result["data"]
            self.ctx.add(
                "assistant",
                f"Returned {result['row_count']} rows. {plan.intent_summary}",
            )

        # Audit
        self.audit.log_query(
            question  = question,
            plan      = plan.model_dump(),
            sql       = sql,
            row_count = result.get("row_count", 0),
            has_error = "error" in result,
        )

        return {
            **result,
            "plan":           plan.model_dump(),
            "intent_summary": plan.intent_summary,
        }
