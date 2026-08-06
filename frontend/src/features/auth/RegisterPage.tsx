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

  const HIGHLIGHTS = [
    'Gửi yêu cầu IT trong vài giây',
    'Theo dõi tiến độ xử lý minh bạch',
    'Đội IT phản hồi đúng cam kết SLA',
  ]

  return (
    <div className="flex min-h-screen">
      {/* Cột trái — brand (ẩn trên mobile, hiện từ md) */}
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden
                         bg-gradient-to-br from-blue-950 via-blue-900 to-sky-900 p-12 text-white md:flex">
        {/* Bóng tròn trôi chậm */}
        <div
          className="animate-float pointer-events-none absolute -left-24 top-24 h-72 w-72
                     rounded-full bg-blue-500/20 blur-3xl"
        />
        <div
          className="animate-float-delayed pointer-events-none absolute -right-16 bottom-16 h-96 w-96
                     rounded-full bg-sky-400/10 blur-3xl"
        />

        <div className="relative flex items-center gap-3">
          <img
            src="/help-desk-logo.jpg"
            alt="Smart IT Helpdesk"
            className="h-10 w-10 rounded-lg object-cover ring-2 ring-white/30"
          />
          <span className="text-lg font-semibold tracking-wide text-white">Smart IT Helpdesk</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl font-bold leading-tight">
            Hệ thống quản lý dịch vụ IT thông minh
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-sky-200/80">
            Một nơi để nhân viên gửi yêu cầu, theo dõi tiến độ và đội IT xử lý nhanh chóng,
            minh bạch.
          </p>

          <ul className="mt-8 space-y-3">
            {HIGHLIGHTS.map((item) => (
              <li key={item} className="flex items-center gap-3 text-sm text-sky-100">
                <span className="flex h-5 w-5 items-center justify-center rounded-full
                                 bg-sky-400/20 text-xs text-sky-300">
                  ✓
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative">
          <div className="mb-4 h-px w-24 bg-sky-300/30" />
          <p className="text-xs text-sky-200/60">© 2026 Smart IT Helpdesk</p>
        </div>
      </aside>

      {/* Cột phải — form */}
      <main className="flex w-full items-center justify-center bg-slate-50 px-4 md:w-1/2">
        <div className="animate-fade-in-up w-full max-w-md rounded-2xl border border-slate-200
                        bg-white p-8 shadow-sm md:p-10">
          {/* Brand bù cho mobile */}
          <div className="mb-6 flex items-center gap-2 md:hidden">
            <img
              src="/help-desk-logo.jpg"
              alt="Smart IT Helpdesk"
              className="h-8 w-8 rounded-md object-cover"
            />
            <span className="text-sm font-semibold tracking-wide text-blue-600">
              Smart IT Helpdesk
            </span>
          </div>

          <h2 className="text-center text-xl font-semibold text-slate-900">Tạo tài khoản</h2>
          <p className="mt-1 mb-6 text-center text-sm text-slate-500">Tạo tài khoản nhân viên</p>

          {error && (
            <div
              role="alert"
              className="mb-4 rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-700"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="mb-1 block text-sm font-medium text-slate-700">
                Họ và tên
              </label>
              <input
                id="fullName"
                type="text"
                required
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm
                           text-slate-900 placeholder-slate-400 transition
                           focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-500/20
                           focus:outline-none"
                placeholder="Nguyễn Văn A"
              />
            </div>

            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm
                           text-slate-900 placeholder-slate-400 transition
                           focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-500/20
                           focus:outline-none"
                placeholder="ten.ban@company.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
                Mật khẩu
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm
                           text-slate-900 placeholder-slate-400 transition
                           focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-500/20
                           focus:outline-none"
                placeholder="Ít nhất 8 ký tự, có chữ hoa, chữ thường và số"
              />
            </div>

            {/* Vô hiệu hoá trong lúc chờ — chống bấm hai lần */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 py-3
                         text-sm font-medium text-white transition-all duration-200
                         shadow-lg shadow-blue-500/25 hover:scale-[1.02]
                         hover:from-blue-700 hover:to-blue-600 hover:shadow-blue-500/40
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Đang đăng ký…' : 'Đăng ký'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Đã có tài khoản?{' '}
            <Link to="/login" className="font-medium text-blue-600 hover:text-blue-700 hover:underline">
              Đăng nhập
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
