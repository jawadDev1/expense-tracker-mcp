from fastmcp import FastMCP

from db import get_connection


async def builtin_categories() -> dict:
    """Fixed category → subcategory tree. Clients should read this before calling
    add_expense/set_budget to pick valid values — do not invent new categories."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT c.name AS category, s.name AS subcategory
            FROM categories c
            LEFT JOIN subcategories s ON s.category_id = c.id
            ORDER BY c.id, s.id
            """
        ).fetchall()
        tree: dict[str, list[str]] = {}
        for row in rows:
            tree.setdefault(row["category"], [])
            if row["subcategory"] is not None:
                tree[row["category"]].append(row["subcategory"])
        return tree
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    mcp.resource("expenses://categories/builtin")(builtin_categories)
