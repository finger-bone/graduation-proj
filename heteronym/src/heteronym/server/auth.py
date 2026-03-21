import os
import hashlib
import hmac
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware

from .logger import logger

# -------------------------------
# 1️⃣ 获取服务端密码
# -------------------------------
def get_server_password() -> str:
    password: str | None = os.environ.get("SERVER_PASSWORD")
    if password is None:
        raise RuntimeError("Set a password by setting environ SERVER_PASSWORD")
    return password

server_password: str = get_server_password()

# -------------------------------
# 2️⃣ SHA-256 哈希函数
# -------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_server_password(password_hashed: str) -> bool:
    expected_hash = hash_password(server_password)
    return hmac.compare_digest(password_hashed, expected_hash)

# -------------------------------
# 3️⃣ HMAC-SHA256 验证函数
# -------------------------------

time_window = os.environ.get("TIME_WINDOW_S", "60")
def verify_hmac(password_hashed: str, timestamp: str, signature: str, method: str, path: str, body: str) -> bool:
    message = f"{timestamp}{method}{path}{body}"
    expected = hmac.new(password_hashed.encode(), message.encode(), hashlib.sha256).hexdigest()

    # 时间窗口 60 秒防重放
    try:
        if abs(time.time() - int(timestamp) / 1000) > int(time_window):
            return False
    except ValueError:
        return False

    return hmac.compare_digest(signature, expected)

# -------------------------------
# 4️⃣ FastAPI 中间件
# -------------------------------
class ServerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 允许公开接口无需认证
        if request.url.path in {"/docs", "/redoc", "/openapi.json", "/ping"}:
            return await call_next(request)

        password_hashed: str | None = request.headers.get("x-server-pwd")
        if password_hashed is None:
            return JSONResponse(status_code=401, content={"detail": "Missing x-server-pwd"})

        if not verify_server_password(password_hashed):
            return JSONResponse(status_code=401, content={"detail": "Invalid x-server-pwd"})

        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        if timestamp and signature:
            body_bytes = await request.body()
            body_str = body_bytes.decode() if body_bytes else ""
            if not verify_hmac(password_hashed, timestamp, signature, request.method, request.url.path, body_str):
                return JSONResponse(status_code=401, content={"detail": "Invalid signature"})

        return await call_next(request)

# -------------------------------
# 5️⃣ OpenAPI 文档注入认证头
# -------------------------------
def inject_auth_header_openapi(app: FastAPI) -> None:
    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema: Dict[str, Any] = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        header_param: Dict[str, Any] = {
            "name": "X-Server-Pwd",
            "in": "header",
            "required": True,
            "description": "Server authentication password (SHA-256 hashed)",
            "schema": {"type": "string"},
        }

        for path_item in openapi_schema["paths"].values():
            for operation in path_item.values():
                parameters = operation.get("parameters", [])
                parameters.append(header_param)
                operation["parameters"] = parameters

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
