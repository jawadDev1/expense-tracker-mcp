from datetime import date
import re

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_expense_date(expense_date: str) -> str:
    if DATE_RE.fullmatch(expense_date) is None:
        raise ToolError(
            f"expense_date must be ISO 8601 YYYY-MM-DD, got '{expense_date}'."
        )
    try:
        date.fromisoformat(expense_date)
    except ValueError as exc:
        raise ToolError(
            f"expense_date must be a valid calendar date, got '{expense_date}'."
        ) from exc
    return expense_date


def require_positive_amount(amount: float, field_name: str = "amount") -> float:
    if amount <= 0:
        raise ToolError(f"{field_name} must be greater than 0.")
    return amount


class ExpenseOut(BaseModel):
    id: int
    amount: float
    category: str
    subcategory: str | None = None
    description: str | None = None
    expense_date: str
    created_at: str


class BudgetOut(BaseModel):
    id: int
    category: str | None = None
    monthly_limit: float = Field(gt=0)
