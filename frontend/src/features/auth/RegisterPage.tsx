import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useAuth } from './AuthProvider'

// Chính sách mật khẩu khớp backend (app/core/security.py): >= 8 ký tự,
// có ít nhất 1 chữ hoa, 1 chữ thường, 1 chữ số.
const PASSWORD_PATTERNS = [
  { test: (v: string) => v.length >= 8, message: 'Mật khẩu phải có ít nhất 8 ký tự' },
  { test: (v: string) => /[A-Z]/.test(v), message: 'Mật khẩu phải có ít nhất 1 chữ hoa' },
  { test: (v: string) => /[a-z]/.test(v), message: 'Mật khẩu phải có ít nhất 1 chữ thường' },
  { test: (v: string) => /[0-9]/.test(v), message: 'Mật khẩu phải có ít nhất 1 chữ số' },
]

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    // Validate chính sách mật khẩu phía FE trước khi gửi
    for (const rule of PASSWORD_PATTERNS) {
      if (!rule.test(password)) {
        setError(rule.message)
        return
      }
    }

    setSubmitting(true)
    try {
      await register(fullName.trim(), email, password)
      navigate('/login', { state: { registered: true }, replace: true })
    } catch (err) {
      // Hiển thị message tiếng Việt từ backend (email trùng 409, password yếu 422)
      setError(err instanceof ApiError ? err.message : 'Không thể đăng ký. Vui lòng thử lại.')
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
        <p className="mb-6 text-sm text-slate-500">Tạo tài khoản nhân viên</p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <label htmlFor="fullName" className="mb-1 block text-sm font-medium">Họ và tên</label>
        <input
          id="fullName"
          type="text"
          required
          autoComplete="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="mb-4 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="Nguyễn Văn A"
        />

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
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="Ít nhất 8 ký tự, có chữ hoa, chữ thường và số"
        />

        {/* Vô hiệu hoá trong lúc chờ — chống bấm hai lần */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium text-white
                     hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? 'Đang đăng ký…' : 'Đăng ký'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Đã có tài khoản?{' '}
          <Link to="/login" className="text-blue-600 hover:underline">Đăng nhập</Link>
        </p>
      </form>
    </div>
  )
}
