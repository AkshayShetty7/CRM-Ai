"""
query_plan.py
Pydantic models that describe the structured query intent produced by the LLM.
Python builds SQL from these models — the LLM never writes SQL directly.
"""

import json
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from config import DEFAULT_QUERY_LIMIT, MAX_QUERY_LIMIT

# ── Operator / function type aliases ─────────────────────────────────────────
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

AggFunction   = Literal["count", "sum", "avg", "min", "max", "count_distinct"]
SortDirection = Literal["asc", "desc"]


# ── Pydantic models ───────────────────────────────────────────────────────────
class FilterCondition(BaseModel):
    column   : str
    operator : FilterOperator
    value    : Optional[Any]        = None
    value2   : Optional[Any]        = None   # for between / date_between
    logic    : Literal["AND", "OR"] = "AND"  # how this joins with the previous filter


class AggregationSpec(BaseModel):
    function : AggFunction
    column   : str
    alias    : Optional[str] = None


class SortSpec(BaseModel):
    column    : str
    direction : SortDirection = "asc"


class QueryPlan(BaseModel):
    """
    Structured query intent produced by the LLM.
    Python builds SQL from this — the LLM never writes SQL.
    """
    operation      : Literal["filter", "aggregate", "top_n", "search"] = "filter"
    filters        : List[FilterCondition] = Field(default_factory=list)
    group_by       : List[str]             = Field(default_factory=list)
    aggregations   : List[AggregationSpec] = Field(default_factory=list)
    select_columns : List[str]             = Field(
        default_factory=list,
        description="Specific columns to return; empty = SELECT *",
    )
    sort           : List[SortSpec]        = Field(default_factory=list)
    limit          : int                   = Field(DEFAULT_QUERY_LIMIT, ge=1, le=MAX_QUERY_LIMIT)
    intent_summary : str                   = ""


# ── JSON schema string sent to the LLM ───────────────────────────────────────
QUERY_PLAN_SCHEMA_JSON = json.dumps(QueryPlan.model_json_schema(), indent=2)
