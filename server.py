from fastmcp import FastMCP

from auth import verifier
from db import init_db

import tools.expenses
import tools.budgets
import resources.categories
import resources.reports
import prompts.reports

# Create the DB file, run schema creation, and seed the builtin category tree
# if it hasn't been seeded yet (no-op on subsequent runs).
init_db()

mcp = FastMCP("Expense Tracker", auth=verifier)

# Each module exposes its own register(mcp) that wires its functions to the
# server via mcp.tool(...) / mcp.resource(uri)(...) / mcp.prompt(...).
tools.expenses.register(mcp)
tools.budgets.register(mcp)
resources.categories.register(mcp)
resources.reports.register(mcp)
prompts.reports.register(mcp)

if __name__ == "__main__":
    # Streamable HTTP, not stdio — this server is multi-user with bearer-token
    # auth, which stdio (single-process/single-client) doesn't support.
    mcp.run(transport="http", host="127.0.0.1", port=8000)