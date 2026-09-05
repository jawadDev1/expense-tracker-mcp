import sqlite3
from pathlib import Path

from fastmcp.exceptions import ToolError

from seed_categories import seed_if_empty

DB_PATH = Path(__file__).resolve().parent / "expenses.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subcategories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    UNIQUE(category_id, name)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    subcategory_id INTEGER REFERENCES subcategories(id),
    description TEXT,
    expense_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    monthly_limit REAL NOT NULL CHECK (monthly_limit > 0),
    UNIQUE(user_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, expense_date);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def validate_category(
    conn: sqlite3.Connection,
    category: str,
    subcategory: str | None = None,
) -> tuple[int, int | None]:
    """Resolve builtin category/subcategory names to ids. Case-insensitive exact match."""
    category_row = conn.execute(
        "SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?)",
        (category,),
    ).fetchone()
    if category_row is None:
        raise ToolError(
            f"Unknown category '{category}'. Call the categories/builtin "
            "resource for the valid list."
        )

    if subcategory is None:
        return category_row["id"], None

    subcategory_row = conn.execute(
        """
        SELECT id, name FROM subcategories
        WHERE category_id = ? AND LOWER(name) = LOWER(?)
        """,
        (category_row["id"], subcategory),
    ).fetchone()
    if subcategory_row is None:
        names = [
            row["name"]
            for row in conn.execute(
                """
                SELECT name FROM subcategories
                WHERE category_id = ?
                ORDER BY name
                """,
                (category_row["id"],),
            ).fetchall()
        ]
        valid = ", ".join(names) if names else "(none)"
        raise ToolError(
            f"Unknown subcategory '{subcategory}' for category "
            f"'{category_row['name']}'. Valid subcategories: {valid}."
        )
    return category_row["id"], subcategory_row["id"]


def expense_to_dict(conn: sqlite3.Connection, expense_id: int, user_id: str) -> dict:
    row = conn.execute(
        """
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
        WHERE e.id = ? AND e.user_id = ?
        """,
        (expense_id, user_id),
    ).fetchone()
    if row is None:
        raise ToolError(f"Expense {expense_id} not found for the current user.")
    return dict(row)
