from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from auth import get_user_id
from db import expense_to_dict, get_connection, validate_category
from models import ExpenseOut, parse_expense_date, require_positive_amount


async def add_expense(
    amount: float,
    category: str,
    description: str,
    expense_date: str,
    subcategory: str | None = None,
) -> dict:
    """Add a new expense. `category` must be one of the values returned by the
    `expenses://categories/builtin` resource. `subcategory`, if given, must belong
    to that category."""
    user_id = get_user_id()
    require_positive_amount(amount)
    expense_date = parse_expense_date(expense_date)

    conn = get_connection()
    try:
        category_id, subcategory_id = validate_category(conn, category, subcategory)
        cursor = conn.execute(
            """
            INSERT INTO expenses (
                user_id, amount, category_id, subcategory_id, description, expense_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, amount, category_id, subcategory_id, description, expense_date),
        )
        conn.commit()
        return ExpenseOut.model_validate(
            expense_to_dict(conn, cursor.lastrowid, user_id)
        ).model_dump()
    finally:
        conn.close()


async def update_expense(
    expense_id: int,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    expense_date: str | None = None,
) -> dict:
    """Partially update an expense owned by the authenticated user."""
    user_id = get_user_id()
    if amount is not None:
        require_positive_amount(amount)
    if expense_date is not None:
        expense_date = parse_expense_date(expense_date)

    conn = get_connection()
    try:
        existing = conn.execute(
            """
            SELECT e.*, c.name AS category_name
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            WHERE e.id = ? AND e.user_id = ?
            """,
            (expense_id, user_id),
        ).fetchone()
        if existing is None:
            raise ToolError(f"Expense {expense_id} not found for the current user.")

        category_id = existing["category_id"]
        subcategory_id = existing["subcategory_id"]

        if category is not None or subcategory is not None:
            resolved_category = category if category is not None else existing["category_name"]
            if subcategory is not None:
                resolved_subcategory = subcategory
            elif existing["subcategory_id"] is not None:
                sub_row = conn.execute(
                    "SELECT name FROM subcategories WHERE id = ?",
                    (existing["subcategory_id"],),
                ).fetchone()
                resolved_subcategory = sub_row["name"] if sub_row else None
            else:
                resolved_subcategory = None
            category_id, subcategory_id = validate_category(
                conn, resolved_category, resolved_subcategory
            )

        conn.execute(
            """
            UPDATE expenses
            SET amount = ?,
                category_id = ?,
                subcategory_id = ?,
                description = ?,
                expense_date = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                existing["amount"] if amount is None else amount,
                category_id,
                subcategory_id,
                existing["description"] if description is None else description,
                existing["expense_date"] if expense_date is None else expense_date,
                expense_id,
                user_id,
            ),
        )
        conn.commit()
        return ExpenseOut.model_validate(
            expense_to_dict(conn, expense_id, user_id)
        ).model_dump()
    finally:
        conn.close()


async def delete_expense(expense_id: int) -> dict:
    """Delete an expense owned by the authenticated user."""
    user_id = get_user_id()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        if cursor.rowcount == 0:
            raise ToolError(f"Expense {expense_id} not found for the current user.")
        conn.commit()
        return {"deleted": True, "id": expense_id}
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    mcp.tool(add_expense)
    mcp.tool(update_expense)
    mcp.tool(delete_expense)
