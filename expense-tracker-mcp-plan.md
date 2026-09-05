# Expense Tracker MCP Server — Implementation Plan

**Target framework:** FastMCP **v3.4.5** (stable). Do not use v4.x (currently beta,
new sessionless protocol — unnecessary churn for this project).
Docs: https://gofastmcp.com

**Package install:**
```bash
pip install "fastmcp>=3.4.5,<4.0" "pyjwt" --break-system-packages
```

---

## 1. Project structure

```
expense-tracker-mcp/
├── server.py                # FastMCP app entrypoint — mounts tools/resources/prompts
├── auth.py                  # JWTVerifier setup
├── db.py                    # SQLite connection, schema init, seed logic
├── seed_categories.py       # Builtin category/subcategory seed data
├── models.py                # Pydantic models for tool inputs/outputs
├── tools/
│   ├── __init__.py
│   ├── expenses.py           # add_expense, update_expense, delete_expense
│   └── budgets.py             # set_budget
├── resources/
│   ├── __init__.py
│   ├── categories.py          # categories/builtin
│   └── reports.py             # recent, by-month, summary
├── prompts/
│   ├── __init__.py
│   └── reports.py              # monthly_report, budget_check
├── requirements.txt
└── expenses.db               # created at first run
```

---

## 2. Database schema (SQLite, via `db.py`)

```sql
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
    expense_date TEXT NOT NULL,   -- ISO 8601 (YYYY-MM-DD)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),  -- NULL = total/overall budget
    monthly_limit REAL NOT NULL CHECK (monthly_limit > 0),
    UNIQUE(user_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, expense_date);
```

- `db.py` runs schema creation on startup, then calls `seed_categories.seed_if_empty(conn)`.
- Seeding only runs if the `categories` table is empty (checked at startup) — matches
  the "seeded once, fixed after that" decision. No MCP tool ever writes to
  `categories` or `subcategories`.

### Seed data (`seed_categories.py`)

```python
BUILTIN_CATEGORIES = {
    "Transport": ["Fuel", "Public Transit", "Parking", "Ride-share", "Vehicle Maintenance"],
    "Travel": ["Flights", "Hotels", "Vacation Activities", "Travel Insurance"],
    "Food": ["Groceries", "Dining Out", "Coffee/Snacks"],
    "Housing": ["Rent/Mortgage", "Utilities", "Maintenance"],
    "Health": ["Medical", "Pharmacy", "Fitness"],
    "Entertainment": ["Subscriptions", "Movies/Events", "Hobbies"],
    "Shopping": ["Clothing", "Electronics", "Household Goods"],
    "Education": ["Tuition", "Books/Supplies", "Courses"],
    "Other": ["Gifts/Donations", "Fees/Charges", "Miscellaneous"],
}
```

`seed_if_empty(conn)` inserts each category, then each subcategory linked by
`category_id`. Idempotent guard: `SELECT COUNT(*) FROM categories` — skip if > 0.

---

## 3. Auth (`auth.py`)

Use `JWTVerifier` (symmetric HS256, shared secret via env var) — no external IdP
needed for this learning project, but real per-user token validation.

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier

verifier = JWTVerifier(
    secret_key=os.environ["EXPENSE_MCP_JWT_SECRET"],
    algorithm="HS256",
    required_scopes=["user"],
)
```

- Mount on the server: `mcp = FastMCP("Expense Tracker", auth=verifier)`.
- Every tool/resource that needs the caller's identity calls
  `fastmcp.server.dependencies.get_access_token()` and reads `.claims["sub"]` as
  `user_id`. Raise a clear `ToolError` if no token is present (shouldn't happen —
  auth middleware rejects unauthenticated calls first).
- Provide a small `scripts/issue_dev_token.py` helper that mints a local HS256 JWT
  with a chosen `sub` for manual testing (not for production use).

---

## 4. Tools (`tools/expenses.py`, `tools/budgets.py`)

All tools defined with `@mcp.tool`, async, Pydantic-validated inputs, and explicit
category/subcategory validation against the seeded tree (query `categories` /
`subcategories` tables — never trust free-text).

```python
@mcp.tool
async def add_expense(
    amount: float,
    category: str,
    description: str,
    expense_date: str,          # ISO 8601 "YYYY-MM-DD"
    subcategory: str | None = None,
) -> dict:
    """Add a new expense. `category` must be one of the values returned by the
    `expenses://categories/builtin` resource. `subcategory`, if given, must belong
    to that category."""
```

Validation logic (shared helper `validate_category(conn, category, subcategory)`):
1. Look up `category` in `categories` (case-insensitive exact match). If missing →
   raise `ToolError("Unknown category '{category}'. Call the categories/builtin
   resource for the valid list.")`
2. If `subcategory` given, look up under that `category_id`. If missing → same
   pattern of error, naming the valid subcategories for that category.

Other tools, same shape:

- `update_expense(expense_id, amount=None, category=None, subcategory=None, description=None, expense_date=None)` — partial update; re-validates category/subcategory if provided; 404-style `ToolError` if `expense_id` doesn't belong to the caller's `user_id`.
- `delete_expense(expense_id)` — same ownership check.
- `set_budget(monthly_limit, category=None)` — `category=None` → upsert the row with `category_id IS NULL` (overall budget). `category` given → validate against builtin list, upsert `(user_id, category_id)`. No subcategory param — budgets don't go that deep, per the plan.

All mutating tools scope every query with `WHERE user_id = ?` using the id pulled
from `get_access_token()`.

---

## 5. Resources (`resources/categories.py`, `resources/reports.py`)

```python
@mcp.resource("expenses://categories/builtin")
async def builtin_categories() -> dict:
    """Fixed category → subcategory tree. Clients should read this before calling
    add_expense/set_budget to pick valid values — do not invent new categories."""
    # returns {"Transport": ["Fuel", "Public Transit", ...], ...}
```

Dynamic, per-user resources use FastMCP's URI template syntax (`{var}`):

```python
@mcp.resource("expenses://{user_id}/recent")
async def recent_expenses(user_id: str) -> list[dict]:
    """Last 20 expenses for the authenticated user."""
    # IMPORTANT: still cross-check user_id against get_access_token().claims["sub"];
    # never trust the URI param alone — reject if they don't match.

@mcp.resource("expenses://{user_id}/by-month/{year}/{month}")
async def expenses_by_month(user_id: str, year: str, month: str) -> dict:
    """Expenses for a given user/year/month, grouped by category, with a total."""

@mcp.resource("expenses://{user_id}/summary")
async def spending_summary(user_id: str) -> dict:
    """All-time (or current-month, see note) spending grouped by category, plus
    budget vs. actual if a budget is set."""
```

Note for the agent: confirm with the identity check pattern used elsewhere — the
`{user_id}` path param is for addressability/readability, but authorization must
always re-derive the real user from the verified token, not the URI string.

---

## 6. Prompts (`prompts/reports.py`)

```python
@mcp.prompt
def monthly_report(year: str, month: str) -> str:
    """Generate a prompt asking the model to summarize the user's spending for
    the given month, pulling from expenses://{user_id}/by-month/{year}/{month}."""

@mcp.prompt
def budget_check() -> str:
    """Generate a prompt asking the model to compare current spending against
    the user's budgets (overall and per-category) using expenses://{user_id}/summary,
    and flag anything over or close to its limit."""
```

---

## 7. `server.py` (entrypoint)

```python
from fastmcp import FastMCP
from auth import verifier
from db import init_db
import tools.expenses, tools.budgets
import resources.categories, resources.reports
import prompts.reports

init_db()  # creates schema + seeds categories if empty

mcp = FastMCP("Expense Tracker", auth=verifier)

# Register tools/resources/prompts (via decorators importing `mcp` from this
# module, or via explicit mcp.tool(fn) / mcp.resource(uri)(fn) calls — agent's
# choice, but keep it consistent across all modules)

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
```

Use **streamable HTTP transport** (not stdio) since this is multi-user with bearer
auth — stdio is single-process/single-client and doesn't fit this design.

---

## 8. Testing checklist (for the agent to self-verify after building)

1. `fastmcp dev server.py` or run directly, confirm server starts and seeds categories exactly once (restart it — verify no duplicate rows).
2. Mint two dev JWTs for two different `sub` values (two fake users).
3. As user A: add a few expenses across different categories/subcategories.
4. As user B: confirm `expenses://{user_id}/recent` for A's user_id is rejected or empty — B must never see A's data.
5. Try `add_expense` with a bogus category (e.g. `"Trvl"`) — confirm it's rejected with a clear error, not silently created.
6. Set an overall budget and a per-category budget for user A; call the summary resource; confirm both show up correctly.
7. Call `monthly_report` and `budget_check` prompts and confirm they reference real data.

---

## 9. Out of scope for v1 (explicitly deferred)

- Category/subcategory creation or editing via MCP tools (admin-only, direct DB edit)
- Subcategory-level budgets
- Multi-currency support
- Recurring/scheduled expenses
- OAuth/enterprise identity (SEP-990) — plain JWT is sufficient here
