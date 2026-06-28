"""Aggregate admin routers under a single APIRouter."""
from fastapi import APIRouter

from src.apps.admin.api.v1 import audit, auth, config, content, dashboard, feedback, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(users.me_router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
api_router.include_router(audit.login_log_router)
api_router.include_router(feedback.router)
api_router.include_router(config.router)
api_router.include_router(config.sensitive_word_router)
api_router.include_router(config.security_router)
api_router.include_router(config.announcement_router)
api_router.include_router(content.router)

__all__ = ["api_router"]
