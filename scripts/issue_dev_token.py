#!/usr/bin/env python3
"""Mint a local HS256 JWT for manual testing. Not for production use."""

import argparse
import os
import time

import jwt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue a development JWT for the Expense Tracker MCP server."
    )
    parser.add_argument(
        "--sub",
        required=True,
        help="User id placed in the JWT sub claim",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=1,
        help="Token lifetime in seconds (default: 1 = 1 second)",
    )
    args = parser.parse_args()

    secret = os.environ.get("EXPENSE_MCP_JWT_SECRET")
    if not secret:
        raise SystemExit(
            "EXPENSE_MCP_JWT_SECRET is not set. Export a shared HMAC secret first."
        )

    now = int(time.time())
    ttl_seconds = args.ttl * 24 * 60 * 60

    token = jwt.encode(
        {
            "sub": args.sub,
            "scope": "user",
            "iat": now,
            "exp": now + ttl_seconds,
        },
        secret,
        algorithm="HS256",
    )
    print(token)


if __name__ == "__main__":
    main()

