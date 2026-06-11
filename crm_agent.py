#!/usr/bin/env python
# coding: utf-8

# # 🤖 AI-Powered CRM / Data Analysis Agent
# 
# **Architecture:** Excel → Pandas → DuckDB → Schema Detection → LLM (Query Plan JSON) → Python Query Builder → SQL → Results
# 
# > The LLM **never** generates SQL directly. It produces a structured `QueryPlan` JSON. Python builds safe, parameterized SQL from that plan.
# 
# ---
# ### Sections
# 1. Environment Setup
# 2. Imports
# 3. Configuration
# 4. Data Models
# 5. Schema Analyzer
# 6. DuckDB Manager
# 7. Query Plan Models (Pydantic)
# 8. Query Plan Generator (LLM)
# 9. Query Builder (Plan → SQL)
# 10. Query Executor
# 11. Email System
# 12. Audit Logger
# 13. Agent Orchestrator
# 14. Demo Workflow
# 15. Testing Examples

# ## 1. Environment Setup

# In[2]:


# Install required packages (run once)
# import subprocess, sys

# packages = [
#     "duckdb",
#     "pandas",
#     "openpyxl",
#     "xlrd",
#     "pydantic>=2.0",
#     "langchain",
#     "langchain-groq",
#     "langchain-core",
#     "python-dotenv",
# ]

# for pkg in packages:
#     subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

# print("✅ All packages installed.")


# ## 2. Imports

# In[3]:


import os
import re
import json
import uuid
import hashlib
import smtplib
import logging
from copy import deepcopy
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict

import duckdb
import pandas as pd
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from pydantic import BaseModel, Field, field_validator, model_validator
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

print("✅ All imports successful.")


# ## 3. Configuration

# In[4]:


load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# ── LLM Model ─────────────────────────────────────────────────────────────────
DEFAULT_MODEL       = "llama-3.3-70b-versatile"
LLM_TEMPERATURE     = 0.0   # deterministic for query plan generation
LLM_MAX_TOKENS      = 1024

# ── Storage Paths ─────────────────────────────────────────────────────────────
AUDIT_LOG_PATH      = Path("crm_audit_log.jsonl")
SENT_EMAILS_LOG     = Path("crm_sent_emails.jsonl")
EXPORT_DIR          = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

# ── Query Limits ──────────────────────────────────────────────────────────────
DEFAULT_QUERY_LIMIT = 500
MAX_QUERY_LIMIT     = 5000

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ai_crm")

if not GROQ_API_KEY:
    logger.warning("⚠️  GROQ_API_KEY not set. LLM features will fail.")
else:
    logger.info("✅ GROQ_API_KEY loaded.")


# ## 4. Data Models

# In[5]:


# ── Organization ──────────────────────────────────────────────────────────────
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
        """Compact schema string sent to LLM."""
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
    status: str = "draft"          # draft | pending_approval | sending | completed | partial | failed
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

print("✅ Data models defined.")


# ## 5. Schema Analyzer

# In[6]:


class SchemaAnalyzer:
    """
    Inspects a Pandas DataFrame and produces a rich SchemaSummary.
    Detects column types, nullability, cardinality, and example values.
    No hardcoded column names — works with any schema.
    """

    # Heuristic keywords to identify special columns
    _EMAIL_HINTS   = {"email", "mail", "emailaddress", "e-mail"}
    _NAME_HINTS    = {"name", "customername", "clientname", "fullname", "contactname", "employeename"}

    def analyze(self, df: pd.DataFrame, table_name: str = "data") -> SchemaSummary:
        columns: List[ColumnMeta] = []
        email_col   = None
        name_col    = None
        date_cols   = []

        for col in df.columns:
            meta = self._analyze_column(df, col)
            columns.append(meta)

            key = col.lower().replace(" ", "").replace("_", "")
            if email_col is None and any(h in key for h in self._EMAIL_HINTS):
                email_col = col
            if name_col is None and any(h in key for h in self._NAME_HINTS):
                name_col = col
            if meta.dtype in ("date", "datetime"):
                date_cols.append(col)

        return SchemaSummary(
            table_name   = table_name,
            row_count    = len(df),
            columns      = columns,
            email_column = email_col,
            name_column  = name_col,
            date_columns = date_cols,
        )

    def _analyze_column(self, df: pd.DataFrame, col: str) -> ColumnMeta:
        series  = df[col]
        n       = len(series)
        n_null  = series.isna().sum()
        non_null = series.dropna()

        dtype   = self._infer_dtype(series)
        examples = []
        min_val  = None
        max_val  = None

        if len(non_null) > 0:
            sample = non_null.head(5).tolist()
            examples = [str(v)[:50] for v in sample]
            if dtype in ("integer", "float", "date", "datetime"):
                try:
                    min_val = str(non_null.min())
                    max_val = str(non_null.max())
                except Exception:
                    pass

        return ColumnMeta(
            name         = col,
            dtype        = dtype,
            null_pct     = round(n_null / n * 100, 1) if n else 0.0,
            unique_count = int(non_null.nunique()),
            examples     = examples,
            min_val      = min_val,
            max_val      = max_val,
        )

    def _infer_dtype(self, series: pd.Series) -> str:
        pd_dtype = str(series.dtype)

        if "datetime" in pd_dtype:
            return "datetime"
        if "date" in pd_dtype:
            return "date"
        if "bool" in pd_dtype:
            return "boolean"
        if "int" in pd_dtype:
            return "integer"
        if "float" in pd_dtype:
            return "float"

        # Try to parse as date if object dtype
        if pd_dtype == "object":
            sample = series.dropna().head(20)
            if self._looks_like_date(sample):
                return "date"
            return "text"

        return "text"

    @staticmethod
    def _looks_like_date(sample: pd.Series) -> bool:
        if len(sample) == 0:
            return False
        parsed = 0
        for v in sample:
            try:
                pd.to_datetime(str(v))
                parsed += 1
            except Exception:
                pass
        return parsed / len(sample) >= 0.8

print("✅ SchemaAnalyzer defined.")


# ## 6. DuckDB Manager

# In[7]:


class DuckDBManager:
    """
    Manages an in-memory DuckDB connection.
    Loads DataFrames, executes validated SELECT queries, and manages exports.
    """

    TABLE_NAME = "crm_data"

    def __init__(self):
        self.conn           = duckdb.connect(":memory:")
        self.schema         : Optional[SchemaSummary] = None
        self._last_results  : List[Dict] = []
        self._campaigns     : Dict[str, EmailCampaign] = {}

    # ── Loading ──────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> SchemaSummary:
        """
        Load xlsx / xls / csv into DuckDB.
        Cleans column names, parses dates, and returns SchemaSummary.
        """
        path = str(path)
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        # Sanitize column names: strip whitespace
        df.columns = [str(c).strip() for c in df.columns]

        # Attempt date parsing for object columns that look like dates
        for col in df.select_dtypes(include="object").columns:
            sample = df[col].dropna().head(20)
            if SchemaAnalyzer._looks_like_date(sample):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass

        analyzer    = SchemaAnalyzer()
        self.schema = analyzer.analyze(df, self.TABLE_NAME)

        # (Re-)register view
        try:
            self.conn.execute(f"DROP VIEW IF EXISTS {self.TABLE_NAME}")
        except Exception:
            pass
        self.conn.register(self.TABLE_NAME, df)

        logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} columns → '{self.TABLE_NAME}'")
        return self.schema

    # ── Execution ────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: Optional[List] = None) -> Dict:
        """
        Execute a validated SELECT statement.
        Returns dict with data, columns, row_count, sql.
        """
        validation_error = self._validate_sql(sql)
        if validation_error:
            return {"error": validation_error, "sql": sql}

        try:
            if params:
                result_df = self.conn.execute(sql, params).fetchdf()
            else:
                result_df = self.conn.execute(sql).fetchdf()

            records = result_df.to_dict(orient="records")
            self._last_results = records

            logger.info(f"Query OK → {len(records):,} rows")
            return {
                "row_count" : len(records),
                "columns"   : result_df.columns.tolist(),
                "data"      : records,
                "sql"       : sql,
            }
        except Exception as exc:
            logger.error(f"Query FAILED: {exc}\nSQL: {sql}")
            return {"error": str(exc), "sql": sql}

    # ── Export ───────────────────────────────────────────────────────────────

    def export_results(
        self,
        fmt: Literal["csv", "excel", "json"] = "csv",
        data: Optional[List[Dict]] = None,
    ) -> Path:
        rows = data if data is not None else self._last_results
        if not rows:
            raise ValueError("No results to export.")

        df        = pd.DataFrame(rows)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "xlsx" if fmt == "excel" else fmt
        out_path  = EXPORT_DIR / f"export_{ts}.{extension}"

        if fmt == "csv":
            df.to_csv(out_path, index=False)
        elif fmt == "excel":
            df.to_excel(out_path, index=False)
        elif fmt == "json":
            df.to_json(out_path, orient="records", indent=2)

        logger.info(f"Exported {len(rows)} rows → {out_path}")
        return out_path

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _validate_sql(self, sql: str) -> Optional[str]:
        """Return an error string if SQL is unsafe, else None."""
        cleaned = sql.lower().strip()
        if not cleaned.startswith("select"):
            return "Only SELECT statements are permitted."
        forbidden = [
            "drop", "delete", "update", "insert", "alter",
            "truncate", "create", "replace", "merge", "grant", "revoke",
        ]
        for kw in forbidden:
            # word-boundary check
            if re.search(rf"\b{kw}\b", cleaned):
                return f"Forbidden keyword '{kw}' in SQL."
        return None

    def filter_valid_email_records(self, records: List[Dict]) -> List[Dict]:
        if not self.schema or not self.schema.email_column:
            return []
        col = self.schema.email_column
        return [
            r for r in records
            if r.get(col) and isinstance(r[col], str) and "@" in r[col]
        ]

print("✅ DuckDBManager defined.")


# ## 7. Query Plan Models (Pydantic)

# In[8]:


# ── Filter Operators ──────────────────────────────────────────────────────────
FilterOperator = Literal[
    "equals", "not_equals",
    "contains", "not_contains", "starts_with", "ends_with",
    "greater_than", "less_than", "greater_equal", "less_equal",
    "between",
    "is_null", "is_not_null",
    "in_list", "not_in_list",
    # Date shortcuts
    "last_7_days", "last_30_days", "last_90_days",
    "this_week", "this_month", "this_year",
    "next_7_days", "next_30_days", "next_90_days",
    "date_before", "date_after", "date_between",
]

AggFunction = Literal["count", "sum", "avg", "min", "max", "count_distinct"]

SortDirection = Literal["asc", "desc"]


class FilterCondition(BaseModel):
    column    : str
    operator  : FilterOperator
    value     : Optional[Any]        = None
    value2    : Optional[Any]        = None   # for between / date_between
    logic     : Literal["AND", "OR"] = "AND"  # how this joins with the previous filter


class AggregationSpec(BaseModel):
    function  : AggFunction
    column    : str
    alias     : Optional[str] = None


class SortSpec(BaseModel):
    column    : str
    direction : SortDirection = "asc"


class QueryPlan(BaseModel):
    """
    Structured query intent produced by the LLM.
    Python builds SQL from this — LLM never writes SQL.
    """
    operation       : Literal["filter", "aggregate", "top_n", "search"] = "filter"
    filters         : List[FilterCondition]  = Field(default_factory=list)
    group_by        : List[str]              = Field(default_factory=list)
    aggregations    : List[AggregationSpec]  = Field(default_factory=list)
    select_columns  : List[str]              = Field(default_factory=list,
                        description="Specific columns to return; empty = SELECT *")
    sort            : List[SortSpec]         = Field(default_factory=list)
    limit           : int                    = Field(DEFAULT_QUERY_LIMIT,
                        ge=1, le=MAX_QUERY_LIMIT)
    intent_summary  : str                    = ""   # human-readable summary (optional)


# ── JSON Schema for LLM prompt ────────────────────────────────────────────────
QUERY_PLAN_SCHEMA_JSON = json.dumps(QueryPlan.model_json_schema(), indent=2)

print("✅ QueryPlan Pydantic models defined.")
print("  Supported filter operators:", ", ".join(FilterOperator.__args__))


# ## 8. Query Plan Generator (LLM)

# In[9]:


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
    """
    Uses the LLM to convert a natural language question into a QueryPlan JSON.
    The LLM never sees SQL and never produces SQL.
    """

    def __init__(self, llm: ChatGroq):
        self.llm = llm
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_PLAN_SYSTEM_PROMPT),
            ("human",  QUERY_PLAN_USER_PROMPT),
        ])

    def generate(
        self,
        question          : str,
        schema_summary    : SchemaSummary,
        previous_plan     : Optional[QueryPlan]  = None,
        conversation_ctx  : str                  = "",
    ) -> Tuple[QueryPlan, str]:
        """
        Returns (QueryPlan, raw_json_string).
        Raises ValueError if the LLM response cannot be parsed.
        """
        prev_plan_str = json.dumps(previous_plan.model_dump(), indent=2) if previous_plan else "None"

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
        raw = re.sub(r"\s*```$", "", raw).strip()

        logger.debug(f"LLM raw plan:\n{raw}")

        try:
            data = json.loads(raw)
            plan = QueryPlan.model_validate(data)
        except Exception as exc:
            raise ValueError(f"Failed to parse LLM QueryPlan: {exc}\nRaw output:\n{raw}") from exc

        logger.info(f"QueryPlan generated: op={plan.operation}, "
                    f"filters={len(plan.filters)}, "
                    f"aggs={len(plan.aggregations)}")
        return plan, raw

print("✅ QueryPlanGenerator defined.")


# ## 9. Query Builder (Plan → SQL)

# In[10]:


class QueryValidationError(Exception):
    """Raised when a QueryPlan references invalid columns or operators."""


class QueryBuilder:
    """
    Converts a validated QueryPlan into a safe DuckDB SQL statement.

    - Uses quoted identifiers for all column names.
    - Uses positional parameters ($1, $2, …) for all values.
    - Handles date arithmetic with DuckDB's INTERVAL syntax.
    - Never interpolates user values directly into the SQL string.
    """

    TABLE = DuckDBManager.TABLE_NAME

    def __init__(self, schema: SchemaSummary):
        self.schema    = schema
        self._col_map  = {c.name: c for c in schema.columns}  # name → ColumnMeta
        self._col_set  = {c.name for c in schema.columns}

    # ── Public API ──────────────────────────────────────────────────────────

    def build(self, plan: QueryPlan) -> Tuple[str, List]:
        """
        Returns (sql_string, params_list).
        Raises QueryValidationError on invalid column / operator references.
        """
        self._validate_plan(plan)

        params      : List[Any] = []
        where_parts : List[str] = []

        for i, f in enumerate(plan.filters):
            clause, f_params = self._build_filter(f, len(params))
            params.extend(f_params)
            if i == 0:
                where_parts.append(clause)
            else:
                where_parts.append(f"{f.logic} {clause}")

        where_sql = "WHERE " + " ".join(where_parts) if where_parts else ""

        # SELECT clause
        if plan.operation == "aggregate" and plan.aggregations:
            select_sql = self._build_select_aggregate(plan)
        elif plan.select_columns:
            cols = ", ".join(self._q(c) for c in plan.select_columns)
            select_sql = f"SELECT {cols}"
        else:
            select_sql = "SELECT *"

        # GROUP BY
        group_sql = ""
        if plan.group_by:
            cols      = ", ".join(self._q(c) for c in plan.group_by)
            group_sql = f"GROUP BY {cols}"

        # ORDER BY
        order_sql = ""
        if plan.sort:
            parts     = [f"{self._q(s.column)} {s.direction.upper()}" for s in plan.sort]
            order_sql = "ORDER BY " + ", ".join(parts)

        # LIMIT
        limit_sql = f"LIMIT {plan.limit}"

        parts = [p for p in [
            select_sql,
            f"FROM {self.TABLE}",
            where_sql,
            group_sql,
            order_sql,
            limit_sql,
        ] if p]

        sql = "\n".join(parts)
        return sql, params

    # ── Validation ──────────────────────────────────────────────────────────

    def _validate_plan(self, plan: QueryPlan):
        errors = []
        all_referenced = (
            [f.column for f in plan.filters]
            + plan.group_by
            + [a.column for a in plan.aggregations]
            + [s.column for s in plan.sort]
            + plan.select_columns
        )
        for col in all_referenced:
            if col not in self._col_set:
                available = ", ".join(sorted(self._col_set))
                errors.append(
                    f"Column '{col}' does not exist.\n"
                    f"Available columns: {available}"
                )
        if errors:
            raise QueryValidationError("\n".join(errors))

    # ── SELECT for aggregates ────────────────────────────────────────────────

    def _build_select_aggregate(self, plan: QueryPlan) -> str:
        parts = [self._q(c) for c in plan.group_by]
        for agg in plan.aggregations:
            fn    = agg.function.upper().replace("COUNT_DISTINCT", "COUNT DISTINCT")
            alias = agg.alias or f"{agg.function}_{agg.column}".replace(" ", "_")
            if agg.function == "count_distinct":
                parts.append(f"COUNT(DISTINCT {self._q(agg.column)}) AS {self._q(alias)}")
            elif agg.function == "count" and agg.column == "*":
                parts.append(f"COUNT(*) AS {self._q(alias)}")
            else:
                parts.append(f"{agg.function.upper()}({self._q(agg.column)}) AS {self._q(alias)}")
        return "SELECT " + ", ".join(parts)

    # ── Filter Builder ───────────────────────────────────────────────────────

    def _build_filter(self, f: FilterCondition, param_offset: int) -> Tuple[str, List]:
        col   = self._q(f.column)
        op    = f.operator
        p     = []   # accumulated params for this filter

        def P(val):  # helper: add param and return placeholder
            p.append(val)
            return f"${param_offset + len(p)}"

        # ── text operators ─────────────────────────────────────
        if op == "equals":       return f"{col} = {P(f.value)}",             p
        if op == "not_equals":   return f"{col} != {P(f.value)}",            p
        if op == "contains":     return f"{col} ILIKE {P(f'%{f.value}%')}",  p
        if op == "not_contains": return f"{col} NOT ILIKE {P(f'%{f.value}%')}", p
        if op == "starts_with":  return f"{col} ILIKE {P(f'{f.value}%')}",   p
        if op == "ends_with":    return f"{col} ILIKE {P(f'%{f.value}')}",   p

        # ── numeric operators ──────────────────────────────────
        if op == "greater_than":   return f"{col} > {P(f.value)}",           p
        if op == "less_than":      return f"{col} < {P(f.value)}",           p
        if op == "greater_equal":  return f"{col} >= {P(f.value)}",          p
        if op == "less_equal":     return f"{col} <= {P(f.value)}",          p
        if op == "between":        return f"{col} BETWEEN {P(f.value)} AND {P(f.value2)}", p

        # ── null operators ─────────────────────────────────────
        if op == "is_null":     return f"{col} IS NULL",     []
        if op == "is_not_null": return f"{col} IS NOT NULL", []

        # ── list operators ─────────────────────────────────────
        if op == "in_list":
            placeholders = ", ".join(P(v) for v in (f.value or []))
            return f"{col} IN ({placeholders})", p
        if op == "not_in_list":
            placeholders = ", ".join(P(v) for v in (f.value or []))
            return f"{col} NOT IN ({placeholders})", p

        # ── date shortcut operators (no params — use DuckDB functions) ──
        today = "CURRENT_DATE"
        date_shortcuts = {
            "last_7_days"  : f"{col} >= {today} - INTERVAL '7 days'",
            "last_30_days" : f"{col} >= {today} - INTERVAL '30 days'",
            "last_90_days" : f"{col} >= {today} - INTERVAL '90 days'",
            "this_week"    : f"date_trunc('week',  {col}) = date_trunc('week',  {today})",
            "this_month"   : f"date_trunc('month', {col}) = date_trunc('month', {today})",
            "this_year"    : f"date_trunc('year',  {col}) = date_trunc('year',  {today})",
            "next_7_days"  : f"{col} BETWEEN {today} AND {today} + INTERVAL '7 days'",
            "next_30_days" : f"{col} BETWEEN {today} AND {today} + INTERVAL '30 days'",
            "next_90_days" : f"{col} BETWEEN {today} AND {today} + INTERVAL '90 days'",
        }
        if op in date_shortcuts:
            return date_shortcuts[op], []

        if op == "date_before": return f"{col} < {P(f.value)}",  p
        if op == "date_after":  return f"{col} > {P(f.value)}",  p
        if op == "date_between":
            return f"{col} BETWEEN {P(f.value)} AND {P(f.value2)}", p

        raise QueryValidationError(f"Unknown operator: '{op}'")

    @staticmethod
    def _q(name: str) -> str:
        """Double-quote an identifier (DuckDB style)."""
        return '"' + name.replace('"', '""') + '"'

print("✅ QueryBuilder defined.")


# ## 10. Query Executor

# In[11]:


class ConversationContext:
    """Rolling window conversation history with previous query plan tracking."""

    MAX_TURNS = 10

    def __init__(self):
        self._history  : List[Dict]            = []
        self.last_plan : Optional[QueryPlan]   = None
        self.last_data : List[Dict]            = []

    def add(self, role: str, content: str):
        self._history.append({"role": role, "content": content[:500], "ts": datetime.now().isoformat()})
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
    """
    Orchestrates the full pipeline:
      Question → QueryPlanGenerator → QueryBuilder → DuckDBManager

    Also logs every step to the AuditLogger.
    """

    def __init__(
        self,
        db          : DuckDBManager,
        plan_gen    : QueryPlanGenerator,
        audit       : "AuditLogger",
    ):
        self.db      = db
        self.plan_gen = plan_gen
        self.audit   = audit
        self.ctx     = ConversationContext()

    def ask(self, question: str) -> Dict:
        """
        Full pipeline: question → plan → SQL → result.
        Returns rich dict with result data and pipeline metadata.
        """
        if not self.db.schema:
            return {"error": "No data loaded. Please upload a file first."}

        self.ctx.add("user", question)

        # Step 1: Generate query plan
        try:
            plan, raw_plan = self.plan_gen.generate(
                question         = question,
                schema_summary   = self.db.schema,
                previous_plan    = self.ctx.last_plan,
                conversation_ctx = self.ctx.to_string(),
            )
        except ValueError as exc:
            return {"error": f"Query planning failed: {exc}"}

        # Step 2: Build SQL from plan
        builder = QueryBuilder(self.db.schema)
        try:
            sql, params = builder.build(plan)
        except QueryValidationError as exc:
            return {"error": str(exc), "plan": plan.model_dump()}

        # Step 3: Execute
        result = self.db.execute(sql, params if params else None)

        # Update context
        self.ctx.last_plan = plan
        if "data" in result:
            self.ctx.last_data = result["data"]
            self.ctx.add("assistant", f"Returned {result['row_count']} rows. {plan.intent_summary}")

        # Audit
        self.audit.log_query(
            question   = question,
            plan       = plan.model_dump(),
            sql        = sql,
            row_count  = result.get("row_count", 0),
            has_error  = "error" in result,
        )

        return {
            **result,
            "plan"         : plan.model_dump(),
            "intent_summary": plan.intent_summary,
        }

    def print_result(self, result: Dict, max_rows: int = 10):
        """Pretty-print a query result to notebook output."""
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return

        print(f"📊 Intent: {result.get('intent_summary', '')}")
        print(f"   Rows returned : {result['row_count']:,}")
        if result.get('sql'):
            plan = result.get('plan', {})
            filter_vals = [f.get('value') for f in plan.get('filters', []) if f.get('value') is not None]
            params_note = f"  params={filter_vals}" if filter_vals else ""
            print(f"   SQL (params)  : {result['sql'].replace(chr(10), ' ')}{params_note}")
            if filter_vals:
                print(f"   ℹ️  $1, $2… are DuckDB parameterized placeholders — values are passed separately to prevent SQL injection.")
        if result["data"]:
            df = pd.DataFrame(result["data"][:max_rows])
            print(df)

print("✅ QueryExecutor & ConversationContext defined.")


# ## 11. Email System

# In[12]:


# ── Email Content Generator ───────────────────────────────────────────────────
class EmailGenerator:
    """
    Uses the LLM to create personalized email subject + body templates.
    Templates use {{Column Name}} placeholders.
    """

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
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()

        try:
            data = json.loads(raw)
            return {"subject": data["subject"], "body": data["body"]}
        except Exception:
            logger.warning("Email generation JSON parse failed, using fallback.")
            return {
                "subject": f"Important Update from {self.org.name}",
                "body"   : raw,
            }

    @staticmethod
    def personalize(template: str, row: Dict) -> str:
        """Replace {{Column Name}} with values from a row dict."""
        result = template
        for key, value in row.items():
            placeholder = "{{" + str(key) + "}}"
            if placeholder in result:
                safe_val = str(value) if (value is not None and not (isinstance(value, float) and pd.isna(value))) else ""
                result   = result.replace(placeholder, safe_val)
        return result

    def preview(
        self,
        subject_template  : str,
        body_template     : str,
        row               : Dict,
    ) -> Dict[str, str]:
        return {
            "subject": self.personalize(subject_template, row),
            "body"   : self.personalize(body_template,    row),
        }


# ── SMTP Email Sender ─────────────────────────────────────────────────────────
class EmailService:
    """
    Sends emails via Gmail SMTP with:
    - Personalization from row data
    - Duplicate prevention (hash-based)
    - Per-email status tracking
    """

    def __init__(self, gmail_address: str, app_password: str):
        self.gmail_address = gmail_address
        self.app_password  = app_password
        self._sent_hashes  : set = set()
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
                        self._sent_hashes.add(self._hash(entry["email"], entry["campaign_id"]))
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
            return EmailStatus(email=recipient, status="duplicate", timestamp=ts,
                               campaign_id=campaign_id, error="Already sent")

        try:
            msg            = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.gmail_address
            msg["To"]      = recipient

            html_body = f"""
            <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333">
            <div style="max-width:600px;margin:0 auto;padding:20px">
            {body.replace(chr(10), '<br>')}
            <hr style="margin-top:30px;border:none;border-top:1px solid #eee">
            <p style="font-size:11px;color:#999">Campaign ID: {campaign_id}</p>
            </div></body></html>
            """
            msg.attach(MIMEText(body,      "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.app_password)
                server.send_message(msg)

            self._sent_hashes.add(self._hash(recipient, campaign_id))
            status = EmailStatus(email=recipient, status="sent", timestamp=ts, campaign_id=campaign_id)

        except Exception as exc:
            status = EmailStatus(email=recipient, status="failed", timestamp=ts,
                                 campaign_id=campaign_id, error=str(exc))

        return status

    def send_campaign(
        self,
        campaign      : EmailCampaign,
        email_column  : str,
        email_gen     : EmailGenerator,
    ) -> Dict:
        """
        Send all emails in a campaign.
        Returns summary dict.
        MUST only be called after user explicitly approves the campaign.
        """
        sent, failed, dupes, skipped = [], [], [], []

        for row in campaign.recipients:
            email = str(row.get(email_column, "")).strip()
            if not email or "@" not in email:
                skipped.append(row)
                continue

            subject = email_gen.personalize(campaign.subject, row)
            body    = email_gen.personalize(campaign.body_template, row)

            status = self.send_one(email, subject, body, campaign.campaign_id)
            entry  = asdict(status)

            if status.status == "sent":       sent.append(entry)
            elif status.status == "duplicate": dupes.append(entry)
            elif status.status == "failed":    failed.append(entry)

        campaign.sent_emails   = sent
        campaign.failed_emails = failed
        campaign.status        = "completed" if not failed else "partial"

        logger.info(f"Campaign {campaign.campaign_id}: sent={len(sent)}, "
                    f"failed={len(failed)}, dupes={len(dupes)}, skipped={len(skipped)}")

        return {
            "campaign_id" : campaign.campaign_id,
            "total"       : len(campaign.recipients),
            "sent"        : len(sent),
            "failed"      : len(failed),
            "duplicates"  : len(dupes),
            "skipped"     : len(skipped),
            "status"      : campaign.status,
        }

print("✅ EmailGenerator & EmailService defined.")


# ## 12. Audit Logger

# In[13]:


class AuditLogger:
    """
    Append-only JSONL audit trail.
    Logs: file uploads, query plans, SQL, email campaigns, email statuses.
    """

    def _write(self, path: Path, entry: Dict):
        entry["logged_at"] = datetime.now().isoformat()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    def log_file_upload(self, file_path: str, schema: SchemaSummary):
        self._write(AUDIT_LOG_PATH, {
            "event"       : "file_upload",
            "file_path"   : file_path,
            "row_count"   : schema.row_count,
            "column_count": len(schema.columns),
            "columns"     : [c.name for c in schema.columns],
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
            "event"     : "query",
            "question"  : question,
            "plan"      : plan,
            "sql"       : sql,
            "row_count" : row_count,
            "has_error" : has_error,
        })

    def log_campaign_created(self, campaign: EmailCampaign):
        self._write(AUDIT_LOG_PATH, {
            "event"          : "campaign_created",
            "campaign_id"    : campaign.campaign_id,
            "recipient_count": campaign.recipient_count,
            "subject"        : campaign.subject,
            "status"         : campaign.status,
        })

    def log_campaign_sent(self, result: Dict):
        self._write(AUDIT_LOG_PATH, {
            "event" : "campaign_sent",
            **result,
        })

    def log_email_status(self, status: EmailStatus):
        self._write(SENT_EMAILS_LOG, asdict(status))

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_log(self, event_type: Optional[str] = None, last_n: int = 50) -> List[Dict]:
        entries = []
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

print("✅ AuditLogger defined.")


# ## 13. Agent Orchestrator

# In[14]:


class CRMAgent:
    """
    Top-level orchestrator.

    Architecture:
      Excel  →  DuckDBManager  →  SchemaAnalyzer  →  SchemaSummary
      Question  →  QueryPlanGenerator (LLM)  →  QueryPlan (JSON)
                →  QueryBuilder             →  SQL + params
                →  DuckDBManager.execute()  →  Results

    The LLM NEVER generates SQL.
    """

    def __init__(
        self,
        org_name        : str,
        org_description : str,
        support_number  : str = "1800-000-0000",
        email_id        : str = "support@example.com",
        model           : str = DEFAULT_MODEL,
        groq_api_key    : Optional[str] = None,
    ):
        self.org = Organization(
            name           = org_name,
            description    = org_description,
            support_number = support_number,
            email_id       = email_id,
        )

        # Core infrastructure
        self.db    = DuckDBManager()
        self.audit = AuditLogger()

        # LLM
        key = groq_api_key or GROQ_API_KEY
        if not key:
            raise ValueError("GROQ_API_KEY is required.")
        self.llm = ChatGroq(
            model        = model,
            temperature  = LLM_TEMPERATURE,
            max_tokens   = LLM_MAX_TOKENS,
            groq_api_key = key,
        )

        plan_gen      = QueryPlanGenerator(self.llm)
        self.executor = QueryExecutor(self.db, plan_gen, self.audit)

        self.email_gen     : Optional[EmailGenerator] = None
        self.email_service : Optional[EmailService]   = None

        # If email credentials available, init service
        if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
            self.email_gen     = EmailGenerator(self.llm, self.org)
            self.email_service = EmailService(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

        logger.info(f"CRMAgent initialized for '{org_name}' with model '{model}'")

    # ─────────────────────────────────────────────────────────────────────────
    # DATA LOADING
    # ─────────────────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> SchemaSummary:
        """Load an Excel or CSV file. Must be called before ask()."""
        schema = self.db.load_file(path)
        self.audit.log_file_upload(path, schema)
        # Re-init email generator with org if needed
        if self.llm and not self.email_gen:
            self.email_gen = EmailGenerator(self.llm, self.org)
        print(f"✅ Loaded: {schema.row_count:,} rows × {len(schema.columns)} columns")
        print(f"   Email column : {schema.email_column}")
        print(f"   Name column  : {schema.name_column}")
        print(f"   Date columns : {schema.date_columns}")
        return schema

    # ─────────────────────────────────────────────────────────────────────────
    # QUERYING
    # ─────────────────────────────────────────────────────────────────────────

    def ask(self, question: str, verbose: bool = True) -> Dict:
        """
        Natural language query.
        Returns result dict with data, plan, sql, row_count.
        """
        result = self.executor.ask(question)
        if verbose:
            self.executor.print_result(result)
        return result

    def reset_conversation(self):
        """Clear conversation context (start fresh)."""
        self.executor.ctx.reset()
        print("🔄 Conversation context reset.")

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    def export(
        self,
        fmt  : Literal["csv", "excel", "json"] = "csv",
        data : Optional[List[Dict]]            = None,
    ) -> Path:
        """Export last query results (or custom data) to file."""
        path = self.db.export_results(fmt, data)
        print(f"📁 Exported → {path}")
        return path

    # ─────────────────────────────────────────────────────────────────────────
    # EMAIL CAMPAIGNS
    # ─────────────────────────────────────────────────────────────────────────

    def create_campaign(
        self,
        context   : str,
        recipients: Optional[List[Dict]] = None,
    ) -> EmailCampaign:
        """
        Generate an email campaign (draft, not yet sent).
        Uses last query results if recipients not provided.
        """
        if not self.email_gen:
            raise RuntimeError("EmailGenerator not initialized (LLM not available).")

        recipients = recipients or self.executor.ctx.last_data
        if not recipients:
            raise ValueError("No recipients. Run a query first or pass recipients explicitly.")

        available_cols = [c.name for c in (self.db.schema.columns if self.db.schema else [])]

        content = self.email_gen.generate_campaign(
            campaign_context  = context,
            recipient_count   = len(recipients),
            sample_data       = recipients[:3],
            available_columns = available_cols,
        )

        campaign = EmailCampaign(
            campaign_id       = str(uuid.uuid4())[:8],
            org_name          = self.org.name,
            query_description = context,
            recipient_count   = len(recipients),
            subject           = content["subject"],
            body_template     = content["body"],
            recipients        = recipients,
            status            = "pending_approval",
        )

        self.db._campaigns[campaign.campaign_id] = campaign
        self.audit.log_campaign_created(campaign)

        print(f"📧 Campaign created: {campaign.campaign_id}")
        print(f"   Subject  : {campaign.subject}")
        print(f"   Recipients: {campaign.recipient_count}")
        print(f"   Status   : {campaign.status}")
        return campaign

    def preview_campaign(
        self,
        campaign       : EmailCampaign,
        recipient_index: int = 0,
    ) -> Dict:
        """Show personalized preview for one recipient."""
        if not self.email_gen:
            raise RuntimeError("EmailGenerator not initialized.")
        if recipient_index >= len(campaign.recipients):
            raise IndexError("Recipient index out of range.")

        row     = campaign.recipients[recipient_index]
        preview = self.email_gen.preview(
            campaign.subject, campaign.body_template, row
        )
        print(f"\n── Preview for recipient #{recipient_index} ──────────────────")
        print(f"TO     : {row.get(self.db.schema.email_column or '', 'N/A')}")
        print(f"SUBJECT: {preview['subject']}")
        print(f"BODY:\n{preview['body']}")
        return preview

    def approve_and_send(self, campaign: EmailCampaign) -> Dict:
        """
        REQUIRES explicit human approval before calling.
        Sends campaign and returns delivery summary.
        """
        if not self.email_service or not self.email_gen:
            raise RuntimeError("Email service not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
        if campaign.status != "pending_approval":
            raise ValueError(f"Campaign status is '{campaign.status}', not 'pending_approval'.")
        if not self.db.schema or not self.db.schema.email_column:
            raise ValueError("No email column detected in the loaded data.")

        result = self.email_service.send_campaign(
            campaign     = campaign,
            email_column = self.db.schema.email_column,
            email_gen    = self.email_gen,
        )

        self.audit.log_campaign_sent(result)
        print(f"📬 Campaign {campaign.campaign_id} sent.")
        print(json.dumps(result, indent=2))
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # AUDIT
    # ─────────────────────────────────────────────────────────────────────────

    def get_audit_log(self, event_type: Optional[str] = None, last_n: int = 20) -> List[Dict]:
        return self.audit.get_log(event_type, last_n)

    def schema_summary(self):
        """Print the current schema."""
        if not self.db.schema:
            print("No data loaded.")
            return
        print(self.db.schema.to_llm_context())

print("✅ CRMAgent defined.")


# ## 14. Demo Workflow

# In[15]:




# In[16]:


# ── Step 1: Initialize the Agent ──────────────────────────────────────────────
# Set GROQ_API_KEY in .env or pass directly:
# agent = CRMAgent(..., groq_api_key="gsk_...")

agent = CRMAgent(
    org_name        = "Shetty Enterprises",
    org_description = "We sell all types of electronic appliances and provide the best quality services.",
    support_number  = "1800-123-4567",
    email_id        = "shettyenterprise@gmail.com",
)


# In[17]:


# ── Step 2: Load Your Excel / CSV File ────────────────────────────────────────
# Update the path to your actual file:
schema = agent.load_file("sales.xlsx")

# Print schema for reference
agent.schema_summary()


# In[18]:


# ── Step 3: Natural Language Query ────────────────────────────────────────────
result = agent.ask("Show me all customers who bought Samsung phones")


# In[ ]:


# ── Step 4: Follow-up Query (uses conversation context) ────────────────────────
result = agent.ask("Only show those from Mysore")


# In[22]:


# ── Step 5: Date-based Query ───────────────────────────────────────────────────
result = agent.ask("Get all customers whose warranty expires within the next 30 days")

# Inspect the generated plan and SQL:
print("\n── Query Plan ──────────────────────────────")
print(json.dumps(result.get("plan", {}), indent=2))
print("\n── Generated SQL ───────────────────────────")
print(result.get("sql", ""))


# In[21]:


# ── Step 6: Aggregation Query ─────────────────────────────────────────────────
result = agent.ask("How many customers per city, sorted by count descending?")


# In[23]:


# ── Step 7: Export Results ────────────────────────────────────────────────────
csv_path   = agent.export("csv")
excel_path = agent.export("excel")
print(f"Saved: {csv_path}, {excel_path}")


# In[24]:


# ── Step 8: Email Campaign (requires email config) ─────────────────────────────
# First run the warranty query to populate last_data:
result    = agent.ask("Customers whose warranty expires in the next 30 days", verbose=False)
recipients = result.get("data", [])
print(f"Found {len(recipients)} recipients.")

# Create campaign (draft)
campaign = agent.create_campaign(
    context    = "Inform customers that their warranty is expiring soon and offer a discounted extension.",
    recipients = recipients,
)

# Preview for first recipient
agent.preview_campaign(campaign, recipient_index=0)


# In[27]:


# ── Step 9: Approve & Send ────────────────────────────────────────────────────
# ⚠️  APPROVAL REQUIRED — Uncomment only after reviewing the preview above.
# This will send real emails to all recipients.

result = agent.approve_and_send(campaign)
print("Campaign is in 'pending_approval' status. Uncomment the line above to send.")


# ## 15. Testing Examples

# In[ ]:


# ── Unit Tests for QueryBuilder (no LLM required) ────────────────────────────

def make_test_schema() -> SchemaSummary:
    return SchemaSummary(
        table_name    = "crm_data",
        row_count     = 100,
        email_column  = "Email",
        name_column   = "Customer Name",
        date_columns  = ["Purchase Date", "Warranty Expiry"],
        columns       = [
            ColumnMeta("Customer Name", "text",    0.0, 100, ["Alice"]),
            ColumnMeta("Email",         "text",    0.0, 100, ["alice@example.com"]),
            ColumnMeta("Product",       "text",    0.0,  20, ["Samsung TV"]),
            ColumnMeta("City",          "text",    0.0,  10, ["Mysore"]),
            ColumnMeta("Amount",        "float",   5.0,  90, ["15000.0"]),
            ColumnMeta("Purchase Date", "date",    0.0, 100, ["2024-01-15"]),
            ColumnMeta("Warranty Expiry","date",   0.0, 100, ["2025-01-15"]),
        ],
    )

schema  = make_test_schema()
builder = QueryBuilder(schema)

print("\n=== TEST 1: Basic text filter ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Product", operator="contains", value="Samsung")
])
sql, params = builder.build(plan)
print(sql)
print("Params:", params)

print("\n=== TEST 2: Multi-filter with AND/OR ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Product", operator="contains", value="Samsung"),
    FilterCondition(column="City",    operator="equals",   value="Mysore", logic="AND"),
    FilterCondition(column="Amount",  operator="greater_than", value=10000, logic="OR"),
])
sql, params = builder.build(plan)
print(sql)
print("Params:", params)

print("\n=== TEST 3: Date shortcut ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Warranty Expiry", operator="next_30_days")
])
sql, params = builder.build(plan)
print(sql)

print("\n=== TEST 4: Aggregation ===")
plan = QueryPlan(
    operation    = "aggregate",
    group_by     = ["City"],
    aggregations = [AggregationSpec(function="count", column="Customer Name", alias="Total")],
    sort         = [SortSpec(column="Total", direction="desc")],
    limit        = 10,
)
sql, params = builder.build(plan)
print(sql)

print("\n=== TEST 5: Validation error on missing column ===")
try:
    plan = QueryPlan(filters=[
        FilterCondition(column="salary", operator="greater_than", value=50000)
    ])
    builder.build(plan)
except QueryValidationError as e:
    print(f"✅ Got expected error:\n{e}")

print("\n=== TEST 6: Between filter ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Amount", operator="between", value=5000, value2=20000)
])
sql, params = builder.build(plan)
print(sql)
print("Params:", params)


# In[ ]:


# ── Integration Test with In-Memory DuckDB ────────────────────────────────────

# Create sample DataFrame
sample_df = pd.DataFrame({
    "Customer Name" : ["Alice", "Bob", "Carol", "Dave", "Eve"],
    "Email"         : ["alice@test.com", "bob@test.com", "carol@test.com", "dave@test.com", "eve@test.com"],
    "Product"       : ["Samsung TV", "LG Fridge", "Samsung Phone", "Sony TV", "Samsung Tablet"],
    "City"          : ["Mysore", "Bangalore", "Mysore", "Chennai", "Mysore"],
    "Amount"        : [15000, 45000, 12000, 55000, 18000],
    "Purchase Date" : pd.to_datetime(["2024-01-10", "2024-02-15", "2025-01-01", "2024-12-01", "2025-05-20"]),
    "Warranty Expiry": pd.to_datetime(["2026-01-10", "2026-02-15", "2026-01-01", "2025-12-01", "2026-05-20"]),
})

# Temporarily save to xlsx for the loader
sample_path = "/tmp/test_crm_data.xlsx"
sample_df.to_excel(sample_path, index=False)

# Load into a fresh DuckDB manager
test_db     = DuckDBManager()
test_schema = test_db.load_file(sample_path)
test_builder = QueryBuilder(test_schema)

print("\n=== Integration Test: Samsung customers in Mysore ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Product", operator="contains", value="Samsung"),
    FilterCondition(column="City",    operator="equals",   value="Mysore"),
])
sql, params = test_builder.build(plan)
result      = test_db.execute(sql, params)

print(f"Rows: {result['row_count']}")
for r in result["data"]:
    print(" ", r["Customer Name"], "|", r["Product"], "|", r["City"])

print("\n=== Integration Test: Amount > 14000 ===")
plan = QueryPlan(filters=[
    FilterCondition(column="Amount", operator="greater_than", value=14000)
], sort=[SortSpec(column="Amount", direction="desc")])
sql, params = test_builder.build(plan)
result      = test_db.execute(sql, params)
print(f"Rows: {result['row_count']}")
for r in result["data"]:
    print(" ", r["Customer Name"], "|", r["Amount"])

print("\n✅ All integration tests passed.")


# In[ ]:


# ── Schema Analyzer Test ──────────────────────────────────────────────────────
analyzer = SchemaAnalyzer()
s        = analyzer.analyze(sample_df, "test_table")

print("Schema Summary:\n")
print(s.to_llm_context())
print(f"\nEmail column : {s.email_column}")
print(f"Name  column : {s.name_column}")
print(f"Date  columns: {s.date_columns}")


# In[ ]:


# ── Email Personalization Test ────────────────────────────────────────────────
row = {
    "Customer Name"   : "Alice",
    "Product"         : "Samsung TV",
    "Warranty Expiry" : "2026-01-10",
}

template = """\
Dear {{Customer Name}},

Your {{Product}} warranty expires on {{Warranty Expiry}}.
Contact us at 1800-123-4567 to extend it at a 20% discount.

Best regards,
Shetty Enterprises
"""

personalized = EmailGenerator.personalize(template, row)
print(personalized)


# In[ ]:


# ── Audit Log Review ──────────────────────────────────────────────────────────
audit = AuditLogger()
logs  = audit.get_log(last_n=10)
if logs:
    print(f"Last {len(logs)} audit entries:")
    for e in logs:
        print(f"  [{e.get('event')}] {e.get('logged_at')}")
else:
    print("No audit logs yet. Run queries or campaigns to generate logs.")

