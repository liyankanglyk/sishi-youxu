-- 四时有序 Supabase 数据库 Schema
-- 使用方法：在 Supabase Dashboard → SQL Editor 中执行此文件

-- ===== 1. Tags 表 =====
CREATE TABLE IF NOT EXISTS public.sishi_tags (
  id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name      TEXT NOT NULL,
  color     TEXT NOT NULL DEFAULT '#A78BFA',
  is_preset BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== 2. Tasks 表 =====
CREATE TABLE IF NOT EXISTS public.sishi_tasks (
  id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  pos_x            REAL NOT NULL DEFAULT 0.5,
  pos_y            REAL NOT NULL DEFAULT 0.5,
  urgency_level    INT NOT NULL DEFAULT 0,
  importance_level INT NOT NULL DEFAULT 0,
  due_date         TEXT,
  tags             TEXT[] DEFAULT '{}',
  note             TEXT DEFAULT '',
  recurrence       TEXT DEFAULT NULL,
  generated_next_id TEXT DEFAULT NULL,
  completed        BOOLEAN NOT NULL DEFAULT false,
  completed_at     TEXT,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);

-- ===== 3. 启用 Row-Level Security =====
ALTER TABLE public.sishi_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sishi_tasks ENABLE ROW LEVEL SECURITY;

-- ===== 4. RLS 策略：用户只能访问自己的数据 =====
-- Tags
CREATE POLICY "Users can read own tags"
  ON public.sishi_tags FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own tags"
  ON public.sishi_tags FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tags"
  ON public.sishi_tags FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own tags"
  ON public.sishi_tags FOR DELETE
  USING (auth.uid() = user_id);

-- Tasks
CREATE POLICY "Users can read own tasks"
  ON public.sishi_tasks FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own tasks"
  ON public.sishi_tasks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tasks"
  ON public.sishi_tasks FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own tasks"
  ON public.sishi_tasks FOR DELETE
  USING (auth.uid() = user_id);

-- ===== 5. 实时同步 =====
ALTER PUBLICATION supabase_realtime ADD TABLE public.sishi_tasks;
ALTER PUBLICATION supabase_realtime ADD TABLE public.sishi_tags;

-- ===== 6. 索引 =====
CREATE INDEX IF NOT EXISTS idx_sishi_tasks_user_id ON public.sishi_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_sishi_tasks_updated_at ON public.sishi_tasks(updated_at);
CREATE INDEX IF NOT EXISTS idx_sishi_tags_user_id ON public.sishi_tags(user_id);
