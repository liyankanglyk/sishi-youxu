"""管理后台 service —— Phase 1 实现。

涵盖：管理员认证、用户 CRUD、仪表盘、审计日志、反馈、系统配置。
"""

from __future__ import annotations

import csv
import io
from datetime import date as date_type, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from src.core.logger import get_logger
from src.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    sha256_hex,
    verify_password,
)
from src.models.admin import (
    AdminPermission,
    Announcement,
    AnnouncementType,
    AuditLog,
    Feedback,
    FeedbackStatus,
    IpBlacklist,
    LoginLog,
    LoginStatus,
    Notification,
    NotificationKind,
    SensitiveWord,
    SystemConfig,
)
from src.models.auth import AuthIdentity, AuthProvider, RefreshToken
from src.models.task import Tag, Task, TaskChecklist, TaskTag
from src.models.user import User, UserRole, UserStatus

logger = get_logger(__name__)


class AdminService:
    """聚合所有管理后台侧的业务逻辑。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # 由路由层在调用审计方法之前设置
        self._request_ip: str | None = None
        self._request_ua: str | None = None

    # =========================================================================
    # 认证
    # =========================================================================

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """管理员登录：使用密码登录方式，角色必须是 admin 或 super_admin。"""
        username = (username or "").strip()
        if not username or not password:
            raise ValidationException(
                "用户名和密码不能为空", code="VALIDATION_ERROR"
            )

        stmt = select(AuthIdentity).where(
            AuthIdentity.provider == AuthProvider.password,
            AuthIdentity.provider_uid == username,
            AuthIdentity.deleted_at.is_(None),
        )
        identity = (await self.db.execute(stmt)).scalar_one_or_none()
        if identity is None or not verify_password(password, identity.credentials or ""):
            await self._record_login_log(
                user_uuid=None,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason="用户名或密码错误",
            )
            raise UnauthorizedException(
                "用户名或密码错误", code="AUTH_INVALID_CREDENTIALS"
            )

        user = await self._get_user(identity.user_uuid)
        if user is None:
            await self._record_login_log(
                user_uuid=identity.user_uuid,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason="用户不存在",
            )
            raise UnauthorizedException("用户不存在", code="USER_NOT_FOUND")

        if user.role not in {UserRole.admin, UserRole.super_admin}:
            await self._record_login_log(
                user_uuid=user.uuid,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason="无管理员权限",
            )
            raise UnauthorizedException("无管理员权限", code="ADMIN_FORBIDDEN")

        try:
            await self._ensure_active(user)
        except UnauthorizedException as e:
            await self._record_login_log(
                user_uuid=user.uuid,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason=e.message,
            )
            raise

        tokens = await self._issue_token_pair(user)
        user_out = self._user_to_out(user)
        # 查询该用户角色对应的权限
        perm_stmt = select(AdminPermission.permission).where(
            AdminPermission.role == user.role
        )
        perms = [
            r
            for r in (await self.db.execute(perm_stmt)).scalars().all()
            if r
        ]
        user_out["permissions"] = perms

        await self._record_login_log(
            user_uuid=user.uuid,
            provider="password",
            login_status=LoginStatus.success,
        )
        return {
            **tokens,
            "user": user_out,
        }

    async def refresh(self, refresh_token_str: str) -> dict[str, Any]:
        """轮换管理员 refresh token。"""
        record = await self._resolve_refresh_token(refresh_token_str)
        user = await self._get_user(record.user_uuid)
        if user is None:
            raise UnauthorizedException("用户不存在", code="USER_NOT_FOUND")
        if user.role not in {UserRole.admin, UserRole.super_admin}:
            raise UnauthorizedException("无管理员权限", code="ADMIN_FORBIDDEN")
        await self._ensure_active(user)

        record.revoked_at = datetime.utcnow()
        await self.db.flush()
        return await self._issue_token_pair(user)

    async def logout(self, refresh_token_str: str) -> dict[str, Any]:
        """幂等的登出操作。"""
        try:
            record = await self._resolve_refresh_token(refresh_token_str)
            record.revoked_at = datetime.utcnow()
            await self.db.flush()
            return {"revokedCount": 1}
        except UnauthorizedException:
            return {"revokedCount": 0}

    # =========================================================================
    # 用户管理
    # =========================================================================

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        status: str | None = None,
        role: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """带筛选条件的用户分页列表。"""
        stmt = select(User).where(User.deleted_at.is_(None))

        if keyword:
            stmt = stmt.where(User.nickname.ilike(f"%{keyword}%"))
        if status:
            stmt = stmt.where(User.status == status)
        if role:
            stmt = stmt.where(User.role == role)
        if start_time:
            stmt = stmt.where(User.created_at >= start_time)
        if end_time:
            stmt = stmt.where(User.created_at <= end_time)

        # 统计总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页
        stmt = stmt.order_by(User.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [self._user_to_out(u) for u in rows]
        return {
            "items": items,
            "meta": {
                "total": total,
                "page": page,
                "pageSize": page_size,
                "hasMore": (page * page_size) < total,
            },
        }

    async def get_user(self, uuid: str) -> dict[str, Any]:
        """用户详情，含任务统计与认证身份。"""
        user = await self._get_user(uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        # 任务计数
        task_total_stmt = select(func.count(Task.uuid)).where(
            Task.user_uuid == uuid, Task.deleted_at.is_(None)
        )
        task_total = (await self.db.execute(task_total_stmt)).scalar() or 0

        completed_stmt = select(func.count(Task.uuid)).where(
            Task.user_uuid == uuid, Task.completed.is_(True), Task.deleted_at.is_(None)
        )
        task_completed = (await self.db.execute(completed_stmt)).scalar() or 0

        # 认证身份
        identity_stmt = select(AuthIdentity).where(
            AuthIdentity.user_uuid == uuid,
            AuthIdentity.deleted_at.is_(None),
        )
        identities = (await self.db.execute(identity_stmt)).scalars().all()
        auth_identities = [
            {"provider": i.provider.value if hasattr(i.provider, "value") else str(i.provider),
             "identifier": i.provider_uid}
            for i in identities
        ]

        return {
            **self._user_to_out(user),
            "authIdentities": auth_identities,
            "taskCount": task_total,
            "completedTaskCount": task_completed,
        }

    async def update_user(self, uuid: str, data: dict, admin_uuid: str = "") -> dict[str, Any]:
        user = await self._get_user(uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        if "nickname" in data:
            user.nickname = data["nickname"]
        if "status" in data:
            new_status = data["status"]
            if new_status not in {s.value for s in UserStatus}:
                raise ValidationException(f"无效的状态值: {new_status}", code="VALIDATION_ERROR")
            user.status = new_status

        await self.db.flush()
        await self._record_audit(admin_uuid, "user.update", "user", uuid, detail=data)
        return {"uuid": user.uuid, "nickname": user.nickname, "status": user.status.value if hasattr(user.status, "value") else str(user.status)}

    async def delete_user(self, uuid: str, admin_uuid: str = "") -> None:
        user = await self._get_user(uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")
        user.deleted_at = datetime.utcnow()
        await self.db.flush()
        await self._record_audit(admin_uuid, "user.delete", "user", uuid)

    async def disable_user(self, uuid: str, admin_uuid: str = "") -> dict[str, Any]:
        return await self.update_user(uuid, {"status": "disabled"}, admin_uuid)

    async def enable_user(self, uuid: str, admin_uuid: str = "") -> dict[str, Any]:
        return await self.update_user(uuid, {"status": "active"}, admin_uuid)

    async def force_logout(self, uuid: str, admin_uuid: str = "") -> dict[str, Any]:
        user = await self._get_user(uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        revoked = await self._revoke_all_refresh_tokens(uuid)

        # 在 Redis 中设置 force-logout 时间戳，使该用户的 access token 立即失效
        # TTL = access token 有效期，过期后自动清理
        try:
            from src.core.config import settings
            from src.core.redis import build_key, get_redis

            r = get_redis()
            key = build_key("force_logout", uuid)
            ts = datetime.utcnow().timestamp()
            ttl = max(int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60), 300)
            await r.set(key, str(ts), ex=ttl)
            logger.info(
                "Force logout: user=%s revoked=%d redis_ttl=%d",
                uuid, revoked, ttl,
            )
        except Exception:
            # Redis 不可用时仍可吊销 refresh token
            pass

        await self._record_audit(admin_uuid, "user.force_logout", "user", uuid)
        return {"revokedCount": revoked}

    async def change_password(
        self, admin_uuid: str, old_password: str, new_password: str
    ) -> dict[str, Any]:
        """管理员修改自己的密码。验证旧密码后设置新密码，撤销所有 refresh token。"""
        if not old_password or not new_password:
            raise ValidationException(
                "oldPassword 与 newPassword 必填",
                code="VALIDATION_ERROR",
            )
        if len(new_password) < 8:
            raise ValidationException(
                "密码至少 8 位",
                code="VALIDATION_ERROR",
            )

        identity = await self._find_password_identity(admin_uuid)
        if not verify_password(old_password, identity.credentials or ""):
            raise ValidationException(
                "当前密码错误",
                code="AUTH_INVALID_CREDENTIALS",
            )

        identity.credentials = hash_password(new_password)
        await self.db.flush()

        revoked = await self._revoke_all_refresh_tokens(admin_uuid)
        logger.info("admin password changed: admin=%s revoked=%d", admin_uuid, revoked)

        await self._record_audit(admin_uuid, "admin.change_password", "user", admin_uuid)
        return {"message": "密码修改成功"}

    async def reset_user_password(
        self, target_uuid: str, new_password: str, admin_uuid: str = ""
    ) -> dict[str, Any]:
        """管理员重置用户密码（无需用户旧密码）。"""
        user = await self._get_user(target_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        if not new_password or len(new_password) < 8:
            raise ValidationException(
                "密码至少 8 位",
                code="VALIDATION_ERROR",
            )

        identity = await self._find_password_identity(target_uuid)
        if identity is None:
            raise ValidationException(
                "该用户未设置密码登录方式",
                code="AUTH_PROVIDER_NOT_LINKED",
            )

        identity.credentials = hash_password(new_password)
        await self.db.flush()

        revoked = await self._revoke_all_refresh_tokens(target_uuid)
        logger.info(
            "admin reset password: admin=%s target=%s revoked=%d",
            admin_uuid, target_uuid, revoked,
        )

        await self._record_audit(admin_uuid, "user.reset_password", "user", target_uuid)
        return {"message": "密码已重置"}

    async def _find_password_identity(self, user_uuid: str) -> AuthIdentity | None:
        """查找用户的 password provider 认证身份。"""
        stmt = select(AuthIdentity).where(
            AuthIdentity.user_uuid == user_uuid,
            AuthIdentity.provider == AuthProvider.password,
            AuthIdentity.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def batch_users(self, action: str, uuids: list[str], admin_uuid: str = "") -> dict[str, Any]:
        if action not in {"disable", "enable"}:
            raise ValidationException(f"不支持的批量操作: {action}", code="VALIDATION_ERROR")

        affected = []
        for uid in uuids:
            try:
                if action == "disable":
                    await self.disable_user(uid, admin_uuid)
                else:
                    await self.enable_user(uid, admin_uuid)
                affected.append(uid)
            except Exception:
                pass  # 批量操作中跳过未找到的用户

        await self._record_audit(admin_uuid, f"user.batch_{action}", "user", "", detail={"uuids": uuids, "affected": affected})
        return {"affected": len(affected), "uuids": affected}

    async def export_users(self) -> str:
        """导出所有用户为 CSV 字符串。"""
        stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["uuid", "nickname", "role", "status", "locale", "created_at", "updated_at"])
        for u in rows:
            writer.writerow([
                u.uuid, u.nickname,
                u.role.value if hasattr(u.role, "value") else str(u.role),
                u.status.value if hasattr(u.status, "value") else str(u.status),
                u.locale,
                u.created_at.isoformat() if u.created_at else "",
                u.updated_at.isoformat() if u.updated_at else "",
            ])
        return output.getvalue()

    # =========================================================================
    # 仪表盘
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """聚合仪表盘统计数据。"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_users = (await self.db.execute(
            select(func.count(User.uuid)).where(User.deleted_at.is_(None))
        )).scalar() or 0

        active_today = (await self.db.execute(
            select(func.count(func.distinct(LoginLog.user_uuid))).where(
                LoginLog.created_at >= today_start,
                LoginLog.login_status == "success",
            )
        )).scalar() or 0

        total_tasks = (await self.db.execute(
            select(func.count(Task.uuid)).where(Task.deleted_at.is_(None))
        )).scalar() or 0

        completed_today = (await self.db.execute(
            select(func.count(Task.uuid)).where(
                Task.completed_at >= today_start,
                Task.deleted_at.is_(None),
            )
        )).scalar() or 0

        # 四象限分布（以 0 为分界划分 urgency_level / importance_level）
        q1 = (await self.db.execute(
            select(func.count(Task.uuid)).where(
                Task.urgency_level > 0, Task.importance_level > 0, Task.deleted_at.is_(None)
            )
        )).scalar() or 0
        q2 = (await self.db.execute(
            select(func.count(Task.uuid)).where(
                Task.urgency_level <= 0, Task.importance_level > 0, Task.deleted_at.is_(None)
            )
        )).scalar() or 0
        q3 = (await self.db.execute(
            select(func.count(Task.uuid)).where(
                Task.urgency_level > 0, Task.importance_level <= 0, Task.deleted_at.is_(None)
            )
        )).scalar() or 0
        q4 = (await self.db.execute(
            select(func.count(Task.uuid)).where(
                Task.urgency_level <= 0, Task.importance_level <= 0, Task.deleted_at.is_(None)
            )
        )).scalar() or 0

        return {
            "total_users": total_users,
            "active_users_today": active_today,
            "total_tasks": total_tasks,
            "completed_tasks_today": completed_today,
            "quadrant_distribution": {"q1": q1, "q2": q2, "q3": q3, "q4": q4},
        }

    async def get_chart(self, metric: str) -> dict[str, Any]:
        """指定指标最近 7 天的时序数据。"""
        now = datetime.utcnow()
        days = []
        for i in range(6, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            days.append((day_start, day_end))

        data = []
        for ds, de in days:
            if metric == "new_users":
                count = (await self.db.execute(
                    select(func.count(User.uuid)).where(
                        User.created_at >= ds, User.created_at < de, User.deleted_at.is_(None)
                    )
                )).scalar() or 0
            elif metric == "tasks_created":
                count = (await self.db.execute(
                    select(func.count(Task.uuid)).where(
                        Task.created_at >= ds, Task.created_at < de, Task.deleted_at.is_(None)
                    )
                )).scalar() or 0
            elif metric == "tasks_completed":
                count = (await self.db.execute(
                    select(func.count(Task.uuid)).where(
                        Task.completed_at >= ds, Task.completed_at < de, Task.deleted_at.is_(None)
                    )
                )).scalar() or 0
            else:
                count = 0
            data.append({"date": ds.strftime("%Y-%m-%d"), "count": count})

        return {"metric": metric, "data": data}

    # =========================================================================
    # 审计日志
    # =========================================================================

    # -----------------------------------------------------------------
    # 审计 action 的中文标签
    # -----------------------------------------------------------------
    _ACTION_LABELS: dict[str, str] = {
        "user.update": "更新用户",
        "user.delete": "删除用户",
        "user.force_logout": "强制登出",
        "user.batch_disable": "批量禁用用户",
        "user.batch_enable": "批量启用用户",
        "task.delete": "删除任务",
        "task.create": "创建任务",
        "task.update": "更新任务",
        "task.batch_delete": "批量删除任务",
        "task.batch_restore": "批量恢复任务",
        "tag.update": "更新标签",
        "tag.delete": "删除标签",
        "feedback.update": "更新反馈状态",
        "config.update": "更新系统配置",
        "announcement.create": "创建公告",
        "announcement.update": "更新公告",
        "announcement.delete": "删除公告",
    }

    async def list_audit(
        self,
        page: int = 1,
        page_size: int = 20,
        user_uuid: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(AuditLog)
        if user_uuid:
            stmt = stmt.where(AuditLog.user_uuid == user_uuid)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if start_time:
            stmt = stmt.where(AuditLog.created_at >= start_time)
        if end_time:
            stmt = stmt.where(AuditLog.created_at <= end_time)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        # 批量解析操作者 UUID 对应的昵称
        user_uuids = {r.user_uuid for r in rows if r.user_uuid}
        nicknames: dict[str, str] = {}
        if user_uuids:
            user_rows = (await self.db.execute(
                select(User.uuid, User.nickname).where(User.uuid.in_(user_uuids))
            )).all()
            nicknames = {u.uuid: u.nickname for u in user_rows}

        items = [{
            "uuid": r.uuid,
            "userUuid": r.user_uuid,
            "userNickname": nicknames.get(r.user_uuid) if r.user_uuid else None,
            "action": r.action,
            "actionLabel": self._ACTION_LABELS.get(r.action, r.action),
            "resourceType": r.resource_type,
            "resourceUuid": r.resource_uuid,
            "ipAddress": r.ip_address,
            "detail": r.detail,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def get_audit_entry(self, uuid: str) -> dict[str, Any]:
        stmt = select(AuditLog).where(AuditLog.uuid == uuid)
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundException("审计日志不存在", code="NOT_FOUND")

        # 解析操作者昵称
        nickname: str | None = None
        if row.user_uuid:
            user_row = (await self.db.execute(
                select(User.nickname).where(User.uuid == row.user_uuid)
            )).scalar_one_or_none()
            nickname = user_row

        return {
            "uuid": row.uuid,
            "userUuid": row.user_uuid,
            "userNickname": nickname,
            "action": row.action,
            "actionLabel": self._ACTION_LABELS.get(row.action, row.action),
            "resourceType": row.resource_type,
            "resourceUuid": row.resource_uuid,
            "ipAddress": row.ip_address,
            "userAgent": row.user_agent,
            "detail": row.detail,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    async def _record_audit(
        self,
        admin_uuid: str,
        action: str,
        resource_type: str,
        resource_uuid: str = "",
        detail: dict | None = None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        log = AuditLog(
            user_uuid=admin_uuid or None,
            action=action,
            resource_type=resource_type,
            resource_uuid=resource_uuid or None,
            detail=detail,
            ip_address=ip_address or getattr(self, "_request_ip", None) or None,
            user_agent=user_agent or getattr(self, "_request_ua", None) or None,
        )
        self.db.add(log)

    async def _record_login_log(
        self,
        *,
        user_uuid: str | None,
        provider: str,
        login_status: LoginStatus,
        fail_reason: str | None = None,
    ) -> None:
        """记录一次登录尝试（成功或失败），从请求中捕获 IP / UA。

        使用同步连接以确保日志写入，即使父级异步事务因认证错误而回滚。
        """
        from uuid import uuid4

        from sqlalchemy import create_engine
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        from src.core.config import settings

        ip = getattr(self, "_request_ip", None) or None
        ua = getattr(self, "_request_ua", None) or None

        sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
        engine = create_engine(sync_url, pool_pre_ping=True)

        with engine.begin() as conn:
            stmt = mysql_insert(LoginLog).values(
                uuid=str(uuid4()),
                user_uuid=user_uuid,
                provider=provider,
                ip_address=ip,
                user_agent=ua,
                login_status=login_status,
                fail_reason=fail_reason,
                created_at=datetime.utcnow(),
            )
            conn.execute(stmt)

        engine.dispose()

    # =========================================================================
    # 反馈
    # =========================================================================

    async def list_feedback(
        self, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> dict[str, Any]:
        stmt = select(Feedback).where(Feedback.deleted_at.is_(None))
        if status:
            stmt = stmt.where(Feedback.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Feedback.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [{
            "uuid": r.uuid,
            "userUuid": r.user_uuid,
            "content": r.content,
            "contact": r.contact,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def update_feedback(self, uuid: str, status: str, admin_uuid: str = "") -> dict[str, Any]:
        stmt = select(Feedback).where(Feedback.uuid == uuid, Feedback.deleted_at.is_(None))
        fb = (await self.db.execute(stmt)).scalar_one_or_none()
        if fb is None:
            raise NotFoundException("反馈不存在", code="FEEDBACK_NOT_FOUND")

        if status not in {s.value for s in FeedbackStatus}:
            raise ValidationException(f"无效的状态: {status}", code="VALIDATION_ERROR")

        fb.status = status
        fb.handled_by = admin_uuid
        fb.handled_at = datetime.utcnow()
        await self.db.flush()
        await self._record_audit(admin_uuid, "feedback.update", "feedback", uuid, detail={"status": status})
        return {
            "uuid": fb.uuid,
            "status": fb.status.value if hasattr(fb.status, "value") else str(fb.status),
            "handledBy": fb.handled_by,
            "handledAt": fb.handled_at.isoformat() if fb.handled_at else None,
        }

    # =========================================================================
    # 系统配置
    # =========================================================================

    async def get_config(self) -> dict[str, Any]:
        """将所有系统配置以扁平 dict 形式返回。"""
        stmt = select(SystemConfig)
        rows = (await self.db.execute(stmt)).scalars().all()
        return {r.key: r.value for r in rows}

    async def update_config(self, patch: dict[str, Any], admin_uuid: str = "") -> dict[str, Any]:
        """插入或更新系统配置键。"""
        updated = []
        for key, value in patch.items():
            stmt = select(SystemConfig).where(SystemConfig.key == key)
            row = (await self.db.execute(stmt)).scalar_one_or_none()
            if row is not None:
                row.value = str(value) if value is not None else None
            else:
                self.db.add(SystemConfig(key=key, value=str(value) if value is not None else None))
            updated.append(key)

        await self.db.flush()
        await self._record_audit(admin_uuid, "config.update", "system_config", "", detail={"keys": updated})
        return {"updated_keys": updated, "updatedAt": datetime.utcnow().isoformat()}

    # =========================================================================
    # 登录日志（Phase 4）
    # =========================================================================

    async def list_login_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        provider: str | None = None,
        user_uuid: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(LoginLog)
        if status:
            stmt = stmt.where(LoginLog.login_status == status)
        if provider:
            stmt = stmt.where(LoginLog.provider == provider)
        if user_uuid:
            stmt = stmt.where(LoginLog.user_uuid == user_uuid)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(LoginLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [{
            "uuid": r.uuid,
            "userUuid": r.user_uuid,
            "provider": r.provider,
            "ipAddress": r.ip_address,
            "userAgent": r.user_agent,
            "loginStatus": r.login_status.value if hasattr(r.login_status, "value") else str(r.login_status),
            "failReason": r.fail_reason,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    # =========================================================================
    # 敏感词（Phase 4）
    # =========================================================================

    async def list_sensitive_words(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        stmt = select(SensitiveWord).where(SensitiveWord.deleted_at.is_(None))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(SensitiveWord.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [{
            "uuid": r.uuid,
            "word": r.word,
            "level": r.level,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def add_sensitive_word(self, word: str, level: int = 1) -> dict[str, Any]:
        existing = await self.db.execute(
            select(SensitiveWord).where(SensitiveWord.word == word, SensitiveWord.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none() is not None:
            from src.core.exceptions import ConflictException
            raise ConflictException(f"敏感词「{word}」已存在", code="CONFLICT")

        sw = SensitiveWord(word=word, level=level)
        self.db.add(sw)
        await self.db.flush()
        return {
            "uuid": sw.uuid,
            "word": sw.word,
            "level": sw.level,
            "createdAt": sw.created_at.isoformat() if sw.created_at else None,
        }

    async def update_sensitive_word(
        self, uuid: str, word: str | None = None, level: int | None = None
    ) -> dict[str, Any]:
        stmt = select(SensitiveWord).where(
            SensitiveWord.uuid == uuid, SensitiveWord.deleted_at.is_(None)
        )
        sw = (await self.db.execute(stmt)).scalar_one_or_none()
        if sw is None:
            from src.core.exceptions import NotFoundException
            raise NotFoundException("敏感词不存在", code="NOT_FOUND")

        if word is not None:
            dup = await self.db.execute(
                select(SensitiveWord).where(
                    SensitiveWord.word == word,
                    SensitiveWord.uuid != uuid,
                    SensitiveWord.deleted_at.is_(None),
                )
            )
            if dup.scalar_one_or_none() is not None:
                from src.core.exceptions import ConflictException
                raise ConflictException(f"敏感词「{word}」已存在", code="CONFLICT")
            sw.word = word
        if level is not None:
            sw.level = level

        await self.db.flush()
        return {
            "uuid": sw.uuid,
            "word": sw.word,
            "level": sw.level,
            "updatedAt": sw.updated_at.isoformat() if sw.updated_at else None,
        }

    async def delete_sensitive_word(self, uuid: str) -> None:
        stmt = select(SensitiveWord).where(
            SensitiveWord.uuid == uuid, SensitiveWord.deleted_at.is_(None)
        )
        sw = (await self.db.execute(stmt)).scalar_one_or_none()
        if sw is None:
            from src.core.exceptions import NotFoundException
            raise NotFoundException("敏感词不存在", code="NOT_FOUND")
        sw.deleted_at = datetime.utcnow()
        await self.db.flush()

    async def import_sensitive_words(self, text: str) -> dict[str, Any]:
        imported = 0
        skipped = 0
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for word in lines:
            existing = await self.db.execute(
                select(SensitiveWord).where(SensitiveWord.word == word, SensitiveWord.deleted_at.is_(None))
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue
            sw = SensitiveWord(word=word, level=1)
            self.db.add(sw)
            imported += 1
        if imported > 0:
            await self.db.flush()
        return {"imported": imported, "skipped": skipped}

    # =========================================================================
    # IP 黑名单（Phase 4）
    # =========================================================================

    async def list_ip_blacklist(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        stmt = select(IpBlacklist)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(IpBlacklist.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [{
            "uuid": r.uuid,
            "ipAddress": r.ip_address,
            "reason": r.reason,
            "createdBy": r.created_by,
            "expiresAt": r.expires_at.isoformat() if r.expires_at else None,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def add_ip_blacklist(
        self,
        ip_address: str,
        reason: str | None = None,
        created_by: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        existing = await self.db.execute(
            select(IpBlacklist).where(IpBlacklist.ip_address == ip_address)
        )
        if existing.scalar_one_or_none() is not None:
            from src.core.exceptions import ConflictException
            raise ConflictException(f"IP {ip_address} 已在黑名单中", code="CONFLICT")

        entry = IpBlacklist(
            ip_address=ip_address,
            reason=reason,
            created_by=created_by,
            expires_at=expires_at,
        )
        self.db.add(entry)
        await self.db.flush()
        return {
            "uuid": entry.uuid,
            "ipAddress": entry.ip_address,
            "reason": entry.reason,
            "createdBy": entry.created_by,
            "expiresAt": entry.expires_at.isoformat() if entry.expires_at else None,
            "createdAt": entry.created_at.isoformat() if entry.created_at else None,
        }

    async def delete_ip_blacklist(self, uuid: str) -> None:
        stmt = select(IpBlacklist).where(IpBlacklist.uuid == uuid)
        entry = (await self.db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            from src.core.exceptions import NotFoundException
            raise NotFoundException("IP 黑名单条目不存在", code="NOT_FOUND")
        await self.db.delete(entry)
        await self.db.flush()

    # =========================================================================
    # 公告（Phase 4）
    # =========================================================================

    async def list_announcements(
        self,
        page: int = 1,
        page_size: int = 20,
        type_filter: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(Announcement).where(Announcement.deleted_at.is_(None))
        if type_filter:
            stmt = stmt.where(Announcement.type == type_filter)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [{
            "uuid": r.uuid,
            "title": r.title,
            "content": r.content,
            "type": r.type.value if hasattr(r.type, "value") else str(r.type),
            "isPinned": r.is_pinned,
            "isActive": r.is_active,
            "startTime": r.start_time.isoformat() if r.start_time else None,
            "endTime": r.end_time.isoformat() if r.end_time else None,
            "createdBy": r.created_by,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rows]

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def create_announcement(
        self,
        title: str,
        content: str,
        announcement_type: str = "info",
        is_pinned: bool = False,
        is_active: bool = True,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        ann = Announcement(
            title=title,
            content=content,
            type=announcement_type,
            is_pinned=is_pinned,
            is_active=is_active,
            start_time=start_time,
            end_time=end_time,
            created_by=created_by,
        )
        self.db.add(ann)
        await self.db.flush()

        # 扇出：为每个活跃用户创建一条通知
        user_uuids = (
            await self.db.execute(
                select(User.uuid).where(
                    User.deleted_at.is_(None),
                    User.status == UserStatus.active,
                )
            )
        ).scalars().all()

        for user_uuid in user_uuids:
            self.db.add(
                Notification(
                    user_uuid=user_uuid,
                    kind=NotificationKind.system_announcement,
                    title=title,
                    body=content,
                )
            )

        await self._record_audit(created_by or "", "announcement.create", "announcement", ann.uuid,
                                 detail={"title": title, "type": announcement_type,
                                         "notified_users": len(user_uuids)})
        return {
            "uuid": ann.uuid,
            "title": ann.title,
            "content": ann.content,
            "type": ann.type.value if hasattr(ann.type, "value") else str(ann.type),
            "isPinned": ann.is_pinned,
            "isActive": ann.is_active,
            "startTime": ann.start_time.isoformat() if ann.start_time else None,
            "endTime": ann.end_time.isoformat() if ann.end_time else None,
            "createdBy": ann.created_by,
            "createdAt": ann.created_at.isoformat() if ann.created_at else None,
        }

    async def update_announcement(
        self,
        uuid: str,
        title: str | None = None,
        content: str | None = None,
        announcement_type: str | None = None,
        is_pinned: bool | None = None,
        is_active: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        *,
        admin_uuid: str = "",
    ) -> dict[str, Any]:
        stmt = select(Announcement).where(
            Announcement.uuid == uuid, Announcement.deleted_at.is_(None)
        )
        ann = (await self.db.execute(stmt)).scalar_one_or_none()
        if ann is None:
            from src.core.exceptions import NotFoundException
            raise NotFoundException("公告不存在", code="NOT_FOUND")

        changed: list[str] = []
        if title is not None:
            ann.title = title
            changed.append("title")
        if content is not None:
            ann.content = content
            changed.append("content")
        if announcement_type is not None:
            ann.type = announcement_type
            changed.append("type")
        if is_pinned is not None:
            ann.is_pinned = is_pinned
            changed.append("isPinned")
        if is_active is not None:
            ann.is_active = is_active
            changed.append("isActive")
        if start_time is not None:
            ann.start_time = start_time
            changed.append("startTime")
        if end_time is not None:
            ann.end_time = end_time
            changed.append("endTime")

        await self.db.flush()
        await self._record_audit(admin_uuid, "announcement.update", "announcement", uuid,
                                 detail={"title": ann.title, "changed": changed})
        return {
            "uuid": ann.uuid,
            "title": ann.title,
            "type": ann.type.value if hasattr(ann.type, "value") else str(ann.type),
            "isPinned": ann.is_pinned,
            "isActive": ann.is_active,
            "updatedAt": ann.updated_at.isoformat() if ann.updated_at else None,
        }

    async def delete_announcement(self, uuid: str, *, admin_uuid: str = "") -> None:
        stmt = select(Announcement).where(
            Announcement.uuid == uuid, Announcement.deleted_at.is_(None)
        )
        ann = (await self.db.execute(stmt)).scalar_one_or_none()
        if ann is None:
            from src.core.exceptions import NotFoundException
            raise NotFoundException("公告不存在", code="NOT_FOUND")
        ann.deleted_at = datetime.utcnow()
        await self.db.flush()
        await self._record_audit(admin_uuid, "announcement.delete", "announcement", uuid)

    # =========================================================================
    # 内容管理（任务 & 标签）
    # =========================================================================

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        user_uuid: str | None = None,
        quadrant: int | None = None,
        completed: bool | None = None,
        tag_uuid: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """管理员可见的带筛选条件的任务列表。"""
        stmt = select(Task).where(Task.deleted_at.is_(None))

        if user_uuid:
            stmt = stmt.where(Task.user_uuid == user_uuid)
        if completed is not None:
            stmt = stmt.where(Task.completed == completed)
        if start_time:
            stmt = stmt.where(Task.created_at >= start_time)
        if end_time:
            stmt = stmt.where(Task.created_at <= end_time)
        if quadrant is not None:
            q_map = {
                1: (Task.urgency_level > 0, Task.importance_level > 0),
                2: (Task.urgency_level <= 0, Task.importance_level > 0),
                3: (Task.urgency_level > 0, Task.importance_level <= 0),
                4: (Task.urgency_level <= 0, Task.importance_level <= 0),
            }
            if quadrant in q_map:
                cx, cy = q_map[quadrant]
                stmt = stmt.where(cx, cy)

        if tag_uuid:
            stmt = stmt.join(TaskTag, and_(
                TaskTag.task_uuid == Task.uuid,
                TaskTag.tag_uuid == tag_uuid,
            )).distinct()

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Task.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        # 补充用户信息和标签
        user_ids = {t.user_uuid for t in rows}
        users_stmt = select(User).where(User.uuid.in_(user_ids))
        users_rows = (await self.db.execute(users_stmt)).scalars().all()
        users_map = {u.uuid: u for u in users_rows}

        items = []
        for task in rows:
            user = users_map.get(task.user_uuid)
            tags_stmt = select(Tag).join(
                TaskTag, and_(TaskTag.tag_uuid == Tag.uuid, TaskTag.task_uuid == task.uuid)
            ).where(Tag.deleted_at.is_(None))
            tags = (await self.db.execute(tags_stmt)).scalars().all()
            items.append({
                "uuid": task.uuid,
                "title": task.title,
                "urgencyLevel": task.urgency_level,
                "importanceLevel": task.importance_level,
                "completed": task.completed,
                "completedAt": task.completed_at.isoformat() if task.completed_at else None,
                "dueDate": task.due_date.isoformat() if task.due_date else None,
                "tags": [{"uuid": t.uuid, "name": t.name, "color": t.color} for t in tags],
                "userUuid": task.user_uuid,
                "userNickname": user.nickname if user else "unknown",
                "createdAt": task.created_at.isoformat() if task.created_at else None,
                "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
            })

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def get_task(self, uuid: str) -> dict[str, Any]:
        """获取任务详情，含完整的标签、检查项和用户信息。"""
        stmt = select(Task).where(Task.uuid == uuid, Task.deleted_at.is_(None))
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在", code="TASK_NOT_FOUND")

        tags_stmt = select(Tag).join(
            TaskTag, and_(TaskTag.tag_uuid == Tag.uuid, TaskTag.task_uuid == uuid)
        ).where(Tag.deleted_at.is_(None))
        tags = (await self.db.execute(tags_stmt)).scalars().all()

        cl_stmt = select(TaskChecklist).where(
            TaskChecklist.task_uuid == uuid, TaskChecklist.deleted_at.is_(None)
        ).order_by(TaskChecklist.sort_order.asc())
        checklist = (await self.db.execute(cl_stmt)).scalars().all()
        checklist_items = [{
            "uuid": c.uuid,
            "title": c.title,
            "completed": c.completed,
            "sortOrder": c.sort_order,
        } for c in checklist]

        user = (await self.db.execute(
            select(User).where(User.uuid == task.user_uuid)
        )).scalar_one_or_none()

        return {
            "uuid": task.uuid,
            "title": task.title,
            "urgencyLevel": task.urgency_level,
            "importanceLevel": task.importance_level,
            "dueDate": task.due_date.isoformat() if task.due_date else None,
            "recurrence": task.recurrence,
            "note": task.note,
            "tags": [{"uuid": t.uuid, "name": t.name, "color": t.color} for t in tags],
            "checklist": checklist_items,
            "completed": task.completed,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
            "sortOrder": task.sort_order,
            "userUuid": task.user_uuid,
            "userNickname": user.nickname if user else "unknown",
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }

    async def delete_task(self, uuid: str, admin_uuid: str = "") -> None:
        """软删除一个任务（管理员操作）。"""
        stmt = select(Task).where(Task.uuid == uuid, Task.deleted_at.is_(None))
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在", code="TASK_NOT_FOUND")
        task.deleted_at = datetime.utcnow()
        await self.db.flush()
        await self._record_audit(admin_uuid, "task.delete", "task", uuid)

    async def batch_tasks(
        self,
        action: str,
        task_uuids: list[str],
        admin_uuid: str = "",
    ) -> dict[str, Any]:
        """批量删除 / 恢复任务（管理员操作）。"""
        if action not in {"delete", "restore"}:
            raise ValidationException(f"不支持的批量操作: {action}", code="VALIDATION_ERROR")

        stmt = select(Task).where(Task.uuid.in_(task_uuids))
        tasks = (await self.db.execute(stmt)).scalars().all()

        affected = []
        for t in tasks:
            if action == "delete":
                if t.deleted_at is None:
                    t.deleted_at = datetime.utcnow()
                    affected.append(t.uuid)
            else:
                if t.deleted_at is not None:
                    t.deleted_at = None
                    affected.append(t.uuid)

        if affected:
            await self.db.flush()

        await self._record_audit(admin_uuid, f"task.batch_{action}", "task", "", detail={"uuids": task_uuids, "affected": affected})
        return {"affected": len(affected), "taskUuids": affected}

    async def create_task(
        self,
        admin_uuid: str,
        user_uuid: str,
        title: str,
        urgency_level: int = 0,
        importance_level: int = 0,
        due_date: str | None = None,
        note: str | None = None,
        tag_uuids: list[str] | None = None,
    ) -> dict[str, Any]:
        """管理员为指定用户创建任务。"""
        # 校验用户存在
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        if not (-4 <= urgency_level <= 4) or not (-4 <= importance_level <= 4):
            raise ValidationException(
                "紧急度/重要度必须在 -4 到 4 之间",
                code="VALIDATION_ERROR",
                detail={"urgencyLevel": "紧急度必须在 -4 到 4 之间", "importanceLevel": "重要度必须在 -4 到 4 之间"},
            )

        task = Task(
            user_uuid=user_uuid,
            title=title.strip(),
            urgency_level=urgency_level,
            importance_level=importance_level,
            due_date=date_type.fromisoformat(due_date) if due_date else None,
            note=note,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        if tag_uuids:
            await self._sync_task_tags(task.uuid, tag_uuids)

        await self._record_audit(
            admin_uuid, "task.create", "task", task.uuid,
            detail={"title": task.title, "userUuid": user_uuid, "urgencyLevel": urgency_level, "importanceLevel": importance_level},
        )
        await self.db.flush()

        return await self.get_task(task.uuid)

    async def update_task(
        self,
        uuid: str,
        admin_uuid: str = "",
        title: str | None = None,
        urgency_level: int | None = None,
        importance_level: int | None = None,
        due_date: str | None = None,
        note: str | None = None,
        completed: bool | None = None,
        tag_uuids: list[str] | None = None,
    ) -> dict[str, Any]:
        """管理员部分更新任务。"""
        stmt = select(Task).where(Task.uuid == uuid, Task.deleted_at.is_(None))
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在", code="TASK_NOT_FOUND")

        changes: list[str] = []

        if title is not None:
            task.title = title.strip()
            changes.append("title")

        if urgency_level is not None:
            if not (-4 <= urgency_level <= 4):
                raise ValidationException(
                    "紧急度必须在 -4 到 4 之间", code="VALIDATION_ERROR",
                    detail={"urgencyLevel": "紧急度必须在 -4 到 4 之间"},
                )
            task.urgency_level = urgency_level
            changes.append("urgencyLevel")

        if importance_level is not None:
            if not (-4 <= importance_level <= 4):
                raise ValidationException(
                    "重要度必须在 -4 到 4 之间", code="VALIDATION_ERROR",
                    detail={"importanceLevel": "重要度必须在 -4 到 4 之间"},
                )
            task.importance_level = importance_level
            changes.append("importanceLevel")

        if due_date is not None:
            task.due_date = date_type.fromisoformat(due_date) if due_date else None
            changes.append("dueDate")

        if note is not None:
            task.note = note
            changes.append("note")

        if completed is not None:
            task.completed = completed
            if completed:
                task.completed_at = datetime.utcnow()
            else:
                task.completed_at = None
            changes.append("completed")

        await self.db.flush()

        if tag_uuids is not None:
            await self._sync_task_tags(uuid, tag_uuids)
            changes.append("tags")

        await self._record_audit(
            admin_uuid, "task.update", "task", uuid,
            detail={"changes": changes, "title": task.title},
        )
        await self.db.flush()

        return await self.get_task(uuid)

    async def _sync_task_tags(self, task_uuid: str, tag_uuids: list[str]) -> None:
        """删除旧关联，创建新关联。"""
        # 硬删除已有的标签关联（复合主键 + 无软删除列）
        await self.db.execute(
            delete(TaskTag).where(TaskTag.task_uuid == task_uuid)
        )

        # 创建新关联
        for tag_uuid in tag_uuids:
            tt = TaskTag(task_uuid=task_uuid, tag_uuid=tag_uuid)
            self.db.add(tt)
        await self.db.flush()

    async def list_user_tasks(
        self,
        user_uuid: str,
        page: int = 1,
        page_size: int = 20,
        quadrant: int | None = None,
        completed: bool | None = None,
    ) -> dict[str, Any]:
        """列出指定用户的任务（管理员视图）。"""
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        stmt = select(Task).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),
        )

        if completed is not None:
            stmt = stmt.where(Task.completed == completed)
        if quadrant is not None:
            q_map = {
                1: (Task.urgency_level > 0, Task.importance_level > 0),
                2: (Task.urgency_level <= 0, Task.importance_level > 0),
                3: (Task.urgency_level > 0, Task.importance_level <= 0),
                4: (Task.urgency_level <= 0, Task.importance_level <= 0),
            }
            if quadrant in q_map:
                cx, cy = q_map[quadrant]
                stmt = stmt.where(cx, cy)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Task.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for task in rows:
            tags_stmt = select(Tag).join(
                TaskTag, and_(TaskTag.tag_uuid == Tag.uuid, TaskTag.task_uuid == task.uuid)
            ).where(Tag.deleted_at.is_(None))
            tags = (await self.db.execute(tags_stmt)).scalars().all()
            items.append({
                "uuid": task.uuid,
                "title": task.title,
                "urgencyLevel": task.urgency_level,
                "importanceLevel": task.importance_level,
                "completed": task.completed,
                "completedAt": task.completed_at.isoformat() if task.completed_at else None,
                "dueDate": task.due_date.isoformat() if task.due_date else None,
                "tags": [{"uuid": t.uuid, "name": t.name, "color": t.color} for t in tags],
                "createdAt": task.created_at.isoformat() if task.created_at else None,
                "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
            })

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def list_user_tags(
        self,
        user_uuid: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """列出指定用户的标签（管理员视图）。"""
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        stmt = select(Tag).where(
            Tag.deleted_at.is_(None),
            (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
        ).order_by(Tag.is_preset.desc(), Tag.name.asc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for tag in rows:
            tc_stmt = select(func.count(TaskTag.task_uuid)).where(
                TaskTag.tag_uuid == tag.uuid,
            )
            tc = (await self.db.execute(tc_stmt)).scalar() or 0
            items.append({
                "uuid": tag.uuid,
                "name": tag.name,
                "color": tag.color,
                "isPreset": tag.is_preset,
                "taskCount": tc,
                "createdAt": tag.created_at.isoformat() if tag.created_at else None,
                "updatedAt": tag.updated_at.isoformat() if tag.updated_at else None,
            })

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    # =========================================================================
    # 标签管理
    # =========================================================================

    async def create_tag(
        self,
        name: str,
        color: str = "#6366f1",
        user_uuid: str | None = None,
        admin_uuid: str = "",
    ) -> dict[str, Any]:
        """创建一个标签（管理员操作）。"""
        import re as _re
        name = name.strip()
        if not name or len(name) > 50:
            raise ValidationException("标签名称长度必须在 1-50 字符之间", code="VALIDATION_ERROR")
        if not _re.match(r"^#[0-9a-fA-F]{6}$", color):
            raise ValidationException("颜色值必须是有效的 HEX 格式", code="VALIDATION_ERROR")

        # 在同一作用域内检查重名
        dup_stmt = select(Tag).where(
            Tag.name == name,
            Tag.deleted_at.is_(None),
        )
        if user_uuid:
            dup_stmt = dup_stmt.where(Tag.user_uuid == user_uuid)
        else:
            dup_stmt = dup_stmt.where(Tag.is_preset.is_(True))
        dup = (await self.db.execute(dup_stmt)).scalar_one_or_none()
        if dup is not None:
            raise ConflictException("标签名称已存在", code="TAG_NAME_CONFLICT")

        tag = Tag(
            user_uuid=user_uuid,
            name=name,
            color=color,
            is_preset=user_uuid is None,
        )
        self.db.add(tag)
        await self.db.flush()
        await self._record_audit(admin_uuid, "tag.create", "tag", tag.uuid, detail={"name": name, "color": color})
        return {
            "uuid": tag.uuid,
            "name": tag.name,
            "color": tag.color,
            "isPreset": tag.is_preset,
            "createdAt": tag.created_at.isoformat() if tag.created_at else None,
        }

    async def list_tags(
        self,
        page: int = 1,
        page_size: int = 20,
        user_uuid: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        """管理员可见的带筛选条件的标签列表。"""
        stmt = select(Tag).where(Tag.deleted_at.is_(None))

        if user_uuid:
            stmt = stmt.where(Tag.user_uuid == user_uuid)
        if q:
            stmt = stmt.where(Tag.name.ilike(f"%{q}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Tag.is_preset.desc(), Tag.name.asc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for tag in rows:
            tc_stmt = select(func.count(TaskTag.task_uuid)).where(
                TaskTag.tag_uuid == tag.uuid,
            )
            tc = (await self.db.execute(tc_stmt)).scalar() or 0
            user = (await self.db.execute(
                select(User).where(User.uuid == tag.user_uuid)
            )).scalar_one_or_none() if tag.user_uuid else None

            items.append({
                "uuid": tag.uuid,
                "name": tag.name,
                "color": tag.color,
                "isPreset": tag.is_preset,
                "taskCount": tc,
                "userUuid": tag.user_uuid,
                "userNickname": user.nickname if user else "system",
                "createdAt": tag.created_at.isoformat() if tag.created_at else None,
            })

        return {
            "items": items,
            "meta": {"total": total, "page": page, "pageSize": page_size, "hasMore": (page * page_size) < total},
        }

    async def get_tag(self, uuid: str) -> dict[str, Any]:
        """获取标签详情，含任务计数和使用者列表。"""
        stmt = select(Tag).where(Tag.uuid == uuid, Tag.deleted_at.is_(None))
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        # 任务计数
        tc_stmt = select(func.count(TaskTag.task_uuid)).where(
            TaskTag.tag_uuid == uuid,
        )
        tc = (await self.db.execute(tc_stmt)).scalar() or 0

        # 使用该标签的用户
        # 更直接的做法：从 TaskTag 关联 Task 找到去重的 user_uuid
        subq = select(Task.user_uuid).join(
            TaskTag, TaskTag.task_uuid == Task.uuid
        ).where(
            TaskTag.tag_uuid == uuid,
            Task.deleted_at.is_(None),
        ).subquery()
        users_using = (await self.db.execute(
            select(User).where(User.uuid.in_(select(subq.c.user_uuid)))
        )).scalars().all()

        return {
            "uuid": tag.uuid,
            "name": tag.name,
            "color": tag.color,
            "isPreset": tag.is_preset,
            "taskCount": tc,
            "users": [{"uuid": u.uuid, "nickname": u.nickname} for u in users_using],
            "createdAt": tag.created_at.isoformat() if tag.created_at else None,
            "updatedAt": tag.updated_at.isoformat() if tag.updated_at else None,
        }

    async def update_tag(
        self,
        uuid: str,
        name: str | None = None,
        color: str | None = None,
        admin_uuid: str = "",
    ) -> dict[str, Any]:
        """更新标签（管理员操作）。"""
        stmt = select(Tag).where(Tag.uuid == uuid, Tag.deleted_at.is_(None))
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        changed = False

        if name is not None:
            name = name.strip()
            if not name or len(name) > 50:
                raise ValidationException("标签名称长度必须在 1-50 字符之间", code="VALIDATION_ERROR")
            if name != tag.name:
                dup = await self.db.execute(
                    select(Tag).where(
                        Tag.name == name,
                        Tag.uuid != uuid,
                        Tag.deleted_at.is_(None),
                        (Tag.user_uuid == tag.user_uuid) | (Tag.is_preset.is_(True)),
                    )
                )
                if dup.scalar_one_or_none() is not None:
                    raise ConflictException("标签名称已存在", code="TAG_NAME_CONFLICT")
                tag.name = name
                changed = True

        if color is not None:
            import re as _re
            if not _re.match(r"^#[0-9a-fA-F]{6}$", color):
                raise ValidationException("颜色值必须是有效的 HEX 格式", code="VALIDATION_ERROR")
            tag.color = color
            changed = True

        if changed:
            await self.db.flush()
            await self._record_audit(admin_uuid, "tag.update", "tag", uuid, detail={"name": name, "color": color})
            return {
                "uuid": tag.uuid,
                "name": tag.name,
                "color": tag.color,
                "updatedAt": tag.updated_at.isoformat() if tag.updated_at else None,
            }

        return {"uuid": tag.uuid, "name": tag.name, "color": tag.color}

    async def delete_tag(self, uuid: str, admin_uuid: str = "") -> None:
        """软删除一个标签，并硬删除其 TaskTag 关联（管理员操作）。"""
        stmt = select(Tag).where(Tag.uuid == uuid, Tag.deleted_at.is_(None))
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        # 硬删除该标签的所有 TaskTag 关联
        await self.db.execute(
            delete(TaskTag).where(TaskTag.tag_uuid == uuid)
        )

        tag.deleted_at = datetime.utcnow()
        await self.db.flush()
        await self._record_audit(admin_uuid, "tag.delete", "tag", uuid)

    # =========================================================================
    # 内部辅助方法
    # =========================================================================

    async def _get_user(self, uuid: str) -> User | None:
        stmt = select(User).where(User.uuid == uuid, User.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _ensure_active(self, user: User) -> None:
        if user.status == UserStatus.banned:
            raise UnauthorizedException("账号已被封禁", code="AUTH_USER_BANNED")
        if user.status == UserStatus.disabled:
            raise UnauthorizedException("账号已被禁用", code="AUTH_USER_DISABLED")

    @staticmethod
    def _user_to_out(user: User) -> dict[str, Any]:
        return {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "avatarUrl": user.avatar_url,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": user.status.value if hasattr(user.status, "value") else str(user.status),
            "locale": user.locale,
            "createdAt": user.created_at.isoformat() if user.created_at else None,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
            "permissions": [],
        }

    async def _issue_token_pair(self, user: User) -> dict[str, Any]:
        extra = {"role": user.role.value if hasattr(user.role, "value") else str(user.role)}
        access_token, _, access_exp = create_access_token(user.uuid, extra_claims=extra)
        refresh_token_str, jti, refresh_exp = create_refresh_token(user.uuid)

        self.db.add(
            RefreshToken(
                user_uuid=user.uuid,
                jti=jti,
                token_hash=sha256_hex(refresh_token_str),
                expires_at=refresh_exp,
            )
        )
        await self.db.flush()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "Bearer",
            "expires_in": int((access_exp - datetime.utcnow()).total_seconds()),
        }

    async def _resolve_refresh_token(self, token: str) -> RefreshToken:
        from jose import JWTError
        from src.core.security import decode_token

        try:
            payload = decode_token(token, expected_type="refresh")
        except JWTError as exc:
            raise UnauthorizedException("refresh_token 无效或已过期", code="AUTH_REFRESH_TOKEN_INVALID") from exc

        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedException("refresh_token 缺少 jti", code="AUTH_REFRESH_TOKEN_INVALID")

        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.deleted_at.is_(None),
        )
        record = (await self.db.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise UnauthorizedException("refresh_token 不存在", code="AUTH_REFRESH_TOKEN_INVALID")
        if record.revoked_at is not None:
            await self._revoke_all_refresh_tokens(record.user_uuid)
            raise UnauthorizedException("refresh_token 已被吊销", code="AUTH_REFRESH_TOKEN_INVALID")
        if record.expires_at <= datetime.utcnow():
            raise UnauthorizedException("refresh_token 已过期", code="AUTH_REFRESH_TOKEN_INVALID")
        if record.token_hash != sha256_hex(token):
            raise UnauthorizedException("refresh_token 哈希不匹配", code="AUTH_REFRESH_TOKEN_INVALID")
        return record

    async def _revoke_all_refresh_tokens(self, user_uuid: str) -> int:
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_uuid == user_uuid,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.deleted_at.is_(None),
            )
            .values(revoked_at=datetime.utcnow())
        )
        result = await self.db.execute(stmt)
        return result.rowcount or 0


__all__ = ["AdminService"]
