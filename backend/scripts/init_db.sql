-- =============================================================================
-- 四时有序 (sishi-youxu) — 数据库初始化脚本
-- =============================================================================
-- 数据库：sishi_youxu
-- 字符集：utf8mb4 / utf8mb4_unicode_ci
-- 存储引擎：InnoDB
-- 表前缀：sishiyouxu_
--
-- 兼容要点：
--   - sishiyouxu_auth_identity.provider ENUM 包含 'wechat'，供微信小程序登录
--   - sishiyouxu_notification 新增 `template_id` 列 + 'wechat_subscribe' kind
--   - sishiyouxu_admin_permission 仅保留 (role, permission) 联合主键
--   - 所有核心业务表含 deleted_at 软删除标记；仅追加表（audit/login）不含
--
-- 使用方法：
--   mysql -u root -p < scripts/init_db.sql
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- 1. 重建数据库（存在则删除，不存在则创建）
-- ---------------------------------------------------------------------------

DROP DATABASE IF EXISTS `sishi_youxu`;

CREATE DATABASE `sishi_youxu`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `sishi_youxu`;

-- ---------------------------------------------------------------------------
-- 2. 用户域
-- ---------------------------------------------------------------------------

-- 用户主表
DROP TABLE IF EXISTS `sishiyouxu_user`;
CREATE TABLE `sishiyouxu_user` (
    `uuid`        CHAR(36)    NOT NULL                    COMMENT '主键 UUID',
    `nickname`    VARCHAR(50) NOT NULL DEFAULT ''         COMMENT '昵称',
    `avatar_url`  VARCHAR(500)        DEFAULT NULL         COMMENT '头像 URL',
    `role`        VARCHAR(20) NOT NULL DEFAULT 'user'
                  COMMENT '角色: user / admin / super_admin',
    `status`      VARCHAR(20) NOT NULL DEFAULT 'active'
                  COMMENT '状态: active / disabled / banned / deleted',
    `locale`      VARCHAR(10) NOT NULL DEFAULT 'zh-CN'    COMMENT '语言偏好',
    `created_at`  DATETIME    NOT NULL                    COMMENT '创建时间',
    `updated_at`  DATETIME    NOT NULL                    COMMENT '更新时间',
    `deleted_at`  DATETIME             DEFAULT NULL       COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_role_status` (`role`, `status`),
    KEY `idx_created_at`  (`created_at`),
    KEY `idx_deleted_at`  (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户主表';

-- 认证身份表（同一 user 可关联多种 provider，含 wechat）
DROP TABLE IF EXISTS `sishiyouxu_auth_identity`;
CREATE TABLE `sishiyouxu_auth_identity` (
    `uuid`         CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `user_uuid`    CHAR(36)     NOT NULL                COMMENT '关联用户 UUID',
    `provider`     VARCHAR(20)  NOT NULL
                   COMMENT '登录方式: password / phone_sms / email_code / wechat',
    `provider_uid` VARCHAR(255) NOT NULL
                   COMMENT 'provider 唯一标识 (微信存 openid / unionid)',
    `credentials`  TEXT                  DEFAULT NULL
                   COMMENT '凭证 (password 存 bcrypt 哈希)',
    `created_at`   DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`   DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`   DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    UNIQUE KEY `uk_provider_uid` (`provider`, `provider_uid`),
    KEY `idx_user_uuid`   (`user_uuid`),
    KEY `idx_deleted_at`  (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='认证身份表';

-- Refresh Token
DROP TABLE IF EXISTS `sishiyouxu_refresh_token`;
CREATE TABLE `sishiyouxu_refresh_token` (
    `uuid`        CHAR(36)    NOT NULL                COMMENT '主键 UUID',
    `user_uuid`   CHAR(36)    NOT NULL                COMMENT '关联用户',
    `jti`         VARCHAR(64) NOT NULL                COMMENT 'JWT ID',
    `token_hash`  VARCHAR(64) NOT NULL                COMMENT 'Token SHA-256',
    `expires_at`  DATETIME    NOT NULL                COMMENT '过期时间',
    `created_at`  DATETIME    NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME    NOT NULL                COMMENT '更新时间',
    `revoked_at`  DATETIME             DEFAULT NULL   COMMENT '撤销时间',
    `deleted_at`  DATETIME             DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    UNIQUE KEY `uk_jti`        (`jti`),
    KEY        `idx_user_uuid` (`user_uuid`),
    KEY        `idx_expires_at` (`expires_at`),
    KEY        `idx_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Refresh Token 表';

-- ---------------------------------------------------------------------------
-- 3. 任务域
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS `sishiyouxu_task`;
CREATE TABLE `sishiyouxu_task` (
    `uuid`                    CHAR(36)      NOT NULL DEFAULT ''                COMMENT '主键 UUID',
    `user_uuid`               CHAR(36)      NOT NULL                          COMMENT '所属用户',
    `title`                   VARCHAR(255)  NOT NULL                          COMMENT '任务标题',
    `urgency_level`           INT           NOT NULL DEFAULT 0                 COMMENT '紧急度 -4..4',
    `importance_level`        INT           NOT NULL DEFAULT 0                 COMMENT '重要度 -4..4',
    `due_date`                DATE                   DEFAULT NULL             COMMENT '截止日期',
    `recurrence`              TEXT                   DEFAULT NULL
                              COMMENT '重复规则 (RFC 5545 RRULE, 可含 EXDATE/RDATE)',
    `note`                    TEXT                   DEFAULT NULL             COMMENT 'Markdown 备注',
    `completed`               TINYINT(1)    NOT NULL DEFAULT 0                 COMMENT '完成状态',
    `completed_at`            DATETIME              DEFAULT NULL              COMMENT '完成时间',
    `sort_order`              INT           NOT NULL DEFAULT 0                 COMMENT '象限内排序',
    `remind_at`               DATETIME              DEFAULT NULL              COMMENT '应被提醒时间',
    `remind_offset_minutes`   INT                   DEFAULT NULL
                              COMMENT '提前提醒分钟数 (NULL=用 due_date 当天 9:00)',
    `reminder_state`          VARCHAR(16)  NOT NULL DEFAULT 'pending'
                              COMMENT '提醒状态: pending / sent / cancelled',
    `created_at`              DATETIME      NOT NULL                          COMMENT '创建时间',
    `updated_at`              DATETIME      NOT NULL                          COMMENT '更新时间',
    `deleted_at`              DATETIME              DEFAULT NULL              COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_completed` (`user_uuid`, `completed`),
    KEY `idx_user_due_date`  (`user_uuid`, `due_date`),
    KEY `idx_user_remind`    (`remind_at`, `reminder_state`),
    KEY `idx_updated_at`     (`updated_at`),
    KEY `idx_deleted_at`     (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- 标签表
DROP TABLE IF EXISTS `sishiyouxu_tag`;
CREATE TABLE `sishiyouxu_tag` (
    `uuid`        CHAR(36)    NOT NULL                COMMENT '主键 UUID',
    `user_uuid`   CHAR(36)             DEFAULT NULL   COMMENT '所属用户 (预设标签为 NULL)',
    `name`        VARCHAR(50) NOT NULL                COMMENT '标签名称',
    `color`       VARCHAR(9)  NOT NULL DEFAULT '#cccccc' COMMENT 'HEX 颜色',
    `is_preset`   TINYINT(1)  NOT NULL DEFAULT 0     COMMENT '是否预设标签',
    `created_at`  DATETIME    NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME    NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME             DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_name`   (`user_uuid`, `name`),
    KEY `idx_user_uuid`   (`user_uuid`),
    KEY `idx_deleted_at`  (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标签表';

-- 任务-标签关联
DROP TABLE IF EXISTS `sishiyouxu_task_tag`;
CREATE TABLE `sishiyouxu_task_tag` (
    `task_uuid`   CHAR(36)  NOT NULL                COMMENT '任务 UUID',
    `tag_uuid`    CHAR(36)  NOT NULL                COMMENT '标签 UUID',
    `created_at`  DATETIME  NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME  NOT NULL                COMMENT '更新时间',
    PRIMARY KEY (`task_uuid`, `tag_uuid`),
    KEY `idx_tag_uuid`  (`tag_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务-标签关联';

-- 检查项
DROP TABLE IF EXISTS `sishiyouxu_task_checklist`;
CREATE TABLE `sishiyouxu_task_checklist` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `task_uuid`   CHAR(36)     NOT NULL                COMMENT '所属任务',
    `title`       VARCHAR(255) NOT NULL                COMMENT '检查项标题',
    `completed`   TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '完成状态',
    `sort_order`  INT          NOT NULL DEFAULT 0      COMMENT '排序',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_task_sort`  (`task_uuid`, `sort_order`),
    KEY `idx_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务检查项';

-- ---------------------------------------------------------------------------
-- 4. 通知 / 反馈
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS `sishiyouxu_notification`;
CREATE TABLE `sishiyouxu_notification` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `user_uuid`   CHAR(36)     NOT NULL                COMMENT '所属用户',
    `kind`        VARCHAR(32)  NOT NULL
                  COMMENT '通知类型: task_reminder / system_announcement / wechat_subscribe',
    `is_read`     TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '是否已读',
    `read_at`     DATETIME              DEFAULT NULL   COMMENT '已读时间',
    `title`       VARCHAR(200) NOT NULL                COMMENT '通知标题',
    `body`        TEXT         NOT NULL                COMMENT '通知内容',
    `task_uuid`   CHAR(36)              DEFAULT NULL   COMMENT '关联任务',
    `template_id` VARCHAR(64)           DEFAULT NULL
                  COMMENT '微信订阅消息模板 ID (仅 wechat_subscribe 使用)',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_is_read` (`user_uuid`, `is_read`),
    KEY `idx_user_created` (`user_uuid`, `created_at`),
    KEY `idx_task_uuid`    (`task_uuid`),
    KEY `idx_deleted_at`   (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知表';

DROP TABLE IF EXISTS `sishiyouxu_feedback`;
CREATE TABLE `sishiyouxu_feedback` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `user_uuid`   CHAR(36)              DEFAULT NULL   COMMENT '反馈用户',
    `content`     TEXT         NOT NULL                COMMENT '反馈内容',
    `contact`     VARCHAR(100)          DEFAULT NULL   COMMENT '联系方式',
    `status`      VARCHAR(16)  NOT NULL DEFAULT 'pending'
                  COMMENT '处理状态: pending / processing / resolved',
    `handled_by`  CHAR(36)              DEFAULT NULL   COMMENT '处理人',
    `handled_at`  DATETIME              DEFAULT NULL   COMMENT '处理时间',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_uuid`  (`user_uuid`),
    KEY `idx_status`     (`status`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈';

-- ---------------------------------------------------------------------------
-- 5. 审计 / 登录日志（仅追加，无 deleted_at）
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS `sishiyouxu_audit_log`;
CREATE TABLE `sishiyouxu_audit_log` (
    `uuid`          CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `user_uuid`     CHAR(36)              DEFAULT NULL   COMMENT '操作用户',
    `action`        VARCHAR(100) NOT NULL                COMMENT '操作类型',
    `resource_type` VARCHAR(50)  NOT NULL                COMMENT '资源类型',
    `resource_uuid` CHAR(36)              DEFAULT NULL   COMMENT '资源 UUID',
    `ip_address`    VARCHAR(45)           DEFAULT NULL   COMMENT 'IP 地址',
    `user_agent`    VARCHAR(500)          DEFAULT NULL   COMMENT 'User Agent',
    `detail`        JSON                  DEFAULT NULL   COMMENT '详细数据',
    `created_at`    DATETIME     NOT NULL                COMMENT '操作时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_action` (`user_uuid`, `action`),
    KEY `idx_resource`    (`resource_type`, `resource_uuid`),
    KEY `idx_created_at`  (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志 (仅追加)';

DROP TABLE IF EXISTS `sishiyouxu_login_log`;
CREATE TABLE `sishiyouxu_login_log` (
    `uuid`         CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `user_uuid`    CHAR(36)              DEFAULT NULL   COMMENT '登录用户',
    `provider`     VARCHAR(32)  NOT NULL
                   COMMENT '登录方式: password / phone_sms / email_code / wechat',
    `ip_address`   VARCHAR(45)           DEFAULT NULL   COMMENT 'IP',
    `user_agent`   VARCHAR(500)          DEFAULT NULL   COMMENT 'User Agent',
    `login_status` VARCHAR(16)  NOT NULL                COMMENT 'success / failed',
    `fail_reason`  VARCHAR(100)          DEFAULT NULL   COMMENT '失败原因',
    `created_at`   DATETIME     NOT NULL                COMMENT '登录时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_user_login`  (`user_uuid`, `login_status`),
    KEY `idx_created_at`  (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志 (仅追加)';

-- ---------------------------------------------------------------------------
-- 6. 系统配置 / 敏感词 / 公告 / 黑名单 / 管理员权限
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS `sishiyouxu_system_config`;
CREATE TABLE `sishiyouxu_system_config` (
    `key`         VARCHAR(100) NOT NULL                COMMENT '配置键',
    `value`       TEXT                  DEFAULT NULL   COMMENT '配置值',
    `description` VARCHAR(255)          DEFAULT NULL   COMMENT '配置描述',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置 KV 表';

DROP TABLE IF EXISTS `sishiyouxu_sensitive_word`;
CREATE TABLE `sishiyouxu_sensitive_word` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `word`        VARCHAR(100) NOT NULL                COMMENT '敏感词',
    `level`       TINYINT      NOT NULL DEFAULT 1      COMMENT '敏感等级 1-3',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    UNIQUE KEY `uk_word` (`word`),
    KEY `idx_word`      (`word`),
    KEY `idx_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='敏感词表';

DROP TABLE IF EXISTS `sishiyouxu_announcement`;
CREATE TABLE `sishiyouxu_announcement` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `title`       VARCHAR(200) NOT NULL                COMMENT '公告标题',
    `content`     TEXT         NOT NULL                COMMENT '公告内容',
    `type`        VARCHAR(16)  NOT NULL DEFAULT 'info'
                  COMMENT '公告类型: info / warning / critical',
    `is_pinned`   TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '是否置顶',
    `is_active`   TINYINT(1)   NOT NULL DEFAULT 1      COMMENT '是否生效',
    `start_time`  DATETIME              DEFAULT NULL   COMMENT '生效开始时间',
    `end_time`    DATETIME              DEFAULT NULL   COMMENT '生效结束时间',
    `created_by`  CHAR(36)              DEFAULT NULL   COMMENT '创建人',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    `deleted_at`  DATETIME              DEFAULT NULL   COMMENT '软删除时间',
    PRIMARY KEY (`uuid`),
    KEY `idx_active_time` (`is_active`, `start_time`, `end_time`),
    KEY `idx_deleted_at`  (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统公告';

DROP TABLE IF EXISTS `sishiyouxu_ip_blacklist`;
CREATE TABLE `sishiyouxu_ip_blacklist` (
    `uuid`        CHAR(36)     NOT NULL                COMMENT '主键 UUID',
    `ip_address`  VARCHAR(45)  NOT NULL                COMMENT 'IP 地址',
    `reason`      VARCHAR(255)          DEFAULT NULL   COMMENT '封禁原因',
    `created_by`  CHAR(36)              DEFAULT NULL   COMMENT '创建人',
    `expires_at`  DATETIME              DEFAULT NULL   COMMENT '过期时间 (NULL=永久)',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL                COMMENT '更新时间',
    PRIMARY KEY (`uuid`),
    UNIQUE KEY `uk_ip`  (`ip_address`),
    KEY `idx_ip`         (`ip_address`),
    KEY `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='IP 黑名单';

DROP TABLE IF EXISTS `sishiyouxu_admin_permission`;
CREATE TABLE `sishiyouxu_admin_permission` (
    `role`        VARCHAR(20)  NOT NULL                COMMENT '角色: super_admin / admin',
    `permission`  VARCHAR(100) NOT NULL                COMMENT '权限节点',
    `created_at`  DATETIME     NOT NULL                COMMENT '创建时间',
    PRIMARY KEY (`role`, `permission`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员权限矩阵';

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- DDL 完成。种子数据由单独的 seed.sql 维护（避免误提交到生产）。
-- =============================================================================
USE `sishi_youxu`;

-- ---------------------------------------------------------------------------
-- 1. 4 个预设标签（全局，user_uuid 为 NULL 占位）
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO `sishiyouxu_tag`
    (`uuid`, `user_uuid`, `name`, `color`, `is_preset`, `created_at`, `updated_at`)
VALUES
    ('00000000-0000-0000-0000-000000000001', NULL, '工作', '#3B82F6', 1, NOW(), NOW()),
    ('00000000-0000-0000-0000-000000000002', NULL, '学习', '#22C55E', 1, NOW(), NOW()),
    ('00000000-0000-0000-0000-000000000003', NULL, '生活', '#F97316', 1, NOW(), NOW()),
    ('00000000-0000-0000-0000-000000000004', NULL, '健康', '#EF4444', 1, NOW(), NOW());

-- ---------------------------------------------------------------------------
-- 2. 管理员权限矩阵
-- ---------------------------------------------------------------------------
-- super_admin 全量权限
INSERT IGNORE INTO `sishiyouxu_admin_permission` (`role`, `permission`, `created_at`) VALUES
    ('super_admin', 'user:read',          NOW()),
    ('super_admin', 'user:update',        NOW()),
    ('super_admin', 'user:delete',        NOW()),
    ('super_admin', 'user:force_logout',  NOW()),
    ('super_admin', 'user:export',        NOW()),
    ('super_admin', 'task:audit',         NOW()),
    ('super_admin', 'task:delete',        NOW()),
    ('super_admin', 'sensitive_word:manage', NOW()),
    ('super_admin', 'sensitive_word:toggle', NOW()),
    ('super_admin', 'system_config:read', NOW()),
    ('super_admin', 'system_config:write',NOW()),
    ('super_admin', 'backup:create',      NOW()),
    ('super_admin', 'backup:restore',     NOW()),
    ('super_admin', 'announcement:manage',NOW()),
    ('super_admin', 'preset_tag:manage',  NOW()),
    ('super_admin', 'ip_blacklist:manage',NOW()),
    ('super_admin', 'audit_log:read',     NOW()),
    ('super_admin', 'admin:manage',       NOW());

-- admin 子集（不含 user:delete / user:export / sensitive_word / backup / ip_blacklist / admin:manage / system_config:write）
INSERT IGNORE INTO `sishiyouxu_admin_permission` (`role`, `permission`, `created_at`) VALUES
    ('admin', 'user:read',          NOW()),
    ('admin', 'user:update',        NOW()),
    ('admin', 'user:force_logout',  NOW()),
    ('admin', 'task:audit',         NOW()),
    ('admin', 'task:delete',        NOW()),
    ('admin', 'system_config:read', NOW()),
    ('admin', 'announcement:manage',NOW()),
    ('admin', 'preset_tag:manage',  NOW()),
    ('admin', 'audit_log:read',     NOW());

-- ---------------------------------------------------------------------------
-- 3. 系统配置默认值
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO `sishiyouxu_system_config` (`key`, `value`, `description`, `created_at`, `updated_at`) VALUES
    ('site.name',                  '四时有序',                  '站点名称',           NOW(), NOW()),
    ('site.icp',                   '',                          'ICP 备案号',         NOW(), NOW()),
    ('registration.enabled',       'true',                      '是否允许新用户注册', NOW(), NOW()),
    ('feature.phone_login',        'true',                      '是否启用手机号登录', NOW(), NOW()),
    ('feature.email_login',        'true',                      '是否启用邮箱登录',   NOW(), NOW()),
    ('feature.wechat_login',       'true',                      '是否启用微信小程序登录', NOW(), NOW()),
    ('rate.login.window_seconds',  '900',                       '登录限流窗口（秒）', NOW(), NOW()),
    ('rate.login.max_attempts',    '10',                        '窗口内最大登录尝试', NOW(), NOW()),
    ('maintenance.enabled',        'false',                     '是否处于维护模式',   NOW(), NOW()),
    ('maintenance.message',        '系统升级中，请稍后再试',     '维护公告',           NOW(), NOW());
