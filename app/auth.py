import hmac
import logging
import os
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


def require_token(authorization: str = Header(default="")) -> None:
    expected = os.environ.get("CALC_SERVICE_TOKEN", "")
    if not expected:
        logger.warning(
            "CALC_SERVICE_TOKEN is not set — all endpoints are unprotected. "
            "Set CALC_SERVICE_TOKEN to enable authentication."
        )
        return
    if not hmac.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
