"""
schema_analyzer.py
Inspects a Pandas DataFrame and produces a rich SchemaSummary.
Detects column types, nullability, cardinality, and example values.
No hardcoded column names — works with any schema.
"""

from typing import Any, List

import pandas as pd

from models import ColumnMeta, SchemaSummary


class SchemaAnalyzer:
    # Heuristic keywords to identify special columns
    _EMAIL_HINTS = {"email", "mail", "emailaddress", "e-mail"}
    _NAME_HINTS  = {"name", "customername", "clientname", "fullname",
                    "contactname", "employeename"}

    def analyze(self, df: pd.DataFrame, table_name: str = "data") -> SchemaSummary:
        columns: List[ColumnMeta] = []
        email_col = None
        name_col  = None
        date_cols: List[str] = []

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
        series   = df[col]
        n        = len(series)
        n_null   = series.isna().sum()
        non_null = series.dropna()

        dtype    = self._infer_dtype(series)
        examples: List[Any] = []
        min_val  = None
        max_val  = None

        if len(non_null) > 0:
            sample   = non_null.head(5).tolist()
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

        if "datetime" in pd_dtype: return "datetime"
        if "date"     in pd_dtype: return "date"
        if "bool"     in pd_dtype: return "boolean"
        if "int"      in pd_dtype: return "integer"
        if "float"    in pd_dtype: return "float"

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
