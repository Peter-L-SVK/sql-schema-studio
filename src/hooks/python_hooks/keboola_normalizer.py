# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola Normalizer Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Keboola Normalizer Hook - Data normalization via Keboola platform.

This hook validates CSV files locally and optionally uploads them to
Keboola Storage for advanced ETL/ELT processing.

The hook detects data quality issues such as:
- Missing values
- Invalid email formats
- Invalid date formats
- Invalid payment methods
- Invalid order statuses
- Invalid categories
- Invalid price/quantity values
"""

import json
import os
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional, Set

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import Keboola client
try:
    from kbcstorage.client import Client

    KEBOOLA_AVAILABLE = True
    logger.info("Keboola client (kbcstorage) loaded successfully")
except ImportError:
    KEBOOLA_AVAILABLE = False
    logger.warning("Keboola client not installed. Run: pip install kbcstorage")


class CSVValidationResult(TypedDict, total=False):
    """Result of CSV validation."""

    total_rows: int
    rows_with_issues: List[int]
    issues: List[Dict[str, Any]]
    error_samples: List[str]
    issue_count: int


class KeboolaNormalizerHook(BaseHook):
    """Data normalization hook using Keboola platform.

    Performs local CSV validation and can optionally upload to Keboola
    for advanced ETL/ELT processing.

    Configuration is stored in ~/.config/sql-schema-studio/keboola_config.json
    """

    def __init__(self):
        """Initialize the hook and load configuration."""
        super().__init__()
        self._client: Optional[Any] = None  # kbcstorage.client.Client
        self._config: Dict[str, Any] = self._load_config()

    # ======================================================================
    # Config management
    # ======================================================================

    def _get_config_path(self) -> Path:
        """Get path to configuration file."""
        return Path.home() / ".config" / "sql-schema-studio" / "keboola_config.json"

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults."""
        config_path = self._get_config_path()
        default_config = {
            "api_url": "https://connection.keboola.com/",
            "token": "",
            "bucket": "in.c-sql-schema-studio",
            "source_table": "raw_orders",
            "output_table": "normalized_orders",
            "flow_id": "",
            "local_mode": True,
        }

        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                logger.error(f"Failed to load Keboola config: {e}")

        return default_config

    def _save_config(self) -> None:
        """Save configuration to file."""
        config_path = self._get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            logger.info("Keboola config saved")
        except Exception as e:
            logger.error(f"Failed to save Keboola config: {e}")

    # ======================================================================
    # Keboola client
    # ======================================================================

    def _get_client(self) -> Optional[Any]:
        """Get or create Keboola client using kbcstorage."""
        if not KEBOOLA_AVAILABLE:
            logger.error("Keboola client not installed")
            return None

        if self._client is None:
            token = self._config.get("token")
            if not token:
                logger.warning("No Keboola API token configured")
                return None
            try:
                self._client = Client(token, self._config.get("api_url"))
                logger.info("Keboola client initialized (kbcstorage)")
            except Exception as e:
                logger.error(f"Failed to initialize Keboola client: {e}")
                return None

        return self._client

    # ======================================================================
    # BaseHook implementation
    # ======================================================================

    def get_metadata(self) -> Dict[str, Any]:
        """Return hook metadata."""
        return {
            "name": "Keboola Normalizer",
            "version": "1.0.0",
            "author": "Peter Leukanič",
            "description": "Data normalization using Keboola platform (cloud ETL/ELT)",
            "triggers": [
                str(HookTrigger.SCHEMA_CHANGED.value),
                str(HookTrigger.SCHEDULED_INTERVAL.value),
            ],
        }

    def validate(self) -> bool:
        """Validate configuration and connection."""
        if not KEBOOLA_AVAILABLE:
            logger.error("Keboola client not available")
            return False

        if self._config.get("local_mode", True):
            return True

        client = self._get_client()
        if client is None:
            return False

        try:
            client.buckets.list()
            logger.info("Keboola connection validated")
            return True
        except Exception as e:
            logger.error(f"Keboola connection validation failed: {e}")
            return False

    async def execute(self, context: HookContext) -> Dict[str, Any]:
        """Execute Keboola normalization.

        Expected context.data:
            - file_path: str - path to CSV file
            - local_only: bool - if True, only local validation

        Returns:
            Dict with status, message, recommendations, error_samples, etc.
        """
        result: Dict[str, Any] = {
            "status": "ok",
            "message": "",
            "recommendations": [],
            "error_samples": [],
            "tables_analyzed": 0,
        }

        file_path = context.data.get("file_path")
        if not file_path or not os.path.exists(file_path):
            result["status"] = "error"
            result["message"] = "No valid CSV file provided"
            return result

        # 1. Local validation
        validation_result = self._validate_csv(file_path)
        result["tables_analyzed"] = validation_result["total_rows"]

        if validation_result["issues"]:
            result["recommendations"] = self._generate_recommendations(validation_result)
            result["error_samples"] = validation_result["error_samples"][:5]
            result["message"] = (
                f"Found {validation_result['issue_count']} issues in "
                f"{len(validation_result['rows_with_issues'])} rows"
            )
        else:
            result["message"] = "All data looks clean!"

        # 2. Upload to Keboola if requested
        if not context.data.get("local_only", False) and self._config.get("token"):
            upload_result = await self._upload_to_keboola(file_path)
            result["keboola"] = upload_result

        return result

    # ======================================================================
    # Local CSV validation
    # ======================================================================

    def _validate_csv(self, file_path: str) -> CSVValidationResult:
        """Validate CSV file and detect data quality issues."""
        issues: List[Dict[str, Any]] = []
        rows_with_issues: Set[int] = set()
        error_samples: List[str] = []
        total_rows = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):
                    total_rows = row_num - 1
                    row_has_issue = False

                    for col, value in row.items():
                        col_issues = self._validate_column(col, value.strip(), row_num)
                        if col_issues:
                            issues.extend(col_issues)
                            row_has_issue = True
                            if len(error_samples) < 5:
                                error_samples.append(f"Row {row_num}, {col}: {value[:50]}")

                    if row_has_issue:
                        rows_with_issues.add(row_num)

            return {
                "total_rows": total_rows,
                "rows_with_issues": list(rows_with_issues),
                "issues": issues,
                "error_samples": error_samples,
                "issue_count": len(issues),
            }

        except Exception as e:
            logger.error(f"CSV validation failed: {e}")
            return {
                "total_rows": 0,
                "rows_with_issues": [],
                "issues": [],
                "error_samples": [f"Validation error: {str(e)}"],
                "issue_count": 0,
            }

    def _validate_column(self, col: str, value: str, row_num: int) -> List[Dict[str, Any]]:
        """Validate a single column value."""
        if not value:
            return [{"row": row_num, "column": col, "issue": "Empty value", "severity": "MEDIUM"}]

        validators = {
            "Email": self._validate_email,
            "TransactionDate": self._validate_date,
            "PaymentMethod": self._validate_payment_method,
            "OrderStatus": self._validate_order_status,
            "Category": self._validate_category,
            "Price": self._validate_price,
            "Quantity": self._validate_quantity,
        }

        if col in validators:
            issue = validators[col](value, row_num, col)
            return [issue] if issue else []

        return []

    def _validate_email(self, value: str, row_num: int, col: str) -> Optional[Dict[str, Any]]:
        """Validate email format."""
        if value.lower() in ("invalid_email", "not_an_email"):
            return {
                "row": row_num,
                "column": col,
                "issue": "Invalid placeholder email",
                "severity": "HIGH",
            }
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, value):
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid email: {value}",
                "severity": "HIGH",
            }
        return None

    def _validate_date(self, value: str, row_num: int, col: str) -> Optional[Dict[str, Any]]:
        """Validate date format."""
        formats = ["%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y"]
        for fmt in formats:
            try:
                datetime.strptime(value.split()[0], fmt)
                return None
            except (ValueError, IndexError):
                continue
        return {
            "row": row_num,
            "column": col,
            "issue": f"Invalid date: {value}",
            "severity": "MEDIUM",
        }

    def _validate_payment_method(
        self, value: str, row_num: int, col: str
    ) -> Optional[Dict[str, Any]]:
        """Validate payment method."""
        valid = {"Credit Card", "PayPal", "Bank Transfer"}
        if value not in valid:
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid payment: {value}",
                "severity": "MEDIUM",
            }
        return None

    def _validate_order_status(
        self, value: str, row_num: int, col: str
    ) -> Optional[Dict[str, Any]]:
        """Validate order status."""
        valid = {"Pending", "Completed", "Refunded", "Shipped", "Delivered"}
        if value not in valid:
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid status: {value}",
                "severity": "MEDIUM",
            }
        return None

    def _validate_category(self, value: str, row_num: int, col: str) -> Optional[Dict[str, Any]]:
        """Validate product category."""
        valid = {
            "Electronics",
            "Sports",
            "Toys",
            "Health",
            "Books",
            "Beauty",
            "Fashion",
            "Home & Garden",
        }
        if value not in valid:
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid category: {value}",
                "severity": "LOW",
            }
        return None

    def _validate_price(self, value: str, row_num: int, col: str) -> Optional[Dict[str, Any]]:
        """Validate price value."""
        try:
            float(value)
            return None
        except ValueError:
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid price: {value}",
                "severity": "HIGH",
            }

    def _validate_quantity(self, value: str, row_num: int, col: str) -> Optional[Dict[str, Any]]:
        """Validate quantity value."""
        try:
            qty = int(value)
            if qty <= 0:
                return {
                    "row": row_num,
                    "column": col,
                    "issue": f"Quantity must be >0: {value}",
                    "severity": "HIGH",
                }
            return None
        except ValueError:
            return {
                "row": row_num,
                "column": col,
                "issue": f"Invalid quantity: {value}",
                "severity": "HIGH",
            }

    # ======================================================================
    # Recommendation generation
    # ======================================================================

    def _generate_recommendations(
        self, validation_result: CSVValidationResult
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on validation results."""
        recommendations: List[Dict[str, Any]] = []
        issue_counts: Dict[str, int] = {}

        for issue in validation_result.get("issues", []):
            col = issue.get("column", "unknown")
            issue_counts[col] = issue_counts.get(col, 0) + 1

        for col, count in issue_counts.items():
            if count > 5:
                recommendations.append(
                    {
                        "table": "CSV Data",
                        "priority": "HIGH",
                        "action": f"Fix {count} issues in '{col}' column",
                        "reason": f"Column '{col}' has {count} invalid entries",
                    }
                )
            elif count > 2:
                recommendations.append(
                    {
                        "table": "CSV Data",
                        "priority": "MEDIUM",
                        "action": f"Review {count} issues in '{col}' column",
                        "reason": f"Column '{col}' has {count} invalid entries",
                    }
                )

        if validation_result.get("issue_count", 0) > 0:
            recommendations.append(
                {
                    "table": "CSV Data",
                    "priority": (
                        "HIGH" if validation_result.get("issue_count", 0) > 20 else "MEDIUM"
                    ),
                    "action": "Run Keboola normalization",
                    "reason": f"Found {validation_result.get('issue_count', 0)} data quality issues",
                }
            )

        return recommendations

    # ======================================================================
    # Keboola upload
    # ======================================================================

    async def _upload_to_keboola(self, file_path: str) -> Dict[str, Any]:
        """Upload CSV to Keboola Storage using kbcstorage."""
        result: Dict[str, Any] = {"status": "error", "message": ""}

        client = self._get_client()
        if client is None:
            result["message"] = "Keboola client not available"
            return result

        try:
            bucket = self._config.get("bucket", "in.c-sql-schema-studio")
            table_name = self._config.get("source_table", "raw_orders")

            with open(file_path, "rb") as f:
                table = client.tables.create(
                    bucket_id=bucket,
                    name=table_name,
                    data=f,
                    primary_key=["TransactionID"],
                )

            result["status"] = "ok"
            result["message"] = f"Uploaded to {bucket}.{table_name}"
            result["table_id"] = table.get("id")

            logger.info(f"File uploaded to Keboola: {bucket}.{table_name}")

        except Exception as e:
            logger.error(f"Keboola upload failed: {e}")
            result["message"] = f"Upload failed: {str(e)}"

        return result


# Plugin class for discovery
class Plugin(KeboolaNormalizerHook):
    """Plugin entry point for hook discovery."""

    pass
