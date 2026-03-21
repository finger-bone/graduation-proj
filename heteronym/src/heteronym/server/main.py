from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .logger import logger
from .router import (
    torch_model_router,
    scanner_router,
    offload_config_router,
    strategy_generator_router,
    deploy_router,
)


logger.info("Initializing FastAPI application")
main_handler = FastAPI()

# 健康检查端点
@main_handler.get("/ping")
async def ping():
    logger.debug("Ping endpoint accessed")
    return "pong"

@main_handler.get("/connect")
async def connect():
    # this is authenticated
    logger.debug("Connect endpoint accessed")
    return "connected"

from .auth import ServerAuthMiddleware, inject_auth_header_openapi

main_handler.add_middleware(ServerAuthMiddleware)
inject_auth_header_openapi(main_handler)

# 添加CORS中间件
main_handler.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册现有路由器
logger.info("Registering routers")
main_handler.include_router(torch_model_router, prefix="/torch-model")
main_handler.include_router(scanner_router, prefix="/scanner")
main_handler.include_router(offload_config_router, prefix="/offload-config")
main_handler.include_router(strategy_generator_router, prefix="/strategy-generator")
main_handler.include_router(deploy_router, prefix="/deploy")
logger.info("Application initialization completed")
