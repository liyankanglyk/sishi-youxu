/** Supabase 数据库类型（与 001_schema.sql 对应） */
export interface Database {
  public: {
    Tables: {
      sishi_tasks: {
        Row: {
          id: string
          user_id: string
          title: string
          pos_x: number
          pos_y: number
          urgency_level: number
          importance_level: number
          due_date: string | null
          tags: string[]
          note: string
          recurrence: string | null
          generated_next_id: string | null
          completed: boolean
          completed_at: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          title: string
          pos_x?: number
          pos_y?: number
          urgency_level?: number
          importance_level?: number
          due_date?: string | null
          tags?: string[]
          note?: string
          recurrence?: string | null
          generated_next_id?: string | null
          completed?: boolean
          completed_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          title?: string
          pos_x?: number
          pos_y?: number
          urgency_level?: number
          importance_level?: number
          due_date?: string | null
          tags?: string[]
          note?: string
          recurrence?: string | null
          generated_next_id?: string | null
          completed?: boolean
          completed_at?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      sishi_tags: {
        Row: {
          id: string
          user_id: string
          name: string
          color: string
          is_preset: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          color?: string
          is_preset?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          color?: string
          is_preset?: boolean
          created_at?: string
        }
      }
    }
  }
}
