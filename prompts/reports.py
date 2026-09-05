from fastmcp import FastMCP

from auth import get_user_id


def monthly_report(year: str, month: str) -> str:
    """Generate a prompt asking the model to summarize the user's spending for
    the given month, pulling from expenses://{user_id}/by-month/{year}/{month}."""
    user_id = get_user_id()
    month_padded = month.zfill(2) if month.isdigit() else month
    uri = f"expenses://{user_id}/by-month/{year}/{month_padded}"
    return f"""Summarize this user's spending for {year}-{month_padded}.

Read the MCP resource `{uri}` and use only that data. Do not invent expenses or categories.

Cover:
- total spend for the month
- breakdown by category
- notable individual expenses
- any patterns or outliers worth flagging
"""


def budget_check() -> str:
    """Generate a prompt asking the model to compare current spending against
    the user's budgets (overall and per-category) using expenses://{user_id}/summary,
    and flag anything over or close to its limit."""
    user_id = get_user_id()
    uri = f"expenses://{user_id}/summary"
    return f"""Compare this user's current spending against their budgets.

Read the MCP resource `{uri}` and use only that data. Do not invent numbers.

The summary includes all-time totals, current-month totals, and budgets (overall and per-category). Compare monthly budgets to **current-month** actuals, not all-time totals.

Flag:
- any budget that is already over its limit
- any budget that is close to its limit (for example, remaining is under 15% of the monthly limit)
- categories with current-month spend but no matching budget, if useful as context

State remaining amounts clearly for the overall budget and each category budget.
"""


def register(mcp: FastMCP) -> None:
    mcp.prompt(monthly_report)
    mcp.prompt(budget_check)
