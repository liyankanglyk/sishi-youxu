import { useState } from 'react'
import { Hourglass, EnvelopeSimple, LockSimple, Phone, Eye, EyeSlash } from '@phosphor-icons/react'
import { useStore } from '../store/useStore'

type Tab = 'login' | 'register'

export function LoginPage() {
  const signUp = useStore((s) => s.signUp)
  const signInWithPassword = useStore((s) => s.signInWithPassword)
  const signInWithEmail = useStore((s) => s.signInWithEmail)

  const [tab, setTab] = useState<Tab>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Magic Link
  const [magicSent, setMagicSent] = useState(false)

  const reset = () => { setEmail(''); setPassword(''); setConfirmPassword(''); setError('') }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) return
    if (tab === 'register' && password !== confirmPassword) { setError('两次密码不一致'); return }
    if (password.length < 6) { setError('密码至少 6 位'); return }
    setLoading(true); setError('')
    try {
      if (tab === 'register') await signUp(email.trim(), password)
      else await signInWithPassword(email.trim(), password)
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('already registered') || msg.includes('already been registered') || msg.includes('unique_phone_number')) {
        setError('该邮箱已被注册，请直接登录')
      } else if (msg.includes('Invalid login') || msg.includes('invalid_credentials')) {
        setError('邮箱或密码错误')
      } else if (msg.includes('rate limited') || msg.includes('too many')) {
        setError('操作太频繁，请稍后再试')
      } else if (msg.includes('Email not confirmed') || msg.includes('not confirmed')) {
        setError('邮箱未验证，请检查收件箱')
      } else if (msg.includes('password')) {
        setError('密码不符合要求（至少 6 位）')
      } else {
        setError(msg || '操作失败，请重试')
      }
    } finally { setLoading(false) }
  }

  const handleMagicLink = async () => {
    if (!email.trim()) { setError('请先输入邮箱'); return }
    setLoading(true); setError('')
    try {
      await signInWithEmail(email.trim())
      setMagicSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败')
    } finally { setLoading(false) }
  }

  if (magicSent) {
    return (
      <div className="h-full flex items-center justify-center bg-[var(--bg-page)] px-4">
        <div className="w-full max-w-sm text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-green-50 mb-4">
            <EnvelopeSimple weight="fill" className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>邮件已发送</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
            请检查 <strong>{email}</strong> 的收件箱，点击链接登录
          </p>
          <button onClick={() => { setMagicSent(false); reset() }}
            className="mt-6 text-sm font-medium text-purple-400 hover:text-purple-500 transition-colors">返回</button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex items-center justify-center bg-[var(--bg-page)] px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-purple-50 mb-4">
            <Hourglass weight="fill" className="w-8 h-8 text-purple-400" />
          </div>
          <h1 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>四时有序</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
            {tab === 'login' ? '登录以跨设备同步任务数据' : '注册账号开始使用'}
          </p>
        </div>

        {/* 登录/注册 */}
        <div className="flex bg-gray-100 rounded-2xl p-0.5 mb-6">
          <button onClick={() => { setTab('login'); reset() }}
            className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-all ${tab === 'login' ? 'bg-white text-purple-400 shadow-sm' : 'text-gray-400'}`}>登录</button>
          <button onClick={() => { setTab('register'); reset() }}
            className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-all ${tab === 'register' ? 'bg-white text-purple-400 shadow-sm' : 'text-gray-400'}`}>注册</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <EnvelopeSimple weight="regular" className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="邮箱地址" required autoFocus autoComplete="email"
              className="w-full pl-10 pr-4 py-3 text-sm border-0 bg-white rounded-2xl focus:outline-none focus:ring-2 focus:ring-purple-200 placeholder:text-gray-300 transition-all" />
          </div>
          <div className="relative">
            <LockSimple weight="regular" className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
            <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="密码（至少 6 位）" required autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              className="w-full pl-10 pr-10 py-3 text-sm border-0 bg-white rounded-2xl focus:outline-none focus:ring-2 focus:ring-purple-200 placeholder:text-gray-300 transition-all" />
            <button type="button" onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5" style={{ color: 'var(--text-muted)' }}>
              {showPassword ? <EyeSlash weight="regular" className="w-4 h-4" /> : <Eye weight="regular" className="w-4 h-4" />}
            </button>
          </div>
          {tab === 'register' && (
            <div className="relative">
              <LockSimple weight="regular" className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="确认密码" required autoComplete="new-password"
                className="w-full pl-10 pr-4 py-3 text-sm border-0 bg-white rounded-2xl focus:outline-none focus:ring-2 focus:ring-purple-200 placeholder:text-gray-300 transition-all" />
            </div>
          )}
          {error && <p className="text-xs text-red-400 bg-red-50 px-3 py-2 rounded-xl">{error}</p>}
          <button type="submit" disabled={loading || !email.trim() || !password}
            className="w-full py-3 text-sm font-medium text-white bg-purple-400 hover:bg-purple-500 rounded-2xl shadow-sm disabled:opacity-30 transition-all active:scale-[0.98]">
            {loading ? '处理中…' : tab === 'register' ? '注册' : '登录'}
          </button>
        </form>

        {/* Magic Link + 手机号预留 */}
        {tab === 'login' && (
          <div className="mt-4 text-center">
            <button onClick={handleMagicLink} disabled={loading}
              className="text-sm font-medium text-purple-400 hover:text-purple-500 transition-colors disabled:opacity-40">
              免密码登录（发送邮箱链接）
            </button>
          </div>
        )}

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>更多登录方式</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        <button disabled
          className="w-full flex items-center justify-center gap-3 py-3 text-sm font-medium bg-gray-100 text-gray-350 rounded-2xl disabled:cursor-not-allowed">
          <Phone weight="regular" className="w-5 h-5" />
          手机号登录（即将推出）
        </button>
      </div>
    </div>
  )
}
