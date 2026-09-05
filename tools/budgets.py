from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from auth import get_user_id
from db import get_connection, validate_category
from models import BudgetOut, require_positive_amount


def _budget_to_dict(conn, budget_id: int, user_id: str) -> dict:
    row = conn.execute(
        """
        SELECT b.id, c.name AS category, b.monthly_limit
        FROM budgets b
        LEFT JOIN categories c ON c.id = b.category_id
        WHERE b.id = ? AND b.user_id = ?
        """,
        (budget_id, user_id),
    ).fetchone()
    if row is None:
        raise ToolError(f"Budget {budget_id} not found for the current user.")
    return dict(row)


async def set_budget(monthly_limit: float, category: str | None = None) -> dict:
    """Upsert a monthly budget. Omit `category` for an overall budget; otherwise
    `category` must be one of the builtin category names."""
    user_id = get_user_id()
    require_positive_amount(monthly_limit, field_name="monthly_limit")

    conn = get_connection()
    try:
        if category is None:
            existing = conn.execute(
                """
                SELECT id FROM budgets
                WHERE user_id = ? AND category_id IS NULL
                """,
                (user_id,),
            ).fetchone()
            if existing is None:
                cursor = conn.execute(
                    """
                    INSERT INTO budgets (user_id, category_id, monthly_limit)
                    VALUES (?, NULL, ?)
                    """,
                    (user_id, monthly_limit),
                )
                budget_id = cursor.lastrowid
            else:
                conn.execute(
                    """
                    UPDATE budgets
                    SET monthly_limit = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (monthly_limit, existing["id"], user_id),
                )
                budget_id = existing["id"]
        else:
            category_id, _ = validate_category(conn, category)
            cursor = conn.execute(
                """
                INSERT INTO budgets (user_id, category_id, monthly_limit)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, category_id) DO UPDATE SET
                    monthly_limit = excluded.monthly_limit
                """,
                (user_id, category_id, monthly_limit),
            )
            if cursor.lastrowid:
                budget_id = cursor.lastrowid
            else:
                row = conn.execute(
                    """
                    SELECT id FROM budgets
                    WHERE user_id = ? AND category_id = ?
                    """,
                    (user_id, category_id),
                ).fetchone()
                budget_id = row["id"]

        conn.commit()
        return BudgetOut.model_validate(
            _budget_to_dict(conn, budget_id, user_id)
        ).model_dump()
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    mcp.tool(set_budget)
