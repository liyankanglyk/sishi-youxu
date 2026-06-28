"""集中式日志配置。

骨架：支持文本或 JSON 格式，通过 settings.LOG_FORMAT / LOG_LEVEL 配置。
"""
import logging
import sys

from src.core.config import settings


def setup_logging() -> None:
    """配置根日志记录器，在应用启动时调用一次。"""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.LOG_FORMAT == "json":
        # 预留给生产环境；骨架阶段保持简洁。
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 抑制嘈杂的第三方库日志
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.DB_ECHO else logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """返回一个模块级 logger。"""
    return logging.getLogger(name)