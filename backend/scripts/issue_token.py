#!/usr/bin/env python3
"""
Issues a signed API token for a client, using API_AUTH_SECRET from the
environment.

Deliberately a CLI script, not an API endpoint: an unauthenticated
"give me a token" HTTP route would be a real vulnerability (anyone could
mint themselves valid tokens); requiring shell access to the server to run
this is the actual security boundary. Only relevant once you've set
REQUIRE_API_AUTH=true (see backend/.env.example) -- with the default
REQUIRE_API_AUTH=false, no token is needed at all.

Usage:
    cd backend
    API_AUTH_SECRET=your-secret python3 scripts/issue_token.py --subject my-client --ttl-hours 24
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.auth import issue_token  # noqa: E402
from app.core.rbac import RBACError, ROLES, scopes_for_role  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a signed AI ResearchOS API token")
    parser.add_argument("--subject", required=True, help="Identifier for who/what this token is for")
    parser.add_argument("--ttl-hours", type=float, default=24.0)
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help="Grants the role's full scope set (see app/core/rbac.py). Mutually exclusive with --scope.",
    )
    parser.add_argument(
        "--scope", action="append", default=[], help="Repeatable, e.g. --scope papers:ingest. Ignored if --role is set."
    )
    args = parser.parse_args()

    secret = os.environ.get("API_AUTH_SECRET")
    if not secret:
        print("ERROR: API_AUTH_SECRET is not set in the environment.", file=sys.stderr)
        sys.exit(1)

    if args.role:
        try:
            scopes = scopes_for_role(args.role)
        except RBACError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        scopes = args.scope

    token = issue_token(secret, subject=args.subject, ttl_seconds=int(args.ttl_hours * 3600), scopes=scopes)
    print(token)


if __name__ == "__main__":
    main()
