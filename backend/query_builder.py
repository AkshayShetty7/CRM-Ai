"""
query_builder.py
Converts a validated QueryPlan into a safe DuckDB SQL statement.

- Uses quoted identifiers for all column names.
- Uses positional parameters ($1, $2, …) for all values.
- Handles date arithmetic with DuckDB's INTERVAL syntax.
- Never interpolates user values directly into the SQL string.
"""

from typing import Any, List, Tuple

from db_manager import DuckDBManager
from models import SchemaSummary
from query_plan import FilterCondition, QueryPlan


class QueryValidationError(Exception):
    """Raised when a QueryPlan references invalid columns or operators."""


class QueryBuilder:
    TABLE = DuckDBManager.TABLE_NAME

    def __init__(self, schema: SchemaSummary):
        self.schema   = schema
        self._col_map = {c.name: c for c in schema.columns}
        self._col_set = {c.name for c in schema.columns}

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self, plan: QueryPlan) -> Tuple[str, List]:
        """Returns (sql_string, params_list). Raises QueryValidationError on bad refs."""
        self._validate_plan(plan)

        params:      List[Any] = []
        where_parts: List[str] = []

        for i, f in enumerate(plan.filters):
            clause, f_params = self._build_filter(f, len(params))
            params.extend(f_params)
            where_parts.append(clause if i == 0 else f"{f.logic} {clause}")

        where_sql = ("WHERE " + " ".join(where_parts)) if where_parts else ""

        # SELECT
        if plan.operation == "aggregate" and plan.aggregations:
            select_sql = self._build_select_aggregate(plan)
        elif plan.select_columns:
            cols       = ", ".join(self._q(c) for c in plan.select_columns)
            select_sql = f"SELECT {cols}"
        else:
            select_sql = "SELECT *"

        # GROUP BY
        group_sql = (
            "GROUP BY " + ", ".join(self._q(c) for c in plan.group_by)
            if plan.group_by else ""
        )

        # ORDER BY
        order_sql = (
            "ORDER BY " + ", ".join(
                f"{self._q(s.column)} {s.direction.upper()}" for s in plan.sort
            )
            if plan.sort else ""
        )

        limit_sql = f"LIMIT {plan.limit}"

        sql = "\n".join(
            p for p in [select_sql, f"FROM {self.TABLE}",
                        where_sql, group_sql, order_sql, limit_sql]
            if p
        )
        return sql, params

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_plan(self, plan: QueryPlan):
        all_referenced = (
            [f.column for f in plan.filters]
            + plan.group_by
            + [a.column for a in plan.aggregations]
            + [s.column for s in plan.sort]
            + plan.select_columns
        )
        errors = []
        for col in all_referenced:
            if col not in self._col_set:
                available = ", ".join(sorted(self._col_set))
                errors.append(
                    f"Column '{col}' does not exist.\nAvailable columns: {available}"
                )
        if errors:
            raise QueryValidationError("\n".join(errors))

    # ── SELECT for aggregates ─────────────────────────────────────────────────

    def _build_select_aggregate(self, plan: QueryPlan) -> str:
        parts = [self._q(c) for c in plan.group_by]
        for agg in plan.aggregations:
            alias = agg.alias or f"{agg.function}_{agg.column}".replace(" ", "_")
            if agg.function == "count_distinct":
                parts.append(f"COUNT(DISTINCT {self._q(agg.column)}) AS {self._q(alias)}")
            elif agg.function == "count" and agg.column == "*":
                parts.append(f"COUNT(*) AS {self._q(alias)}")
            else:
                parts.append(f"{agg.function.upper()}({self._q(agg.column)}) AS {self._q(alias)}")
        return "SELECT " + ", ".join(parts)

    # ── Filter Builder ────────────────────────────────────────────────────────

    def _build_filter(self, f: FilterCondition, param_offset: int) -> Tuple[str, List]:
        col = self._q(f.column)
        op  = f.operator
        p: List[Any] = []

        def P(val):
            p.append(val)
            return f"${param_offset + len(p)}"

        # Text
        if op == "equals":       return f"{col} = {P(f.value)}",                   p
        if op == "not_equals":   return f"{col} != {P(f.value)}",                  p
        if op == "contains":     return f"{col} ILIKE {P(f'%{f.value}%')}",        p
        if op == "not_contains": return f"{col} NOT ILIKE {P(f'%{f.value}%')}",    p
        if op == "starts_with":  return f"{col} ILIKE {P(f'{f.value}%')}",         p
        if op == "ends_with":    return f"{col} ILIKE {P(f'%{f.value}')}",         p

        # Numeric
        if op == "greater_than":  return f"{col} > {P(f.value)}",                  p
        if op == "less_than":     return f"{col} < {P(f.value)}",                  p
        if op == "greater_equal": return f"{col} >= {P(f.value)}",                 p
        if op == "less_equal":    return f"{col} <= {P(f.value)}",                 p
        if op == "between":
            return f"{col} BETWEEN {P(f.value)} AND {P(f.value2)}",                p

        # Null
        if op == "is_null":     return f"{col} IS NULL",     []
        if op == "is_not_null": return f"{col} IS NOT NULL", []

        # List
        if op == "in_list":
            placeholders = ", ".join(P(v) for v in (f.value or []))
            return f"{col} IN ({placeholders})", p
        if op == "not_in_list":
            placeholders = ", ".join(P(v) for v in (f.value or []))
            return f"{col} NOT IN ({placeholders})", p

        # Date shortcuts (no params — pure DuckDB expressions)
        today = "CURRENT_DATE"
        date_shortcuts = {
            "last_7_days":   f"{col} >= {today} - INTERVAL '7 days'",
            "last_30_days":  f"{col} >= {today} - INTERVAL '30 days'",
            "last_90_days":  f"{col} >= {today} - INTERVAL '90 days'",
            "this_week":     f"date_trunc('week',  {col}) = date_trunc('week',  {today})",
            "this_month":    f"date_trunc('month', {col}) = date_trunc('month', {today})",
            "this_year":     f"date_trunc('year',  {col}) = date_trunc('year',  {today})",
            "next_7_days":   f"{col} BETWEEN {today} AND {today} + INTERVAL '7 days'",
            "next_30_days":  f"{col} BETWEEN {today} AND {today} + INTERVAL '30 days'",
            "next_90_days":  f"{col} BETWEEN {today} AND {today} + INTERVAL '90 days'",
        }
        if op in date_shortcuts:
            return date_shortcuts[op], []

        if op == "date_before":  return f"{col} < {P(f.value)}",                   p
        if op == "date_after":   return f"{col} > {P(f.value)}",                   p
        if op == "date_between":
            return f"{col} BETWEEN {P(f.value)} AND {P(f.value2)}",                p

        raise QueryValidationError(f"Unknown operator: '{op}'")

    @staticmethod
    def _q(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'
