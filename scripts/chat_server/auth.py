import base64
from fastapi import Request, HTTPException
from . import config


def check_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'},
        )
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        user, passwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401)
    if user != config.AUTH_USER or passwd != config.AUTH_PASS:
        raise HTTPException(status_code=401)
    return True


def board_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.BOARD_TOKEN:
        headers["Authorization"] = f"Bearer {config.BOARD_TOKEN}"
    return headers
