"""Aggregate all user-facing routers under a single APIRouter."""
from fastapi import APIRouter

from src.apps.user.api.v1 import auth, feedback, notifications, sync, tags, tasks, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tasks.router)
api_router.include_router(tasks.checklist_router)
api_router.include_router(tags.router)
api_router.include_router(notifications.router)
api_router.include_router(feedback.router)
api_router.include_router(sync.router)

__all__ = ["api_router"]