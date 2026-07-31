import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useAuth } from './AuthProvider'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      // Hiển thị message tiếng Việt từ backend, không hiện lỗi kỹ thuật
      setError(err instanceof ApiError ? err.message : 'Không thể đăng nhập. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-white p-8 shadow-sm"
      >
        <h1 className="mb-1 text-xl font-semibold">Smart IT Helpdesk</h1>
        <p className="mb-6 text-sm text-slate-500">Đăng nhập bằng tài khoản công ty</p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <label htmlFor="email" className="mb-1 block text-sm font-medium">Email</label>
        <input
          id="email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="ten.ban@company.com"
        />

        <label htmlFor="password" className="mb-1 block text-sm font-medium">Mật khẩu</label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />

        {/* Vô hiệu hoá trong lúc chờ — chống bấm hai lần */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium text-white
                     hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>
      </form>
    </div>
  )
}
