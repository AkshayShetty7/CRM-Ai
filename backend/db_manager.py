import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

import duckdb
import pandas as pd

from config import EXPORT_DIR, logger
from models import EmailCampaign, SchemaSummary
from schema_analyzer import SchemaAnalyzer


class DuckDBManager:
    TABLE_NAME = "crm_data"

    def __init__(self):
        self.conn          = duckdb.connect(":memory:")
        self.schema        : Optional[SchemaSummary] = None
        self._last_results : List[Dict] = []
        self._campaigns    : Dict[str, EmailCampaign] = {}

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> SchemaSummary:
        """Load .xlsx / .xls / .csv into DuckDB and return a SchemaSummary."""
        path = str(path)
        df   = pd.read_csv(path) if path.endswith(".csv") else pd.read_excel(path)

        df.columns = [str(c).strip() for c in df.columns]

        for col in df.select_dtypes(include="object").columns:
            sample = df[col].dropna().head(20)
            if SchemaAnalyzer._looks_like_date(sample):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass

        analyzer     = SchemaAnalyzer()
        self.schema  = analyzer.analyze(df, self.TABLE_NAME)

        try:
            self.conn.execute(f"DROP VIEW IF EXISTS {self.TABLE_NAME}")
        except Exception:
            pass
        self.conn.register(self.TABLE_NAME, df)

        logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} columns → '{self.TABLE_NAME}'")
        return self.schema

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: Optional[List] = None) -> Dict:
        """Execute a validated SELECT statement. Returns result dict."""
        error = self._validate_sql(sql)
        if error:
            return {"error": error, "sql": sql}

        try:
            result_df = (
                self.conn.execute(sql, params).fetchdf()
                if params
                else self.conn.execute(sql).fetchdf()
            )
            records            = result_df.to_dict(orient="records")
            self._last_results = records
            logger.info(f"Query OK → {len(records):,} rows")
            return {
                "row_count": len(records),
                "columns":   result_df.columns.tolist(),
                "data":      records,
                "sql":       sql,
            }
        except Exception as exc:
            logger.error(f"Query FAILED: {exc}\nSQL: {sql}")
            return {"error": str(exc), "sql": sql}

    # ── Export ────────────────────────────────────────────────────────────────

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
    

    def clear_data(self):

        try:
            self.conn.unregister(self.TABLE_NAME)
        except Exception:
            pass

        self.schema = None
        self._last_results = []
        self._campaigns = {}

        logger.info("Dataset cleared")
    # ── Helpers ───────────────────────────────────────────────────────────────



    def _validate_sql(self, sql: str) -> Optional[str]:
        cleaned = sql.lower().strip()
        if not cleaned.startswith("select"):
            return "Only SELECT statements are permitted."
        forbidden = [
            "drop", "delete", "update", "insert", "alter",
            "truncate", "create", "replace", "merge", "grant", "revoke",
        ]
        for kw in forbidden:
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
