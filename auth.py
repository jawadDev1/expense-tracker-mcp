import os

from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token

# FastMCP 3.x JWTVerifier has no `secret_key` arg. For HS256 the shared secret
# is passed as `public_key` (used as the HMAC key, not a PEM public key).
verifier = JWTVerifier(
    public_key=os.environ["EXPENSE_MCP_JWT_SECRET"],
    algorithm="HS256",
    required_scopes=["user"],
)


def get_user_id() -> str:
    """Return the authenticated user's id from the JWT `sub` claim."""
    token = get_access_token()
    if token is None:
        raise ToolError(
            "No access token present. Authenticate with a Bearer JWT."
        )
    user_id = token.claims.get("sub")
    if not user_id:
        raise ToolError("Access token is missing the required 'sub' claim.")
    return str(user_id)
