import os
from fastapi import Header, HTTPException, status


def require_token(authorization: str = Header(default="")) -> None:
    expected = os.environ.get("CALC_SERVICE_TOKEN", "")
    if not expected:
        return  # token check disabled if env var not set
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
