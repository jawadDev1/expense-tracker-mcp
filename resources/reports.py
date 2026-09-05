from datetime import date

from fastmcp import FastMCP
from fastmcp.exceptions import AuthorizationError, ResourceError

from auth import get_user_id
from db import get_connection
from models import ExpenseOut

EXPENSE_SELECT = """
    SELECT
        e.id,
        e.amount,
        c.name AS category,
        s.name AS subcategory,
        e.description,
        e.expense_date,
        e.created_at
    FROM expenses e
    JOIN categories c ON c.id = e.category_id
    LEFT JOIN subcategories s ON s.id = e.subcategory_id
"""


def _require_matching_user(user_id: str) -> str:
    token_user = get_user_id()
    if user_id != token_user:
        raise AuthorizationError(
            "Resource user_id does not match the authenticated user."
        )
    return token_user


def _parse_year_month(year: str, month: str) -> tuple[str, str]:
    if not year.isdigit() or len(year) != 4:
        raise ResourceError(f"year must be a 4-digit calendar year, got '{year}'.")
    if not month.isdigit():
        raise ResourceError(f"month must be a number from 1 to 12, got '{month}'.")
    month_num = int(month)
    if month_num < 1 or month_num > 12:
        raise ResourceError(f"month must be a number from 1 to 12, got '{month}'.")
    return year, f"{month_num:02d}"


def _rows_to_expenses(rows) -> list[dict]:
    return [ExpenseOut.model_validate(dict(row)).model_dump() for row in rows]


def _sum_by_category(rows) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        totals[row["category"]] = totals.get(row["category"], 0.0) + float(row["amount"])
    return totals


async def recent_expenses(user_id: str) -> list[dict]:
    """Last 20 expenses for the authenticated user."""
    user_id = _require_matching_user(user_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            EXPENSE_SELECT
            + """
            WHERE e.user_id = ?
            ORDER BY e.expense_date DESC, e.created_at DESC, e.id DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
        return _rows_to_expenses(rows)
    finally:
        conn.close()


async def expenses_by_month(user_id: str, year: str, month: str) -> dict:
    """Expenses for a given user/year/month, grouped by category, with a total."""
    user_id = _require_matching_user(user_id)
    year, month = _parse_year_month(year, month)
    prefix = f"{year}-{month}-"
    conn = get_connection()
    try:
        rows = conn.execute(
            EXPENSE_SELECT
            + """
            WHERE e.user_id = ? AND e.expense_date LIKE ?
            ORDER BY e.expense_date, e.id
            """,
            (user_id, prefix + "%"),
        ).fetchall()
        expenses = _rows_to_expenses(rows)
        by_category: dict[str, dict] = {}
        for expense in expenses:
            bucket = by_category.setdefault(
                expense["category"],
                {"total": 0.0, "expenses": []},
            )
            bucket["expenses"].append(expense)
            bucket["total"] += expense["amount"]
        return {
            "year": year,
            "month": month,
            "total": sum(expense["amount"] for expense in expenses),
            "by_category": by_category,
        }
    finally:
        conn.close()


async def spending_summary(user_id: str) -> dict:
    """All-time and current-month spending grouped by category, plus
    budget vs. actual if a budget is set."""
    user_id = _require_matching_user(user_id)
    today = date.today()
    period = today.strftime("%Y-%m")
    month_prefix = period + "-"

    conn = get_connection()
    try:
        all_rows = conn.execute(
            EXPENSE_SELECT + " WHERE e.user_id = ?",
            (user_id,),
        ).fetchall()
        month_rows = conn.execute(
            EXPENSE_SELECT + " WHERE e.user_id = ? AND e.expense_date LIKE ?",
            (user_id, month_prefix + "%"),
        ).fetchall()
        budget_rows = conn.execute(
            """
            SELECT c.name AS category, b.monthly_limit
            FROM budgets b
            LEFT JOIN categories c ON c.id = b.category_id
            WHERE b.user_id = ?
            """,
            (user_id,),
        ).fetchall()

        all_time_by_category = _sum_by_category(all_rows)
        current_month_by_category = _sum_by_category(month_rows)
        current_month_total = sum(current_month_by_category.values())

        overall_budget = None
        category_budgets = []
        for row in budget_rows:
            actual = (
                current_month_total
                if row["category"] is None
                else current_month_by_category.get(row["category"], 0.0)
            )
            entry = {
                "category": row["category"],
                "monthly_limit": float(row["monthly_limit"]),
                "actual": actual,
                "remaining": float(row["monthly_limit"]) - actual,
                "over_limit": actual > float(row["monthly_limit"]),
            }
            if row["category"] is None:
                overall_budget = {k: v for k, v in entry.items() if k != "category"}
            else:
                category_budgets.append(entry)

        return {
            "period": period,
            "all_time": {
                "total": sum(all_time_by_category.values()),
                "by_category": all_time_by_category,
            },
            "current_month": {
                "total": current_month_total,
                "by_category": current_month_by_category,
            },
            "budgets": {
                "overall": overall_budget,
                "by_category": category_budgets,
            },
        }
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    mcp.resource("expenses://{user_id}/recent")(recent_expenses)
    mcp.resource("expenses://{user_id}/by-month/{year}/{month}")(expenses_by_month)
    mcp.resource("expenses://{user_id}/summary")(spending_summary)
