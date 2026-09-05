# Expense Tracker MCP Server

A expense tracking server built with FastMCP, exposing tools and resources for logging expenses, managing budgets, and running basic analytics — designed to be used by LLM clients over MCP.

## Features

- **Expense CRUD** — add, update, and delete expenses
- **Fixed category system** — expenses are tagged from a built-in, seeded category/subcategory tree (not free-text) to keep data consistent across LLM calls
- **Budgets** — set an overall monthly budget, or a budget per top-level category
- **Analytics** — spending by month, category breakdown (reporting layer)

## Tech Stack

- **FastMCP** (latest) for the MCP server
- **SQLite** for storage
- **JWTVerifier** for auth/identity (multi-user, basic auth)
- **Streamable HTTP** transport

## Categories

Categories and subcategories are seeded into SQLite on first run and are fixed afterward — editable only directly via the database, not through MCP tools. This keeps category names consistent (e.g. always "Transport", never a drifting mix of "Transport"/"Travel").

## Available Tools

| Tool | Description |
|---|---|
| `add_expense` | Add a new expense (category must match a built-in value) |
| `update_expense` | Partially update an existing expense |
| `delete_expense` | Delete an expense |
| `set_budget` | Set an overall or per-category monthly budget |

## Resources

- `expenses://categories/builtin` — returns the built-in category/subcategory tree
