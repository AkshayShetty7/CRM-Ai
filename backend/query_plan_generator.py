

import json
import re
from typing import Optional, Tuple

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from config import logger
from models import SchemaSummary
from query_plan import QueryPlan, QUERY_PLAN_SCHEMA_JSON


# ── Prompts ───────────────────────────────────────────────────────────────────
QUERY_PLAN_SYSTEM_PROMPT = """\
You are a data query planner. Given a user question and a database schema, \
produce a structured JSON QueryPlan that describes WHAT data to retrieve.

CRITICAL RULES:
1. You MUST output ONLY a valid JSON object that matches the QueryPlan schema.
2. Do NOT write SQL. Do NOT explain. Output JSON only.
3. Use ONLY column names that exist in the schema (exact spelling, case-sensitive).
4. For text matching, prefer 'contains' or 'equals'. Use 'starts_with' / 'ends_with' when relevant.
5. For date filtering, prefer date shortcut operators (last_7_days, this_month, next_30_days, etc.).
6. If the user wants all data without filtering, return an empty filters list.
7. 'intent_summary' should be a 1-line human-readable description.

FILTER LOGIC:
- Each filter has a 'logic' field: 'AND' (default) or 'OR'.
- The 'logic' field specifies how this filter joins with the PREVIOUS one.
- The first filter's 'logic' is ignored.

CONTEXT:
{conversation_context}
"""

QUERY_PLAN_USER_PROMPT = """\
DATABASE SCHEMA:
{schema}

PREVIOUS QUERY PLAN (for follow-up context):
{previous_plan}

USER QUESTION: {question}

Return ONLY a JSON object matching this schema:
{json_schema}
"""


class QueryPlanGenerator:
    def __init__(self, llm: ChatGroq):
        self.llm     = llm
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_PLAN_SYSTEM_PROMPT),
            ("human",  QUERY_PLAN_USER_PROMPT),
        ])

    def generate(
        self,
        question         : str,
        schema_summary   : SchemaSummary,
        previous_plan    : Optional[QueryPlan] = None,
        conversation_ctx : str = "",
    ) -> Tuple[QueryPlan, str]:
        """
        Returns (QueryPlan, raw_json_string).
        Raises ValueError if the LLM response cannot be parsed.
        """
        prev_plan_str = (
            json.dumps(previous_plan.model_dump(), indent=2)
            if previous_plan else "None"
        )

        chain    = self._prompt | self.llm
        response = chain.invoke({
            "schema"              : schema_summary.to_llm_context(),
            "question"            : question,
            "previous_plan"       : prev_plan_str,
            "json_schema"         : QUERY_PLAN_SCHEMA_JSON,
            "conversation_context": conversation_ctx,
        })

        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$",          "", raw).strip()

        logger.debug(f"LLM raw plan:\n{raw}")

        try:
            data = json.loads(raw)
            plan = QueryPlan.model_validate(data)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse LLM QueryPlan: {exc}\nRaw output:\n{raw}"
            ) from exc

        logger.info(
            f"QueryPlan generated: op={plan.operation}, "
            f"filters={len(plan.filters)}, aggs={len(plan.aggregations)}"
        )
        return plan, raw
