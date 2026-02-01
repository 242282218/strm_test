"""
FastAPI主应用

参考: MediaHelp main.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import quark, strm, proxy, emby, tasks, strm_validator, quark_sdk, search, rename
from app.config.settings import AppConfig
from app.core.logging import setup_logging, get_logger
import os

logger = get_logger(__name__)

config: AppConfig = None


def init_app():
    """初始化应用"""
    global config

    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    try:
        config = AppConfig.from_yaml(config_path)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using default config")
        config = AppConfig()

    setup_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        colored=config.colored_log
    )

    logger.info(f"Application initialized with config: {config_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_app()
    logger.info("Application started")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="夸克STRM系统",
    description="Emby/Jellyfin可播放的夸克网盘STRM系统",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quark.router)
app.include_router(strm.router)
app.include_router(proxy.router)
app.include_router(emby.router)
app.include_router(tasks.router)
app.include_router(strm_validator.router)
app.include_router(quark_sdk.router)
app.include_router(search.router)
app.include_router(rename.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "夸克STRM系统",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/config")
async def get_config():
    """获取配置（敏感信息脱敏）"""
    if config is None:
        return {"error": "Config not loaded"}

    return {
        "database": config.database,
        "log_level": config.log_level,
        "timeout": config.timeout,
        "exts": config.exts,
        "alt_exts": config.alt_exts,
        "endpoints_count": len(config.endpoints)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
